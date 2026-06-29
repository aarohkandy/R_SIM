"""Bang-bang valve actuation and control allocation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from rocketsim.actuation.schema import ActuationConfig
from rocketsim.propulsion import ColdGasSystem

VectorArray = NDArray[np.float64]


@dataclass(frozen=True)
class ControlDemand:
    """Normalized collective thrust and body torque demand."""

    collective: float
    torque_x: float
    torque_y: float


@dataclass(frozen=True)
class ValveCommands:
    """Bang-bang command packet for all valves."""

    states: tuple[bool, ...]

    def __post_init__(self) -> None:
        if not self.states:
            msg = "ValveCommands requires at least one valve"
            raise ValueError(msg)


@dataclass(frozen=True)
class AllocationResult:
    """Continuous and bang-bang allocation output."""

    demand: ControlDemand
    duty_fractions: tuple[float, ...]
    raw_commands: ValveCommands
    sigma_state: tuple[float, ...]


class ControlAllocator:
    """Map collective + two torque axes onto three fixed axial nozzles."""

    def __init__(self, actuation: ActuationConfig, coldgas: ColdGasSystem) -> None:
        self.actuation = actuation
        self.coldgas = coldgas
        self._matrix = allocation_matrix(coldgas)
        if self._matrix.shape[1] != actuation.data.valve_count:
            msg = "actuation valve_count must match cold-gas nozzle count"
            raise ValueError(msg)
        self._sigma = np.zeros(actuation.data.valve_count, dtype=np.float64)

    @property
    def sigma_state(self) -> tuple[float, ...]:
        return tuple(float(item) for item in self._sigma)

    def reset(self) -> None:
        self._sigma = np.zeros(self.actuation.data.valve_count, dtype=np.float64)

    def allocate(self, demand: ControlDemand) -> AllocationResult:
        """Return sigma-delta bang-bang commands for the requested demand."""

        scaled = np.asarray(
            [
                self.actuation.data.allocation.collective_gain * demand.collective,
                self.actuation.data.allocation.torque_gain * demand.torque_x,
                self.actuation.data.allocation.torque_gain * demand.torque_y,
            ],
            dtype=np.float64,
        )
        duty, *_ = np.linalg.lstsq(self._matrix, scaled, rcond=None)
        duty = np.clip(duty, 0.0, 1.0)
        self._sigma = self._sigma + duty
        raw = self._sigma >= 1.0
        self._sigma = np.where(raw, self._sigma - 1.0, self._sigma)
        if demand.collective >= 1.0:
            raw = np.ones_like(raw, dtype=np.bool_)
        commands = ValveCommands(tuple(bool(item) for item in raw))
        return AllocationResult(
            demand=demand,
            duty_fractions=tuple(float(item) for item in duty),
            raw_commands=commands,
            sigma_state=self.sigma_state,
        )


class SolenoidValveBank:
    """Finite-latency solenoid bank with a minimum reliable pulse floor."""

    def __init__(self, config: ActuationConfig) -> None:
        self.config = config
        self._actual = [False] * config.data.valve_count
        self._desired = [False] * config.data.valve_count
        self._pending_target: list[bool | None] = [None] * config.data.valve_count
        self._pending_time_s = [0.0] * config.data.valve_count
        self._opened_until_s = [0.0] * config.data.valve_count

    def reset(self) -> None:
        self._actual = [False] * self.config.data.valve_count
        self._desired = [False] * self.config.data.valve_count
        self._pending_target = [None] * self.config.data.valve_count
        self._pending_time_s = [0.0] * self.config.data.valve_count
        self._opened_until_s = [0.0] * self.config.data.valve_count

    @property
    def actual(self) -> ValveCommands:
        return ValveCommands(tuple(self._actual))

    def update(self, desired: ValveCommands, t_s: float) -> ValveCommands:
        """Advance valve states to ``t_s`` and return actual open/closed states."""

        if len(desired.states) != self.config.data.valve_count:
            msg = "desired valve count must match config"
            raise ValueError(msg)
        if t_s < 0.0:
            msg = "t_s must be non-negative"
            raise ValueError(msg)

        for index, wanted in enumerate(desired.states):
            if t_s < self._opened_until_s[index] and not wanted:
                wanted = True
            if wanted != self._desired[index]:
                self._desired[index] = wanted
                latency = (
                    self.config.data.open_latency_s if wanted else self.config.data.close_latency_s
                )
                self._pending_target[index] = wanted
                self._pending_time_s[index] = t_s + latency

            pending = self._pending_target[index]
            if pending is not None and t_s + 1.0e-12 >= self._pending_time_s[index]:
                self._actual[index] = pending
                self._pending_target[index] = None
                if pending:
                    self._opened_until_s[index] = t_s + self.config.data.min_reliable_pulse_s

        if self.config.data.fault_injection.enabled:
            for index in self.config.data.fault_injection.stuck_open:
                self._actual[index] = True
            for index in self.config.data.fault_injection.stuck_closed:
                self._actual[index] = False
        return self.actual


def allocation_matrix(coldgas: ColdGasSystem) -> VectorArray:
    """Build the [collective, pitch, yaw] contribution matrix per unit nozzle thrust."""

    columns: list[VectorArray] = []
    for nozzle in coldgas.config.data.nozzles.items:
        position = np.asarray(nozzle.position_m, dtype=np.float64)
        axis = nozzle.unit_axis_array
        torque = np.cross(position, axis)
        collective = max(0.0, float(axis[2]))
        columns.append(np.asarray([collective, torque[0], torque[1]], dtype=np.float64))
    return np.column_stack(columns)
