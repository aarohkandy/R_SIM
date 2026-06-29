"""Native software-in-the-loop controller backend."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from rocketsim.actuation import (
    ControlAllocator,
    ControlDemand,
    SolenoidValveBank,
    ValveCommands,
    load_actuation_config,
)
from rocketsim.control.backend import ControllerBackend
from rocketsim.control.schema import ControlConfig, load_control_config
from rocketsim.propulsion import ColdGasSystem
from rocketsim.randomness import make_rng
from rocketsim.sensors import SensorPacket


@dataclass(frozen=True)
class PendingCommand:
    """Controller command waiting for modeled latency release."""

    release_time_s: float
    commands: ValveCommands


class NativeSILBackend(ControllerBackend):
    """Baseline cascaded PD controller for fast plant validation."""

    def __init__(
        self,
        control: ControlConfig,
        allocator: ControlAllocator,
        valve_bank: SolenoidValveBank,
    ) -> None:
        if control.data.backend != "sil":
            msg = "NativeSILBackend requires control backend 'sil'"
            raise ValueError(msg)
        self.control = control
        self.allocator = allocator
        self.valve_bank = valve_bank
        self._rng = make_rng(0, "control.sil")
        self._pending: list[PendingCommand] = []
        self._active_desired = ValveCommands(tuple(False for _ in range(self.valve_count)))
        self._previous_altitude_m: float | None = None
        self._previous_time_s: float | None = None
        self._telemetry: dict[str, Any] = {}

    @classmethod
    def from_config_paths(
        cls,
        control_config_path: Path | str,
        actuation_config_path: Path | str,
        coldgas_config_path: Path | str,
    ) -> NativeSILBackend:
        coldgas = ColdGasSystem.from_config_path(coldgas_config_path)
        actuation = load_actuation_config(actuation_config_path)
        return cls(
            control=load_control_config(control_config_path),
            allocator=ControlAllocator(actuation, coldgas),
            valve_bank=SolenoidValveBank(actuation),
        )

    @property
    def valve_count(self) -> int:
        return self.allocator.actuation.data.valve_count

    @property
    def loop_period_s(self) -> float:
        return 1.0 / self.control.data.loop_rate_hz

    def reset(self, seed: int) -> None:
        self._rng = make_rng(seed, "control.sil")
        self._pending = []
        self._active_desired = ValveCommands(tuple(False for _ in range(self.valve_count)))
        self._previous_altitude_m = None
        self._previous_time_s = None
        self._telemetry = {}
        self.allocator.reset()
        self.valve_bank.reset()

    def step(self, sensor_packet: SensorPacket, t_s: float) -> ValveCommands:
        if t_s < 0.0:
            msg = "t_s must be non-negative"
            raise ValueError(msg)
        self._release_pending(t_s)
        desired = self._compute_desired(sensor_packet, t_s)
        release_time = t_s + self.control.data.latency_s + self._latency_jitter_s()
        self._pending.append(PendingCommand(release_time_s=release_time, commands=desired))
        actual = self.valve_bank.update(self._active_desired, t_s)
        self._telemetry["actual_valves"] = actual.states
        self._telemetry["pending_count"] = len(self._pending)
        return actual

    def telemetry(self) -> dict[str, Any]:
        return dict(self._telemetry)

    def _compute_desired(self, sensor_packet: SensorPacket, t_s: float) -> ValveCommands:
        altitude = _packet_altitude(sensor_packet)
        vertical_rate = self._estimate_vertical_rate(altitude, t_s)
        sil = self.control.data.sil
        if t_s < sil.control_start_time_s or altitude > sil.landing_burn_altitude_m:
            demand = ControlDemand(collective=0.0, torque_x=0.0, torque_y=0.0)
        else:
            descent_error = max(0.0, sil.target_descent_rate_m_s - vertical_rate)
            altitude_fraction = max(0.0, 1.0 - altitude / sil.landing_burn_altitude_m)
            collective = np.clip(
                sil.descent_rate_kp * descent_error + sil.altitude_kp * altitude_fraction,
                0.0,
                sil.max_collective_duty,
            )
            torque_x, torque_y = self._attitude_torque_terms(sensor_packet)
            demand = ControlDemand(
                collective=float(collective),
                torque_x=float(np.clip(torque_x, -sil.max_torque_duty, sil.max_torque_duty)),
                torque_y=float(np.clip(torque_y, -sil.max_torque_duty, sil.max_torque_duty)),
            )
        allocation = self.allocator.allocate(demand)
        self._telemetry.update(
            {
                "altitude_m": altitude,
                "estimated_vertical_rate_m_s": vertical_rate,
                "collective_duty": demand.collective,
                "torque_x_duty": demand.torque_x,
                "torque_y_duty": demand.torque_y,
                "duty_fractions": allocation.duty_fractions,
                "raw_valves": allocation.raw_commands.states,
                "sigma_state": allocation.sigma_state,
            }
        )
        return allocation.raw_commands

    def _estimate_vertical_rate(self, altitude_m: float, t_s: float) -> float:
        if self._previous_altitude_m is None or self._previous_time_s is None:
            rate = 0.0
        else:
            dt = t_s - self._previous_time_s
            rate = 0.0 if dt <= 0.0 else (altitude_m - self._previous_altitude_m) / dt
        self._previous_altitude_m = altitude_m
        self._previous_time_s = t_s
        return rate

    def _attitude_torque_terms(self, sensor_packet: SensorPacket) -> tuple[float, float]:
        imu = sensor_packet.imu
        if imu is None:
            return (0.0, 0.0)
        sil = self.control.data.sil
        accel = imu.accel_m_s2
        gyro = imu.gyro_rad_s
        torque_x = -sil.attitude_accel_kp * float(accel[1]) - sil.angular_rate_kd * float(gyro[0])
        torque_y = sil.attitude_accel_kp * float(accel[0]) - sil.angular_rate_kd * float(gyro[1])
        return (torque_x, torque_y)

    def _latency_jitter_s(self) -> float:
        if self.control.data.jitter_s <= 0.0:
            return 0.0
        return float(self._rng.normal(0.0, self.control.data.jitter_s))

    def _release_pending(self, t_s: float) -> None:
        ready: list[PendingCommand] = []
        pending: list[PendingCommand] = []
        for command in self._pending:
            if t_s + 1.0e-12 >= command.release_time_s:
                ready.append(command)
            else:
                pending.append(command)
        if ready:
            ready.sort(key=lambda item: item.release_time_s)
            self._active_desired = ready[-1].commands
        self._pending = pending


def _packet_altitude(packet: SensorPacket) -> float:
    if packet.barometer is not None:
        return packet.barometer.altitude_m
    if packet.imu is not None:
        return 0.0
    return 0.0


def valve_timeline_durations(
    times_s: Sequence[float],
    valve_states: Sequence[tuple[bool, ...]],
) -> list[float]:
    """Return open-pulse durations for regression tests."""

    durations: list[float] = []
    open_start: dict[int, float] = {}
    for t_s, states in zip(times_s, valve_states, strict=True):
        for index, is_open in enumerate(states):
            if is_open and index not in open_start:
                open_start[index] = t_s
            if not is_open and index in open_start:
                durations.append(t_s - open_start.pop(index))
    if times_s:
        final_time = times_s[-1]
        durations.extend(final_time - opened_at for opened_at in open_start.values())
    return durations
