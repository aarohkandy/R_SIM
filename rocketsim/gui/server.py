"""Stdlib localhost server for the R-SIM workbench GUI."""

from __future__ import annotations

import csv
import json
import math
import mimetypes
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from rocketsim.gui.workbench import (
    list_workbench_files,
    read_workbench_file,
    rocket_summary,
    save_workbench_text,
    validate_workbench_text,
)
from rocketsim.sim.flight import run_native_sil_e2e

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_OUTPUT_ROOT = "outputs"


@dataclass(frozen=True)
class RunSummary:
    """Minimal run metadata for the GUI run tree."""

    run_id: str
    output_dir: Path
    touchdown: bool | None
    max_altitude_m: float | None
    touchdown_speed_m_s: float | None
    telemetry_rows: int | None


def discover_runs(repo_root: Path, output_root: str = DEFAULT_OUTPUT_ROOT) -> list[RunSummary]:
    """Discover output bundles that contain a landing summary or manifest."""

    root = (repo_root / output_root).resolve()
    if not root.exists():
        return []
    runs: list[RunSummary] = []
    for item in sorted(root.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True):
        if not item.is_dir():
            continue
        summary_path = item / "landing_summary.json"
        manifest_path = item / "run_manifest.json"
        if not summary_path.exists() and not manifest_path.exists():
            continue
        summary = _read_json(summary_path) if summary_path.exists() else {}
        runs.append(
            RunSummary(
                run_id=item.name,
                output_dir=item,
                touchdown=_optional_bool(summary.get("touchdown")),
                max_altitude_m=_optional_float(summary.get("max_altitude_m")),
                touchdown_speed_m_s=_optional_float(summary.get("touchdown_speed_m_s")),
                telemetry_rows=_optional_int(summary.get("telemetry_rows")),
            )
        )
    return runs


def read_run_detail(
    repo_root: Path,
    run_id: str,
    output_root: str = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Read summary, manifest, artifact URLs, and table previews for one run."""

    run_dir = _safe_run_dir(repo_root, output_root, run_id)
    summary = _read_json(run_dir / "landing_summary.json")
    manifest = _read_json(run_dir / "run_manifest.json")
    telemetry_preview = _read_csv_preview(run_dir / "telemetry.csv", max_rows=180)
    thermal_preview = _read_csv_preview(
        run_dir / "thermal" / "thermal_timeseries.csv",
        max_rows=120,
    )
    structural_preview = _read_csv_preview(run_dir / "structural" / "fea_results.csv", max_rows=120)
    artifact_index = _artifact_index(run_id, run_dir, manifest)
    return {
        "run_id": run_id,
        "summary": summary,
        "manifest": manifest,
        "artifacts": artifact_index,
        "telemetry_preview": telemetry_preview,
        "thermal_preview": thermal_preview,
        "structural_preview": structural_preview,
    }


def serve_gui(repo_root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve the local workbench until interrupted."""

    server = create_server(repo_root=repo_root, host=host, port=port)
    url = f"http://{str(server.server_address[0])}:{server.server_address[1]}"
    print(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def create_server(
    repo_root: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    """Create a configured GUI server. Tests use this with port 0."""

    root = repo_root.resolve()

    class RocketsimGuiHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            _handle_get(self, root)

        def do_POST(self) -> None:  # noqa: N802
            _handle_post(self, root)

        def log_message(self, format: str, *args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), RocketsimGuiHandler)


def _handle_get(handler: BaseHTTPRequestHandler, repo_root: Path) -> None:
    parsed = urlparse(handler.path)
    path = unquote(parsed.path)
    if path in ("/", "/index.html"):
        _send_file(handler, STATIC_DIR / "index.html")
        return
    if path.startswith("/static/"):
        _send_file(handler, STATIC_DIR / path.removeprefix("/static/"))
        return
    if path == "/api/runs":
        payload = [
            {
                "run_id": run.run_id,
                "touchdown": run.touchdown,
                "max_altitude_m": run.max_altitude_m,
                "touchdown_speed_m_s": run.touchdown_speed_m_s,
                "telemetry_rows": run.telemetry_rows,
            }
            for run in discover_runs(repo_root)
        ]
        _send_json(handler, {"runs": payload})
        return
    if path.startswith("/api/runs/"):
        run_id = path.removeprefix("/api/runs/").strip("/")
        try:
            detail = read_run_detail(repo_root, run_id)
        except FileNotFoundError:
            _send_error(handler, HTTPStatus.NOT_FOUND, "run not found")
            return
        _send_json(handler, detail)
        return
    if path.startswith("/artifacts/"):
        pieces = path.removeprefix("/artifacts/").split("/", 1)
        if len(pieces) != 2:
            _send_error(handler, HTTPStatus.NOT_FOUND, "artifact not found")
            return
        run_id, relative = pieces
        try:
            run_dir = _safe_run_dir(repo_root, DEFAULT_OUTPUT_ROOT, run_id)
            artifact_path = _safe_artifact_path(run_dir, relative)
        except FileNotFoundError:
            _send_error(handler, HTTPStatus.NOT_FOUND, "artifact not found")
            return
        _send_file(handler, artifact_path)
        return
    if path == "/api/telemetry":
        params = parse_qs(parsed.query)
        run_id = params.get("run", [""])[0]
        limit = _optional_int(params.get("limit", ["500"])[0]) or 500
        try:
            run_dir = _safe_run_dir(repo_root, DEFAULT_OUTPUT_ROOT, run_id)
            preview = _read_csv_preview(run_dir / "telemetry.csv", max_rows=max(1, limit))
        except FileNotFoundError:
            _send_error(handler, HTTPStatus.NOT_FOUND, "telemetry not found")
            return
        _send_json(handler, preview)
        return
    if path == "/api/configs":
        try:
            _send_json(handler, {"configs": list_workbench_files(repo_root)})
        except (FileNotFoundError, ValueError, TypeError) as exc:
            _send_error(handler, HTTPStatus.BAD_REQUEST, str(exc))
        return
    if path.startswith("/api/configs/"):
        name = path.removeprefix("/api/configs/").strip("/")
        try:
            _send_json(handler, read_workbench_file(repo_root, name))
        except FileNotFoundError:
            _send_error(handler, HTTPStatus.NOT_FOUND, "config file not found")
        return
    if path == "/api/rocket-summary":
        try:
            _send_json(handler, {"summary": rocket_summary(repo_root)})
        except (FileNotFoundError, ValueError, TypeError) as exc:
            _send_error(handler, HTTPStatus.BAD_REQUEST, str(exc))
        return
    _send_error(handler, HTTPStatus.NOT_FOUND, "route not found")


def _handle_post(handler: BaseHTTPRequestHandler, repo_root: Path) -> None:
    parsed = urlparse(handler.path)
    path = unquote(parsed.path)
    if path == "/api/run/e2e":
        try:
            result = run_native_sil_e2e(repo_root=repo_root)
        except Exception as exc:  # pragma: no cover - converted into GUI payload
            _send_json(handler, {"ok": False, "message": str(exc)})
            return
        _send_json(
            handler,
            {
                "ok": True,
                "run_id": result.output_dir.name,
                "output_dir": str(result.output_dir),
                "summary": result.summary,
            },
        )
        return
    if path.startswith("/api/configs/"):
        pieces = path.removeprefix("/api/configs/").strip("/").split("/")
        name = pieces[0] if pieces else ""
        try:
            body = _read_json_body(handler)
            text = body.get("text")
            if not isinstance(text, str):
                _send_error(handler, HTTPStatus.BAD_REQUEST, "request body needs text")
                return
            if len(pieces) == 2 and pieces[1] == "validate":
                _send_json(handler, validate_workbench_text(name, text))
                return
            if len(pieces) == 1:
                payload = save_workbench_text(repo_root, name, text)
                status = HTTPStatus.OK if payload.get("valid") else HTTPStatus.BAD_REQUEST
                _send_json(handler, payload, status=status)
                return
        except FileNotFoundError:
            _send_error(handler, HTTPStatus.NOT_FOUND, "config file not found")
            return
        except (ValueError, TypeError) as exc:
            _send_error(handler, HTTPStatus.BAD_REQUEST, str(exc))
            return
    _send_error(handler, HTTPStatus.NOT_FOUND, "route not found")


def _artifact_index(run_id: str, run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = manifest.get("artifacts", {})
    plot_files = sorted((run_dir / "plots").glob("*.png")) if (run_dir / "plots").exists() else []
    index = {
        "plots": [
            {
                "name": path.name,
                "url": f"/artifacts/{run_id}/plots/{path.name}",
            }
            for path in plot_files
        ],
        "animation_gif": _artifact_url(run_id, artifacts.get("animation_gif")),
        "animation_html": _artifact_url(run_id, artifacts.get("animation_html")),
        "telemetry_csv": _artifact_url(run_id, artifacts.get("telemetry_csv")),
        "telemetry_parquet": _artifact_url(run_id, artifacts.get("telemetry_parquet")),
        "landing_summary_json": _artifact_url(run_id, artifacts.get("landing_summary_json")),
        "thermal": _artifact_group_urls(run_id, artifacts.get("thermal")),
        "structural": _artifact_group_urls(run_id, artifacts.get("structural")),
    }
    return index


def _artifact_group_urls(run_id: str, group: Any) -> dict[str, Any]:
    if not isinstance(group, dict):
        return {}
    mapped: dict[str, Any] = {}
    for key, value in group.items():
        if isinstance(value, str):
            mapped[key] = _artifact_url(run_id, value)
        elif isinstance(value, list):
            mapped[key] = [_artifact_url(run_id, item) for item in value if isinstance(item, str)]
    return mapped


def _artifact_url(run_id: str, relative: Any) -> str | None:
    return f"/artifacts/{run_id}/{relative}" if isinstance(relative, str) else None


def _safe_run_dir(repo_root: Path, output_root: str, run_id: str) -> Path:
    if "/" in run_id or "\\" in run_id or run_id in ("", ".", ".."):
        raise FileNotFoundError(run_id)
    output_dir = (repo_root / output_root).resolve()
    run_dir = (output_dir / run_id).resolve()
    if not run_dir.exists() or output_dir not in run_dir.parents:
        raise FileNotFoundError(run_id)
    return run_dir


def _safe_artifact_path(run_dir: Path, relative: str) -> Path:
    artifact_path = (run_dir / relative).resolve()
    if not artifact_path.exists() or run_dir not in artifact_path.parents:
        raise FileNotFoundError(relative)
    return artifact_path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _read_csv_preview(path: Path, max_rows: int) -> dict[str, Any]:
    if not path.exists():
        return {"columns": [], "rows": [], "row_count": 0}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows: list[Mapping[str, str]] = []
        row_count = 0
        stride = 1
        for row in reader:
            if row_count >= max_rows * stride:
                stride *= 2
                rows = rows[::2]
            if row_count % stride == 0:
                rows.append(row)
            row_count += 1
    return {"columns": columns, "rows": rows[:max_rows], "row_count": row_count}


def _send_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
    if not path.exists() or not path.is_file():
        _send_error(handler, HTTPStatus.NOT_FOUND, "file not found")
        return
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = path.read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _send_json(
    handler: BaseHTTPRequestHandler,
    payload: dict[str, Any],
    status: HTTPStatus = HTTPStatus.OK,
) -> None:
    data = json.dumps(_json_safe(payload), sort_keys=True, allow_nan=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _send_error(handler: BaseHTTPRequestHandler, status: HTTPStatus, message: str) -> None:
    payload = json.dumps({"error": message}).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    payload = json.loads(raw.decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _optional_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
