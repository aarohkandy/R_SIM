from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from rocketsim.sim import SimConfig, load_sim_config
from rocketsim.sim.flight import SILRunResult
from rocketsim.validation.phase13 import (
    ballistic_cross_validation,
    convergence_rows_with_deltas,
    run_phase13_convergence,
)

ROOT = Path(__file__).resolve().parents[1]


def write_phase13_repo(root: Path) -> Path:
    shutil.copytree(ROOT / "config", root / "config")
    shutil.copytree(ROOT / "inputs", root / "inputs")
    return root


def fake_sil_runner(
    *,
    repo_root: Path,
    output_root: Path,
    sim_config_override: SimConfig,
    run_id_override: str,
) -> SILRunResult:
    del repo_root, output_root
    dt_s = sim_config_override.data.integrator_dt_s
    summary = {
        "touchdown_time_s": 9.31 + 0.5 * dt_s,
        "touchdown_speed_m_s": 18.33 + 2.0 * dt_s,
        "touchdown_vertical_speed_m_s": -18.0 - dt_s,
        "max_altitude_m": 75.68 + 4.0 * dt_s,
        "co2_remaining_kg": 0.0808 - 0.1 * dt_s,
        "telemetry_rows": int(10.0 / dt_s),
    }
    return cast(
        SILRunResult,
        SimpleNamespace(
            summary=summary,
            telemetry_hash=f"telemetry-{run_id_override}",
            state_hash=f"state-{run_id_override}",
        ),
    )


def test_phase13_config_loads() -> None:
    sim = load_sim_config(ROOT / "config" / "sim.yaml")

    assert sim.data.phase13.integrator_dt_values_s == (0.002, 0.001, 0.0005)
    assert sim.data.phase13.renode_sync_quantum_values_s == (0.002, 0.001, 0.0005)
    assert sim.data.phase13.output_dir == "outputs/phase13_convergence"


def test_convergence_rows_are_reported_against_finest_timestep() -> None:
    rows = convergence_rows_with_deltas(
        [
            {
                "integrator_dt_s": 0.002,
                "touchdown_time_s": 10.0,
                "touchdown_speed_m_s": 4.0,
                "touchdown_vertical_speed_m_s": -3.0,
                "max_altitude_m": 12.0,
                "co2_remaining_kg": 0.08,
            },
            {
                "integrator_dt_s": 0.001,
                "touchdown_time_s": 9.0,
                "touchdown_speed_m_s": 3.5,
                "touchdown_vertical_speed_m_s": -3.1,
                "max_altitude_m": 12.5,
                "co2_remaining_kg": 0.081,
            },
        ]
    )

    assert rows[0]["integrator_dt_s"] == pytest.approx(0.002)
    assert rows[0]["touchdown_speed_abs_delta_m_s"] == pytest.approx(0.5)
    assert rows[1]["touchdown_speed_abs_delta_m_s"] == pytest.approx(0.0)


def test_phase13_runner_writes_convergence_and_cross_validation_artifacts(
    tmp_path: Path,
) -> None:
    repo = write_phase13_repo(tmp_path)
    result = run_phase13_convergence(repo, runner=fake_sil_runner)

    convergence = json.loads(result.convergence_json.read_text(encoding="utf-8"))
    cross_validation = json.loads(result.cross_validation_json.read_text(encoding="utf-8"))
    manifest = json.loads(result.manifest_json.read_text(encoding="utf-8"))

    assert result.convergence_csv.exists()
    assert result.openrocket_csv.exists()
    assert result.plot_path.exists()
    assert len(convergence["rows"]) == 3
    assert cross_validation["ballistic"]["position_error_norm_m"] < 1.0e-9
    assert cross_validation["openrocket_anchor"]["rows"]
    assert manifest["summary"]["convergence_rows"] == 3


def test_ballistic_cross_validation_matches_analytic_solution() -> None:
    report = ballistic_cross_validation(1.0)

    assert report["position_error_norm_m"] < 1.0e-9
    assert report["velocity_error_norm_m_s"] < 1.0e-9


def test_cli_converge_dispatch_can_be_monkeypatched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rocketsim import cli

    monkeypatch.setattr(
        cli,
        "run_phase13_convergence",
        lambda repo_root: SimpleNamespace(
            manifest_json=tmp_path / "phase13_manifest.json",
            summary={"convergence_rows": 3, "rocketpy_status": "unavailable_documented"},
        ),
    )

    assert cli.main(["converge", "--repo-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "phase13_manifest.json" in out
    assert "rows=3" in out


def test_fake_runner_signature_matches_phase13_call() -> None:
    sim = load_sim_config(ROOT / "config" / "sim.yaml")
    result = fake_sil_runner(
        repo_root=ROOT,
        output_root=ROOT / "outputs",
        sim_config_override=sim,
        run_id_override="unit",
    )

    assert result.summary["touchdown_speed_m_s"] > 0.0
