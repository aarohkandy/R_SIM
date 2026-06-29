from __future__ import annotations

import json
import shutil
import threading
import urllib.request
from pathlib import Path

import pytest

from rocketsim.gui import discover_runs, read_run_detail
from rocketsim.gui.server import create_server
from rocketsim.gui.workbench import (
    list_workbench_files,
    read_workbench_file,
    rocket_summary,
    save_workbench_text,
    validate_workbench_text,
)

ROOT = Path(__file__).resolve().parents[1]


def write_run(root: Path) -> Path:
    run_dir = root / "outputs" / "unit_run"
    plots_dir = run_dir / "plots"
    thermal_dir = run_dir / "thermal"
    plots_dir.mkdir(parents=True)
    thermal_dir.mkdir()
    (run_dir / "landing_summary.json").write_text(
        json.dumps(
            {
                "touchdown": True,
                "max_altitude_m": 12.3,
                "touchdown_speed_m_s": 4.5,
                "telemetry_rows": 3,
                "thermal": {"peak_temperature_deg_c": 24.0},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "seed": 1,
                "backend": "sil",
                "artifacts": {
                    "telemetry_csv": "telemetry.csv",
                    "animation_gif": "flight_animation.gif",
                    "thermal": {"summary_json": "thermal/thermal_summary.json"},
                },
                "deferred_artifacts": {},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "telemetry.csv").write_text(
        "time_s,position_z_m,velocity_z_m_s\n0,0,1\n1,2,3\n2,4,5\n",
        encoding="utf-8",
    )
    (thermal_dir / "thermal_summary.json").write_text("{}", encoding="utf-8")
    (plots_dir / "altitude_velocity_accel.png").write_bytes(b"not-a-real-png")
    (run_dir / "flight_animation.gif").write_bytes(b"GIF89a")
    return run_dir


def write_workbench_repo(root: Path) -> Path:
    shutil.copytree(ROOT / "config", root / "config")
    shutil.copytree(ROOT / "inputs", root / "inputs")
    (root / "outputs").mkdir()
    return root


def test_gui_discovers_runs_and_reads_details(tmp_path: Path) -> None:
    write_run(tmp_path)

    runs = discover_runs(tmp_path)
    detail = read_run_detail(tmp_path, "unit_run")

    assert [run.run_id for run in runs] == ["unit_run"]
    assert detail["summary"]["touchdown"] is True
    assert detail["artifacts"]["animation_gif"] == "/artifacts/unit_run/flight_animation.gif"
    assert detail["artifacts"]["thermal"]["summary_json"] == (
        "/artifacts/unit_run/thermal/thermal_summary.json"
    )
    assert detail["telemetry_preview"]["row_count"] == 3


def test_gui_http_api_serves_index_and_runs(tmp_path: Path) -> None:
    write_run(tmp_path)
    server = create_server(tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{str(server.server_address[0])}:{server.server_address[1]}"
    try:
        index = urllib.request.urlopen(f"{base}/", timeout=5).read().decode("utf-8")
        runs = json.loads(urllib.request.urlopen(f"{base}/api/runs", timeout=5).read())
        detail = json.loads(
            urllib.request.urlopen(f"{base}/api/runs/unit_run", timeout=5).read()
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "R-SIM Workbench" in index
    assert "Rocket Definition" in index
    assert runs["runs"][0]["run_id"] == "unit_run"
    assert detail["telemetry_preview"]["columns"] == [
        "time_s",
        "position_z_m",
        "velocity_z_m_s",
    ]


def test_cli_gui_dispatch_can_be_monkeypatched(monkeypatch: pytest.MonkeyPatch) -> None:
    from rocketsim import cli

    called: dict[str, object] = {}

    def fake_serve_gui(repo_root: Path, host: str, port: int) -> None:
        called["repo_root"] = repo_root
        called["host"] = host
        called["port"] = port

    monkeypatch.setattr(cli, "serve_gui", fake_serve_gui)

    assert cli.main(["gui", "--repo-root", ".", "--host", "127.0.0.1", "--port", "9001"]) == 0
    assert called["host"] == "127.0.0.1"
    assert called["port"] == 9001


def test_workbench_lists_reads_validates_and_saves_definition_files(tmp_path: Path) -> None:
    repo = write_workbench_repo(tmp_path)

    files = list_workbench_files(repo)
    bom = read_workbench_file(repo, "bom")
    invalid = validate_workbench_text("bom", "schema_version: 1\nparts: []\n")
    edited = bom["text"].replace("mass_kg: 0.08", "mass_kg: 0.081", 1)
    saved = save_workbench_text(repo, "bom", edited)
    summary = rocket_summary(repo)

    assert any(item["name"] == "bom" and item["valid"] for item in files)
    assert bom["path"] == "inputs/bom_placeholder.yaml"
    assert invalid["valid"] is False
    assert saved["valid"] is True
    assert "mass_kg: 0.081" in (repo / "inputs" / "bom_placeholder.yaml").read_text(
        encoding="utf-8"
    )
    assert summary["wet_mass_kg"] > 0.0


def test_gui_http_config_api_validates_and_saves(tmp_path: Path) -> None:
    repo = write_workbench_repo(tmp_path)
    server = create_server(repo, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{str(server.server_address[0])}:{server.server_address[1]}"
    try:
        configs = json.loads(urllib.request.urlopen(f"{base}/api/configs", timeout=5).read())
        bom = json.loads(urllib.request.urlopen(f"{base}/api/configs/bom", timeout=5).read())
        bad_request = urllib.request.Request(
            f"{base}/api/configs/bom/validate",
            data=json.dumps({"text": "schema_version: 1\nparts: []\n"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        invalid = json.loads(urllib.request.urlopen(bad_request, timeout=5).read())
        edited = bom["text"].replace("mass_kg: 0.08", "mass_kg: 0.082", 1)
        save_request = urllib.request.Request(
            f"{base}/api/configs/bom",
            data=json.dumps({"text": edited}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        saved = json.loads(urllib.request.urlopen(save_request, timeout=5).read())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert any(item["name"] == "bom" for item in configs["configs"])
    assert bom["valid"] is True
    assert invalid["valid"] is False
    assert saved["valid"] is True
