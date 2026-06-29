from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from pydantic import ValidationError

from rocketsim.actuation import (
    ControlAllocator,
    ControlDemand,
    SolenoidValveBank,
    ValveCommands,
    allocation_matrix,
    load_actuation_config,
)
from rocketsim.control import NativeSILBackend, load_control_config, valve_timeline_durations
from rocketsim.propulsion import ColdGasSystem
from rocketsim.sensors import BarometerReading, IMUReading, SensorPacket
from rocketsim.sim.flight import run_native_sil_e2e

ROOT = Path(__file__).resolve().parents[1]
CONTROL_CONFIG = ROOT / "config" / "control.yaml"
ACTUATION_CONFIG = ROOT / "config" / "actuation.yaml"
COLDGAS_CONFIG = ROOT / "config" / "coldgas.yaml"


def packet(time_s: float, altitude_m: float) -> SensorPacket:
    return SensorPacket(
        time_s=time_s,
        imu=IMUReading(
            time_s=time_s,
            accel_m_s2=np.asarray((0.0, 0.0, 9.81), dtype=np.float64),
            gyro_rad_s=np.asarray((0.0, 0.0, 0.0), dtype=np.float64),
            truth_specific_force_body_m_s2=np.asarray((0.0, 0.0, 9.81), dtype=np.float64),
            truth_angular_velocity_rad_s=np.zeros(3, dtype=np.float64),
            accel_bias_m_s2=np.zeros(3, dtype=np.float64),
            gyro_bias_rad_s=np.zeros(3, dtype=np.float64),
        ),
        barometer=BarometerReading(
            time_s=time_s,
            pressure_pa=101325.0,
            altitude_m=altitude_m,
            truth_pressure_pa=101325.0,
            truth_altitude_m=altitude_m,
            pressure_bias_pa=0.0,
        ),
        tof_range_m=None,
        pressure_transducer_pa=None,
    )


def test_control_and_actuation_configs_load() -> None:
    control = load_control_config(CONTROL_CONFIG)
    actuation = load_actuation_config(ACTUATION_CONFIG)

    assert control.data.backend == "sil"
    assert control.data.loop_rate_hz == pytest.approx(100.0)
    assert actuation.data.min_reliable_pulse_s == pytest.approx(0.02)


def test_allocator_maps_collective_to_all_three_nozzles() -> None:
    actuation = load_actuation_config(ACTUATION_CONFIG)
    coldgas = ColdGasSystem.from_config_path(COLDGAS_CONFIG)
    allocator = ControlAllocator(actuation, coldgas)

    matrix = allocation_matrix(coldgas)
    result = allocator.allocate(ControlDemand(collective=1.0, torque_x=0.0, torque_y=0.0))

    assert matrix.shape == (3, 3)
    assert result.raw_commands.states == (True, True, True)
    assert all(0.0 <= duty <= 1.0 for duty in result.duty_fractions)


def test_solenoid_bank_enforces_latency_and_minimum_pulse() -> None:
    bank = SolenoidValveBank(load_actuation_config(ACTUATION_CONFIG))
    times: list[float] = []
    states: list[tuple[bool, ...]] = []

    for t_s, desired in [
        (0.0, ValveCommands((True, False, False))),
        (0.010, ValveCommands((True, False, False))),
        (0.011, ValveCommands((False, False, False))),
        (0.031, ValveCommands((False, False, False))),
        (0.041, ValveCommands((False, False, False))),
    ]:
        actual = bank.update(desired, t_s)
        times.append(t_s)
        states.append(actual.states)

    assert states[0][0] is False
    assert states[1][0] is True
    assert states[2][0] is True
    assert states[-1][0] is False
    assert max(valve_timeline_durations(times, states)) >= 0.02


def test_native_sil_backend_respects_latency_before_valves_open() -> None:
    backend = NativeSILBackend.from_config_paths(CONTROL_CONFIG, ACTUATION_CONFIG, COLDGAS_CONFIG)
    backend.reset(123)

    assert backend.step(packet(2.00, 40.0), 2.00).states == (False, False, False)
    assert backend.step(packet(2.01, 35.0), 2.01).states == (False, False, False)
    assert backend.step(packet(2.02, 30.0), 2.02).states == (False, False, False)
    assert any(backend.step(packet(2.03, 25.0), 2.03).states)
    assert backend.telemetry()["collective_duty"] > 0.0


def test_phase8_e2e_native_sil_writes_full_phase9_bundle(tmp_path: Path) -> None:
    result = run_native_sil_e2e(repo_root=ROOT, output_root=tmp_path)

    assert result.summary["touchdown"] is True
    assert result.telemetry_csv.exists()
    assert result.telemetry_parquet.exists()
    assert result.landing_summary_json.exists()
    assert result.landing_summary_csv.exists()
    assert result.run_manifest_json.exists()
    assert result.animation_gif.exists()
    assert result.animation_html.exists()
    assert result.thermal_artifacts.timeseries_csv.exists()
    assert result.thermal_artifacts.timeseries_parquet.exists()
    assert result.thermal_artifacts.summary_json.exists()
    assert len(result.thermal_artifacts.plot_paths) == 2
    assert result.structural_artifacts.load_cases_json.exists()
    assert result.structural_artifacts.fea_results_parquet.exists()
    assert result.structural_artifacts.summary_json.exists()
    assert result.structural_artifacts.calculix_input.exists()
    assert len(result.structural_artifacts.plot_paths) == 3
    assert len(result.plot_paths) >= 6
    assert all(path.exists() and path.stat().st_size > 0 for path in result.plot_paths)
    assert all(
        path.exists() and path.stat().st_size > 0
        for path in result.thermal_artifacts.plot_paths
    )
    assert all(
        path.exists() and path.stat().st_size > 0
        for path in result.structural_artifacts.plot_paths
    )
    assert result.summary["telemetry_rows"] > 1000
    assert "thermal" in result.summary
    assert "peak_thermal_temperature_deg_c" in result.summary
    assert "minimum_thermal_margin_deg_c" in result.summary
    assert "structural" in result.summary
    assert "peak_structural_stress_pa" in result.summary
    assert "peak_structural_displacement_m" in result.summary
    manifest = json.loads(result.run_manifest_json.read_text(encoding="utf-8"))
    assert manifest["backend"] == "sil"
    assert manifest["telemetry_hash"] == result.telemetry_hash
    assert len(manifest["state_hash"]) == 64
    assert manifest["artifacts"]["telemetry_parquet"] == "telemetry.parquet"
    assert manifest["artifacts"]["thermal"]["summary_json"] == "thermal/thermal_summary.json"
    assert manifest["artifacts"]["structural"]["summary_json"] == (
        "structural/structural_summary.json"
    )
    assert "animation_gif" in manifest["artifacts"]
    assert "animation_html" in manifest["artifacts"]
    assert "deferred_artifacts" in manifest
    assert "thermal_node_temperature_plots" not in manifest["deferred_artifacts"]
    assert "fea_stress_summary_plots" not in manifest["deferred_artifacts"]


def test_invalid_actuation_fault_index_rejected() -> None:
    payload = load_actuation_config(ACTUATION_CONFIG).model_dump(mode="python")
    payload["data"]["fault_injection"]["stuck_open"] = (99,)

    with pytest.raises(ValidationError, match="fault valve indices"):
        load_actuation_config_from_payload(payload)


def load_actuation_config_from_payload(payload: dict[str, object]) -> object:
    from rocketsim.actuation.schema import ActuationConfig

    return ActuationConfig.model_validate(payload)


def test_cli_e2e_dispatch_can_be_monkeypatched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rocketsim import cli

    monkeypatch.setattr(
        cli,
        "run_native_sil_e2e",
        lambda repo_root, output_root: SimpleNamespace(output_dir=tmp_path / "bundle"),
    )

    assert cli.main(["e2e", "--output-root", str(tmp_path)]) == 0
    assert str(tmp_path / "bundle") in capsys.readouterr().out
