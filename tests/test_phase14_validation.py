from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
import yaml

from rocketsim.sim import load_sim_config
from rocketsim.sim.flight import SILRunResult
from rocketsim.validation.phase14 import (
    MonteCarloScenario,
    apply_scenario_to_repo,
    distribution_summary,
    generate_monte_carlo_scenarios,
    run_phase14_monte_carlo,
)

ROOT = Path(__file__).resolve().parents[1]


def write_phase14_repo(root: Path) -> Path:
    shutil.copytree(ROOT / "config", root / "config")
    shutil.copytree(ROOT / "inputs", root / "inputs")
    return root


def fake_phase14_runner(
    *,
    repo_root: Path,
    output_root: Path,
    run_id_override: str,
) -> SILRunResult:
    output_root.mkdir(parents=True, exist_ok=True)
    sim = load_sim_config(repo_root / "config" / "sim.yaml")
    environment = yaml.safe_load((repo_root / "config" / "environment.yaml").read_text())
    coldgas = yaml.safe_load((repo_root / "config" / "coldgas.yaml").read_text())
    actuation = yaml.safe_load((repo_root / "config" / "actuation.yaml").read_text())
    wind = environment["data"]["wind"]["steady_m_s"]
    axis = np.asarray(coldgas["data"]["nozzles"]["items"][0]["axis_unit"], dtype=np.float64)
    open_latency_s = float(actuation["data"]["open_latency_s"])
    wind_norm = float(np.linalg.norm(np.asarray(wind[:2], dtype=np.float64)))
    summary = {
        "touchdown": True,
        "touchdown_time_s": 9.0 + 0.001 * (sim.data.master_seed % 100),
        "touchdown_speed_m_s": 12.0 + 0.2 * wind_norm,
        "touchdown_vertical_speed_m_s": -11.0 - 0.1 * wind_norm,
        "touchdown_tilt_deg": abs(float(axis[0])) * 100.0 + abs(float(axis[1])) * 100.0,
        "touchdown_lateral_error_m": 0.5 * wind_norm,
        "co2_remaining_kg": max(0.0, 0.085 - open_latency_s),
        "max_altitude_m": 80.0 + wind_norm,
        "max_dynamic_pressure_pa": 200.0 + 5.0 * wind_norm,
        "telemetry_rows": 9000,
    }
    return cast(
        SILRunResult,
        SimpleNamespace(
            summary=summary,
            telemetry_hash=f"telemetry-{run_id_override}",
            state_hash=f"state-{run_id_override}",
        ),
    )


def test_phase14_config_loads_large_n_contract() -> None:
    sim = load_sim_config(ROOT / "config" / "sim.yaml")

    assert sim.data.phase14.target_runs == 1000
    assert sim.data.phase14.batch_size == 100
    assert sim.data.phase14.resume_enabled is True
    assert sim.data.phase14.checkpoint_interval_runs == 25
    assert sim.data.phase14.dispersions.wind_xy_std_m_s == pytest.approx(2.0)


def test_scenario_generation_is_deterministic_and_spawned() -> None:
    sim = load_sim_config(ROOT / "config" / "sim.yaml")

    first = generate_monte_carlo_scenarios(sim, run_count=5, nozzle_count=3)
    second = generate_monte_carlo_scenarios(sim, run_count=5, nozzle_count=3)
    changed_seed = sim.model_copy(
        update={"data": sim.data.model_copy(update={"master_seed": sim.data.master_seed + 1})}
    )
    changed = generate_monte_carlo_scenarios(changed_seed, run_count=5, nozzle_count=3)

    assert [scenario.flat_row() for scenario in first] == [
        scenario.flat_row() for scenario in second
    ]
    assert [scenario.spawn_key for scenario in first] == [(0,), (1,), (2,), (3,), (4,)]
    assert first[0].flat_row() != changed[0].flat_row()


def test_apply_scenario_mutates_copied_yaml_inputs(tmp_path: Path) -> None:
    repo = write_phase14_repo(tmp_path / "repo")
    scenario = MonteCarloScenario(
        index=0,
        seed=1,
        spawn_key=(0,),
        sensor_seed=222,
        wind_m_s=(3.0, -2.0, 0.0),
        mass_scale=1.1,
        cg_shift_m=(0.01, -0.02, 0.03),
        nozzle_cant_deg=((1.0, -1.0), (0.5, 0.25), (-0.5, 0.75)),
        valve_latency_delta_s=0.005,
    )
    scenario_root = apply_scenario_to_repo(repo, scenario, tmp_path / "scenario")

    environment = _read_yaml(scenario_root / "config" / "environment.yaml")
    bom = _read_yaml(scenario_root / "inputs" / "bom_placeholder.yaml")
    coldgas = _read_yaml(scenario_root / "config" / "coldgas.yaml")
    actuation = _read_yaml(scenario_root / "config" / "actuation.yaml")
    sim = load_sim_config(scenario_root / "config" / "sim.yaml")

    assert environment["data"]["wind"]["enabled"] is True
    assert environment["data"]["wind"]["steady_m_s"] == [3.0, -2.0, 0.0]
    assert bom["parts"][0]["mass_kg"] == pytest.approx(0.088)
    assert bom["parts"][0]["position_m"] == pytest.approx([0.01, -0.02, 0.03])
    first_axis = np.asarray(coldgas["data"]["nozzles"]["items"][0]["axis_unit"])
    assert np.linalg.norm(first_axis) == pytest.approx(1.0)
    assert first_axis[2] < 1.0
    assert actuation["data"]["open_latency_s"] == pytest.approx(0.015)
    assert sim.data.master_seed == 222


def test_distribution_summary_reports_percentiles_without_verdicts() -> None:
    frame = _sample_frame()

    summary = distribution_summary(
        frame,
        ("landing_speed_m_s", "co2_margin_kg"),
        (5.0, 50.0, 95.0),
    )

    assert summary["landing_speed_m_s"]["count"] == 4
    assert summary["landing_speed_m_s"]["percentiles"]["p50"] == pytest.approx(13.0)
    assert "pass" not in json.dumps(summary).lower()


def test_phase14_runner_writes_samples_histograms_and_manifest(tmp_path: Path) -> None:
    repo = write_phase14_repo(tmp_path / "repo")
    result = run_phase14_monte_carlo(
        repo,
        runner=fake_phase14_runner,
        run_count_override=8,
    )

    summary = json.loads(result.summary_json.read_text(encoding="utf-8"))
    manifest = json.loads(result.manifest_json.read_text(encoding="utf-8"))

    assert result.samples_csv.exists()
    assert result.samples_parquet.exists()
    assert result.stability_csv.exists()
    assert all(path.exists() and path.stat().st_size > 0 for path in result.histogram_paths)
    assert summary["runs_completed"] == 8
    assert summary["requested_runs"] == 8
    assert summary["target_runs"] == 1000
    assert summary["gate_complete"] is False
    assert summary["resume_enabled"] is True
    assert summary["resumed_rows"] == 0
    assert len(summary["phase14_signature"]) == 64
    assert summary["stability"]["status"] == "insufficient_batches"
    assert manifest["scenario_generation"]["seed_strategy"] == "numpy.random.SeedSequence.spawn"
    assert manifest["scenario_generation"]["resume_signature"] == summary["phase14_signature"]


def test_phase14_default_dispatch_retains_full_bundles_only_at_stride(tmp_path: Path) -> None:
    import pandas as pd  # type: ignore[import-untyped]

    repo = write_phase14_repo(tmp_path / "repo")
    calls = {"full": 0, "metrics": 0}

    def full_runner(**kwargs: Any) -> SILRunResult:
        calls["full"] += 1
        return fake_phase14_runner(**kwargs)

    def metrics_runner(**kwargs: Any) -> SILRunResult:
        calls["metrics"] += 1
        return fake_phase14_runner(**kwargs)

    result = run_phase14_monte_carlo(
        repo,
        full_runner=full_runner,
        metrics_runner=metrics_runner,
        run_count_override=3,
    )
    samples = pd.read_csv(result.samples_csv)

    assert calls == {"full": 1, "metrics": 2}
    assert samples["artifact_mode"].tolist() == [
        "full_bundle",
        "metrics_only",
        "metrics_only",
    ]
    assert samples["retained_bundle"].tolist() == [True, False, False]


def test_phase14_resume_skips_completed_indices(tmp_path: Path) -> None:
    import pandas as pd

    repo = write_phase14_repo(tmp_path / "repo")
    first = run_phase14_monte_carlo(
        repo,
        runner=fake_phase14_runner,
        run_count_override=3,
    )
    first_samples = pd.read_csv(first.samples_csv)
    calls: list[str] = []

    def tracking_runner(**kwargs: Any) -> SILRunResult:
        calls.append(str(kwargs["run_id_override"]))
        return fake_phase14_runner(**kwargs)

    second = run_phase14_monte_carlo(
        repo,
        runner=tracking_runner,
        run_count_override=5,
    )
    second_samples = pd.read_csv(second.samples_csv)

    assert first.summary["runs_completed"] == 3
    assert first_samples["run_index"].tolist() == [0, 1, 2]
    assert calls == [second_samples.loc[3, "run_id"], second_samples.loc[4, "run_id"]]
    assert second.summary["runs_completed"] == 5
    assert second.summary["resumed_rows"] == 3
    assert second_samples["run_index"].tolist() == [0, 1, 2, 3, 4]
    assert second_samples["phase14_signature"].nunique() == 1


def test_cli_montecarlo_dispatch_can_be_monkeypatched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rocketsim import cli

    monkeypatch.setattr(
        cli,
        "run_phase14_monte_carlo",
        lambda repo_root: SimpleNamespace(
            manifest_json=tmp_path / "phase14_manifest.json",
            summary={
                "runs_completed": 8,
                "gate_complete": False,
                "stability": {"status": "insufficient_batches"},
            },
        ),
    )

    assert cli.main(["montecarlo", "--repo-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "phase14_manifest.json" in out
    assert "runs=8" in out


def _sample_frame() -> Any:
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "landing_speed_m_s": 10.0,
                "touchdown_tilt_deg": 1.0,
                "touchdown_lateral_error_m": 0.1,
                "co2_margin_kg": 0.08,
            },
            {
                "landing_speed_m_s": 12.0,
                "touchdown_tilt_deg": 2.0,
                "touchdown_lateral_error_m": 0.2,
                "co2_margin_kg": 0.079,
            },
            {
                "landing_speed_m_s": 14.0,
                "touchdown_tilt_deg": 3.0,
                "touchdown_lateral_error_m": 0.3,
                "co2_margin_kg": 0.078,
            },
            {
                "landing_speed_m_s": 16.0,
                "touchdown_tilt_deg": 4.0,
                "touchdown_lateral_error_m": 0.4,
                "co2_margin_kg": 0.077,
            },
        ]
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)
