"""Renode hardware-in-the-loop backend scaffold and bring-up status."""

from __future__ import annotations

import importlib.util
import json
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from rocketsim.actuation import ValveCommands
from rocketsim.control.backend import ControllerBackend
from rocketsim.control.schema import ControlConfig, RenodeMachineConfig, load_control_config
from rocketsim.sensors import SensorPacket
from rocketsim.sim.schema import load_sim_config

ExecutableResolver = Callable[[str], str | None]
ModuleResolver = Callable[[str], bool]


class RenodeUnavailableError(RuntimeError):
    """Raised when Backend B is called before Renode HIL is ready."""


@dataclass(frozen=True)
class RenodeBlocker:
    """A concrete blocker preventing real firmware co-simulation."""

    code: str
    severity: str
    message: str
    resolution: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "resolution": self.resolution,
        }


@dataclass(frozen=True)
class RenodeComponentStatus:
    """Presence/verification state for one Renode HIL dependency."""

    id: str
    kind: str
    required: bool
    present: bool
    path: str
    verified: bool
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "required": self.required,
            "present": self.present,
            "path": self.path,
            "verified": self.verified,
            "message": self.message,
        }


@dataclass(frozen=True)
class RenodeHilReport:
    """Machine-readable Phase-12 Renode bring-up report."""

    ready: bool
    status: str
    generated_at_utc: str
    backend: str
    components: tuple[RenodeComponentStatus, ...]
    blockers: tuple[RenodeBlocker, ...]
    time_sync: dict[str, Any]
    io_channels: dict[str, Any]
    next_steps: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "status": self.status,
            "generated_at_utc": self.generated_at_utc,
            "backend": self.backend,
            "components": [component.as_dict() for component in self.components],
            "blockers": [blocker.as_dict() for blocker in self.blockers],
            "time_sync": self.time_sync,
            "io_channels": self.io_channels,
            "next_steps": list(self.next_steps),
        }


@dataclass(frozen=True)
class RenodeHilStatusResult:
    """Written status artifact paths for the Phase-12 gate."""

    report: RenodeHilReport
    output_dir: Path
    status_json: Path
    status_markdown: Path


class RenodeHILBackend(ControllerBackend):
    """Backend-B seam for real firmware co-simulation through Renode."""

    def __init__(self, repo_root: Path | str, control: ControlConfig) -> None:
        if control.data.backend != "renode":
            msg = "RenodeHILBackend requires control backend 'renode'"
            raise ValueError(msg)
        self.repo_root = Path(repo_root).resolve()
        self.control = control
        self._seed = 0
        self._report = build_renode_hil_report(self.repo_root)
        self._last_sensor_frame: dict[str, Any] | None = None
        self._last_valves = ValveCommands(tuple(False for _ in self.solenoid_lines))

    @classmethod
    def from_config_path(
        cls,
        repo_root: Path | str,
        control_config_path: Path | str = "config/control.yaml",
    ) -> RenodeHILBackend:
        root = Path(repo_root).resolve()
        return cls(root, load_control_config(root / control_config_path))

    @property
    def solenoid_lines(self) -> tuple[str, ...]:
        return self.control.data.renode.actuation.solenoid_lines

    @property
    def loop_period_s(self) -> float:
        return 1.0 / self.control.data.loop_rate_hz

    def reset(self, seed: int) -> None:
        self._seed = seed
        self._report = build_renode_hil_report(self.repo_root)
        self._last_sensor_frame = None
        self._last_valves = ValveCommands(tuple(False for _ in self.solenoid_lines))

    def step(self, sensor_packet: SensorPacket, t_s: float) -> ValveCommands:
        if t_s < 0.0:
            msg = "t_s must be non-negative"
            raise ValueError(msg)
        self._last_sensor_frame = sensor_packet_to_injection_frame(sensor_packet)
        if not self._report.ready:
            blocker_codes = ", ".join(blocker.code for blocker in self._report.blockers)
            msg = f"Renode HIL is not ready for firmware execution: {blocker_codes}"
            raise RenodeUnavailableError(msg)
        msg = (
            "Renode HIL preflight is ready, but this in-process backend requires the "
            "pyrenode3/External Control runtime to be attached before stepping firmware."
        )
        raise RenodeUnavailableError(msg)

    def telemetry(self) -> dict[str, Any]:
        return {
            "backend": "renode",
            "seed": self._seed,
            "ready": self._report.ready,
            "status": self._report.status,
            "blockers": [blocker.as_dict() for blocker in self._report.blockers],
            "last_sensor_frame": self._last_sensor_frame,
            "last_valves": self._last_valves.states,
        }

    def update_valves_from_gpio(self, line_levels: Sequence[bool]) -> ValveCommands:
        """Convert Renode GPIO/PWM line levels to plant valve commands."""

        self._last_valves = actuator_levels_to_valves(line_levels, len(self.solenoid_lines))
        return self._last_valves


def run_renode_hil_status(
    repo_root: Path | str,
    *,
    control_config_path: Path | str = "config/control.yaml",
    sim_config_path: Path | str = "config/sim.yaml",
    executable_resolver: ExecutableResolver = shutil.which,
    module_resolver: ModuleResolver | None = None,
) -> RenodeHilStatusResult:
    """Write the Phase-12 Renode HIL status bundle and return its paths."""

    root = Path(repo_root).resolve()
    report = build_renode_hil_report(
        root,
        control_config_path=control_config_path,
        sim_config_path=sim_config_path,
        executable_resolver=executable_resolver,
        module_resolver=module_resolver or _module_available,
    )
    control = load_control_config(root / control_config_path)
    output_dir = (root / control.data.renode.status_output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    status_json = output_dir / "renode_hil_status.json"
    status_markdown = output_dir / "renode_hil_status.md"
    status_json.write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    status_markdown.write_text(_status_markdown(report), encoding="utf-8")
    return RenodeHilStatusResult(
        report=report,
        output_dir=output_dir,
        status_json=status_json,
        status_markdown=status_markdown,
    )


def build_renode_hil_report(
    repo_root: Path | str,
    *,
    control_config_path: Path | str = "config/control.yaml",
    sim_config_path: Path | str = "config/sim.yaml",
    executable_resolver: ExecutableResolver = shutil.which,
    module_resolver: ModuleResolver | None = None,
    generated_at_utc: str | None = None,
) -> RenodeHilReport:
    """Inspect local Renode HIL readiness without pretending to run firmware."""

    root = Path(repo_root).resolve()
    control = load_control_config(root / control_config_path)
    sim = load_sim_config(root / sim_config_path)
    renode = control.data.renode
    resolve_module = module_resolver or _module_available
    generated = generated_at_utc or datetime.now(UTC).replace(microsecond=0).isoformat()
    components: list[RenodeComponentStatus] = []
    blockers: list[RenodeBlocker] = []

    renode_path = executable_resolver(renode.renode_executable)
    components.append(
        RenodeComponentStatus(
            id="renode_executable",
            kind="tool",
            required=True,
            present=renode_path is not None,
            path=renode_path or renode.renode_executable,
            verified=renode_path is not None,
            message="Renode executable used to run the two-machine co-sim.",
        )
    )
    if renode_path is None:
        blockers.append(
            RenodeBlocker(
                code="renode_executable_missing",
                severity="blocking",
                message=f"Renode executable {renode.renode_executable!r} was not found on PATH.",
                resolution="Install Renode, then rerun `make hil`.",
            )
        )

    module_present = resolve_module(renode.python_bridge_module)
    components.append(
        RenodeComponentStatus(
            id="python_bridge_module",
            kind="python_module",
            required=True,
            present=module_present,
            path=renode.python_bridge_module,
            verified=module_present,
            message="Python-side Renode External Control/pyrenode bridge.",
        )
    )
    if not module_present:
        blockers.append(
            RenodeBlocker(
                code="python_bridge_module_missing",
                severity="blocking",
                message=f"Python module {renode.python_bridge_module!r} is not importable.",
                resolution=(
                    "Install/configure the Renode Python control bridge used for "
                    "lockstep co-sim."
                ),
            )
        )

    _inspect_path_component(
        root,
        component_id="renode_script",
        kind="script",
        relative_path=renode.script_path,
        message="Renode script that creates ESP32 + Teensy machines and loads firmware.",
        blocker_code="renode_script_missing",
        blockers=blockers,
        components=components,
    )

    for machine in sorted(renode.machines, key=lambda item: item.name):
        _inspect_machine(root, machine, blockers, components)

    loop_period_s = 1.0 / control.data.loop_rate_hz
    quantum_s = sim.data.renode_sync_quantum_s
    if quantum_s > loop_period_s:
        blockers.append(
            RenodeBlocker(
                code="sync_quantum_exceeds_loop_period",
                severity="blocking",
                message="Renode sync quantum is larger than the configured controller loop period.",
                resolution=(
                    "Lower config/sim.yaml:data.renode_sync_quantum_s or the "
                    "controller rate."
                ),
            )
        )

    ready = not blockers
    return RenodeHilReport(
        ready=ready,
        status="ready" if ready else "blocked",
        generated_at_utc=generated,
        backend=control.data.backend,
        components=tuple(components),
        blockers=tuple(blockers),
        time_sync={
            "scheme": "advance Renode virtual time and fixed-step plant in equal quanta",
            "controller_loop_rate_hz": control.data.loop_rate_hz,
            "controller_loop_period_s": loop_period_s,
            "plant_integrator_dt_s": sim.data.integrator_dt_s,
            "renode_sync_quantum_s": quantum_s,
            "sync_timeout_s": renode.sync_timeout_s,
            "loop_overrun_margin_s": renode.loop_overrun_margin_s,
        },
        io_channels={
            "sensor_injection": renode.sensor_injection.model_dump(mode="json"),
            "actuation": renode.actuation.model_dump(mode="json"),
            "inter_mcu_link": renode.inter_mcu_link.model_dump(mode="json"),
        },
        next_steps=_next_steps(blockers),
    )


def read_latest_hil_status(repo_root: Path | str) -> dict[str, Any]:
    """Return the latest written HIL status, or a live preflight report if absent."""

    root = Path(repo_root).resolve()
    control = load_control_config(root / "config/control.yaml")
    status_json = root / control.data.renode.status_output_dir / "renode_hil_status.json"
    if status_json.exists():
        raw = json.loads(status_json.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    return build_renode_hil_report(root).as_dict()


def sensor_packet_to_injection_frame(packet: SensorPacket) -> dict[str, Any]:
    """Serialize a plant sensor packet into the Renode injection payload shape."""

    imu = packet.imu
    barometer = packet.barometer
    return {
        "time_s": packet.time_s,
        "imu": None
        if imu is None
        else {
            "accel_m_s2": _array_to_list(imu.accel_m_s2),
            "gyro_rad_s": _array_to_list(imu.gyro_rad_s),
            "truth_specific_force_body_m_s2": _array_to_list(
                imu.truth_specific_force_body_m_s2
            ),
            "truth_angular_velocity_rad_s": _array_to_list(
                imu.truth_angular_velocity_rad_s
            ),
        },
        "barometer": None
        if barometer is None
        else {
            "pressure_pa": barometer.pressure_pa,
            "altitude_m": barometer.altitude_m,
            "truth_pressure_pa": barometer.truth_pressure_pa,
            "truth_altitude_m": barometer.truth_altitude_m,
        },
        "tof_range_m": packet.tof_range_m,
        "pressure_transducer_pa": packet.pressure_transducer_pa,
    }


def actuator_levels_to_valves(line_levels: Sequence[bool], expected_count: int) -> ValveCommands:
    """Convert MCU output line states into bang-bang valve commands."""

    if len(line_levels) != expected_count:
        msg = f"expected {expected_count} actuator lines, got {len(line_levels)}"
        raise ValueError(msg)
    return ValveCommands(tuple(bool(level) for level in line_levels))


def _inspect_machine(
    root: Path,
    machine: RenodeMachineConfig,
    blockers: list[RenodeBlocker],
    components: list[RenodeComponentStatus],
) -> None:
    _inspect_path_component(
        root,
        component_id=f"{machine.name}_firmware_elf",
        kind="firmware",
        relative_path=machine.elf_path,
        message=f"Real, unmodified {machine.name} firmware ELF for Renode.",
        blocker_code=f"{machine.name}_firmware_elf_missing",
        blockers=blockers,
        components=components,
    )
    platform_path = (root / machine.platform_repl_path).resolve()
    platform_present = platform_path.exists()
    components.append(
        RenodeComponentStatus(
            id=f"{machine.name}_platform_repl",
            kind="platform",
            required=True,
            present=platform_present,
            path=machine.platform_repl_path,
            verified=platform_present and machine.platform_verified,
            message=(
                f"{machine.name} Renode platform description; "
                f"verified={machine.platform_verified}."
            ),
        )
    )
    if not platform_present:
        blockers.append(
            RenodeBlocker(
                code=f"{machine.name}_platform_repl_missing",
                severity="blocking",
                message=f"{machine.name} platform file {machine.platform_repl_path} is missing.",
                resolution=(
                    "Add a Renode .repl platform file with the required "
                    "timers/GPIO/sensor bus."
                ),
            )
        )
    elif not machine.platform_verified:
        blockers.append(
            RenodeBlocker(
                code=f"{machine.name}_platform_repl_unverified",
                severity="blocking",
                message=f"{machine.name} platform file exists but is marked unverified.",
                resolution="Replace the placeholder .repl with a verified board/peripheral model.",
            )
        )


def _inspect_path_component(
    root: Path,
    *,
    component_id: str,
    kind: str,
    relative_path: str,
    message: str,
    blocker_code: str,
    blockers: list[RenodeBlocker],
    components: list[RenodeComponentStatus],
) -> None:
    path = (root / relative_path).resolve()
    present = path.exists()
    components.append(
        RenodeComponentStatus(
            id=component_id,
            kind=kind,
            required=True,
            present=present,
            path=relative_path,
            verified=present,
            message=message,
        )
    )
    if not present:
        blockers.append(
            RenodeBlocker(
                code=blocker_code,
                severity="blocking",
                message=f"Required {kind} file {relative_path} is missing.",
                resolution=f"Create or provide {relative_path}, then rerun `make hil`.",
            )
        )


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _array_to_list(values: Sequence[float] | np.ndarray[Any, Any]) -> list[float]:
    return [float(item) for item in values]


def _status_markdown(report: RenodeHilReport) -> str:
    lines = [
        "# Renode HIL Status",
        "",
        f"- Status: `{report.status}`",
        f"- Ready: `{report.ready}`",
        f"- Generated UTC: `{report.generated_at_utc}`",
        "",
        "## Blockers",
    ]
    if report.blockers:
        for blocker in report.blockers:
            lines.append(f"- `{blocker.code}`: {blocker.message} Resolution: {blocker.resolution}")
    else:
        lines.append("- None")
    lines.extend(["", "## Components"])
    for component in report.components:
        lines.append(
            f"- `{component.id}` ({component.kind}): present={component.present}, "
            f"verified={component.verified}, path={component.path}"
        )
    lines.extend(["", "## Next Steps"])
    for step in report.next_steps:
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def _next_steps(blockers: Sequence[RenodeBlocker]) -> tuple[str, ...]:
    if not blockers:
        return (
            "Attach the pyrenode3/External Control runtime and execute one lockstep flight.",
            "Record loop timing and actuator GPIO/PWM transitions in the output bundle.",
        )
    grouped = {blocker.code for blocker in blockers}
    steps: list[str] = []
    if "renode_executable_missing" in grouped:
        steps.append("Install Renode and confirm the `renode` executable is on PATH.")
    if "python_bridge_module_missing" in grouped:
        steps.append("Install/configure the Python Renode control bridge module.")
    if any(code.endswith("_firmware_elf_missing") for code in grouped):
        steps.append("Add real ESP32 and Teensy firmware ELFs under `firmware/`.")
    if any(code.endswith("_platform_repl_unverified") for code in grouped):
        steps.append("Replace placeholder ESP32/Teensy .repl files with verified board models.")
    if any(code.endswith("_platform_repl_missing") for code in grouped):
        steps.append("Add missing Renode platform .repl files.")
    if "renode_script_missing" in grouped:
        steps.append("Add the dual-machine Renode .resc script.")
    if "sync_quantum_exceeds_loop_period" in grouped:
        steps.append("Adjust Renode sync quantum so it is no larger than the controller period.")
    return tuple(steps)
