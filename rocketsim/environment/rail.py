"""Launch rail constraint helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from rocketsim.environment.schema import LaunchRailDefinition


@dataclass(frozen=True)
class RailExitReport:
    """Rail-exit speed and configured stability threshold."""

    exit_speed_mps: float
    minimum_exit_speed_mps: float
    is_sane: bool


class LaunchRail:
    """Straight launch rail in the inertial x-z plane."""

    def __init__(self, definition: LaunchRailDefinition) -> None:
        self.definition = definition

    @property
    def direction_m(self) -> NDArray[np.float64]:
        angle = math.radians(self.definition.angle_from_vertical_deg)
        return np.asarray((math.sin(angle), 0.0, math.cos(angle)), dtype=np.float64)

    def is_constrained(self, distance_along_rail_m: float) -> bool:
        return distance_along_rail_m < self.definition.length_m

    def position_at_distance(self, distance_along_rail_m: float) -> NDArray[np.float64]:
        distance = min(max(distance_along_rail_m, 0.0), self.definition.length_m)
        return self.direction_m * distance

    def exit_report(self, exit_speed_mps: float) -> RailExitReport:
        return RailExitReport(
            exit_speed_mps=exit_speed_mps,
            minimum_exit_speed_mps=self.definition.minimum_exit_speed_mps,
            is_sane=exit_speed_mps >= self.definition.minimum_exit_speed_mps,
        )
