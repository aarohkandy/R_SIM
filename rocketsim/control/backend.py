"""Stable controller backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from rocketsim.actuation import ValveCommands
from rocketsim.sensors import SensorPacket


class ControllerBackend(ABC):
    """Swappable plant/controller seam used by SIL and future Renode HIL."""

    @abstractmethod
    def reset(self, seed: int) -> None:
        """Reset backend state deterministically."""

    @abstractmethod
    def step(self, sensor_packet: SensorPacket, t_s: float) -> ValveCommands:
        """Advance the controller at its configured rate."""

    @abstractmethod
    def telemetry(self) -> dict[str, Any]:
        """Return backend-internal telemetry for logging."""
