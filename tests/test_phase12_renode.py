from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from rocketsim.control import (
    RenodeHILBackend,
    RenodeUnavailableError,
    actuator_levels_to_valves,
    build_renode_hil_report,
    run_renode_hil_status,
    sensor_packet_to_injection_frame,
)
from rocketsim.sensors import BarometerReading, IMUReading, SensorPacket

ROOT = Path(__file__).resolve().parents[1]


def write_phase12_repo(root: Path, *, backend: str = "sil", verified: bool = False) -> Path:
    (root / "config").mkdir()
    (root / "firmware").mkdir()
    (root / "renode" / "scripts").mkdir(parents=True)
    (root / "renode" / "platforms").mkdir(parents=True)
    shutil.copy(ROOT / "config" / "control.yaml", root / "config" / "control.yaml")
    shutil.copy(ROOT / "config" / "sim.yaml", root / "config" / "sim.yaml")
    payload = yaml.safe_load((root / "config" / "control.yaml").read_text(encoding="utf-8"))
    payload["data"]["backend"] = backend
    for machine in payload["data"]["renode"]["machines"]:
        machine["platform_verified"] = verified
    (root / "config" / "control.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )
    (root / "renode" / "scripts" / "dual_mcu_cosim.resc").write_text(
        "mach create \"teensy\"\n",
        encoding="utf-8",
    )
    (root / "renode" / "platforms" / "esp32_placeholder.repl").write_text(
        "// esp32\n",
        encoding="utf-8",
    )
    (root / "renode" / "platforms" / "teensy_imxrt1062_placeholder.repl").write_text(
        "// teensy\n",
        encoding="utf-8",
    )
    return root


def packet() -> SensorPacket:
    return SensorPacket(
        time_s=1.25,
        imu=IMUReading(
            time_s=1.25,
            accel_m_s2=np.asarray((1.0, 2.0, 3.0), dtype=np.float64),
            gyro_rad_s=np.asarray((0.1, 0.2, 0.3), dtype=np.float64),
            truth_specific_force_body_m_s2=np.asarray((1.5, 2.5, 3.5), dtype=np.float64),
            truth_angular_velocity_rad_s=np.asarray((0.4, 0.5, 0.6), dtype=np.float64),
            accel_bias_m_s2=np.zeros(3, dtype=np.float64),
            gyro_bias_rad_s=np.zeros(3, dtype=np.float64),
        ),
        barometer=BarometerReading(
            time_s=1.25,
            pressure_pa=100100.0,
            altitude_m=102.0,
            truth_pressure_pa=100000.0,
            truth_altitude_m=103.0,
            pressure_bias_pa=0.5,
        ),
        tof_range_m=None,
        pressure_transducer_pa=None,
    )


def test_renode_preflight_reports_exact_missing_local_blockers() -> None:
    report = build_renode_hil_report(
        ROOT,
        executable_resolver=lambda _: None,
        module_resolver=lambda _: False,
        generated_at_utc="2026-06-29T00:00:00+00:00",
    )
    codes = {blocker.code for blocker in report.blockers}

    assert report.ready is False
    assert "renode_executable_missing" in codes
    assert "python_bridge_module_missing" in codes
    assert "esp32_firmware_elf_missing" in codes
    assert "teensy_firmware_elf_missing" in codes
    assert "esp32_platform_repl_unverified" in codes
    assert "teensy_platform_repl_unverified" in codes
    assert report.time_sync["renode_sync_quantum_s"] == pytest.approx(0.001)


def test_renode_preflight_can_be_ready_when_all_artifacts_are_present(tmp_path: Path) -> None:
    repo = write_phase12_repo(tmp_path, backend="renode", verified=True)
    (repo / "firmware" / "esp32_flight.elf").write_bytes(b"\x7fELFesp32")
    (repo / "firmware" / "teensy_flight.elf").write_bytes(b"\x7fELFteensy")

    report = build_renode_hil_report(
        repo,
        executable_resolver=lambda _: "/usr/local/bin/renode",
        module_resolver=lambda _: True,
        generated_at_utc="2026-06-29T00:00:00+00:00",
    )

    assert report.ready is True
    assert report.blockers == ()
    assert report.status == "ready"
    assert report.backend == "renode"


def test_make_hil_status_writes_json_and_markdown(tmp_path: Path) -> None:
    repo = write_phase12_repo(tmp_path)

    result = run_renode_hil_status(
        repo,
        executable_resolver=lambda _: None,
        module_resolver=lambda _: False,
    )
    payload = json.loads(result.status_json.read_text(encoding="utf-8"))

    assert result.status_json.exists()
    assert result.status_markdown.exists()
    assert payload["status"] == "blocked"
    assert payload["blockers"]


def test_renode_backend_preserves_controller_seam_and_refuses_fake_step(tmp_path: Path) -> None:
    repo = write_phase12_repo(tmp_path, backend="renode")
    backend = RenodeHILBackend.from_config_path(repo)
    backend.reset(123)

    with pytest.raises(RenodeUnavailableError, match="Renode HIL is not ready"):
        backend.step(packet(), 1.25)

    telemetry = backend.telemetry()
    assert telemetry["backend"] == "renode"
    assert telemetry["ready"] is False
    assert telemetry["last_sensor_frame"]["barometer"]["altitude_m"] == pytest.approx(102.0)


def test_sensor_injection_and_actuator_mapping_are_deterministic() -> None:
    frame = sensor_packet_to_injection_frame(packet())
    valves = actuator_levels_to_valves((True, False, True), 3)

    assert frame["time_s"] == pytest.approx(1.25)
    assert frame["imu"]["accel_m_s2"] == [1.0, 2.0, 3.0]
    assert frame["barometer"]["pressure_pa"] == pytest.approx(100100.0)
    assert valves.states == (True, False, True)
    with pytest.raises(ValueError, match="expected 3 actuator lines"):
        actuator_levels_to_valves((True, False), 3)


def test_cli_hil_dispatch_can_be_monkeypatched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from rocketsim import cli

    monkeypatch.setattr(
        cli,
        "run_renode_hil_status",
        lambda repo_root: SimpleNamespace(
            status_json=tmp_path / "renode_hil_status.json",
            report=SimpleNamespace(status="blocked", blockers=[object(), object()]),
        ),
    )

    assert cli.main(["hil", "--repo-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "renode_hil_status.json" in out
    assert "status=blocked blockers=2" in out
