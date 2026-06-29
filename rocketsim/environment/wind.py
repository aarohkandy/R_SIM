"""Deterministic wind model."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from rocketsim.environment.schema import GustDefinition, WindDefinition


@dataclass(frozen=True)
class WindState:
    """Wind vector in inertial coordinates."""

    velocity_m_s: NDArray[np.float64]


class WindModel:
    """Steady wind with altitude shear and deterministic 1-cosine gusts."""

    def __init__(self, definition: WindDefinition) -> None:
        self.definition = definition

    def velocity_at(self, altitude_m: float, t_s: float) -> NDArray[np.float64]:
        if not self.definition.enabled:
            return np.zeros(3, dtype=np.float64)
        altitude = max(0.0, altitude_m)
        steady = np.asarray(self.definition.steady_m_s, dtype=np.float64)
        shear_scale = (altitude / self.definition.shear_reference_altitude_m) ** (
            self.definition.shear_exponent
        )
        velocity = steady * shear_scale
        for gust in self.definition.gusts:
            velocity = velocity + gust_velocity(gust, t_s)
        return np.asarray(velocity, dtype=np.float64)


def gust_velocity(gust: GustDefinition, t_s: float) -> NDArray[np.float64]:
    """Return deterministic 1-cosine gust contribution at time."""

    elapsed = t_s - gust.start_s
    if elapsed <= 0.0 or elapsed >= gust.duration_s:
        return np.zeros(3, dtype=np.float64)
    scale = 0.5 * (1.0 - math.cos(2.0 * math.pi * elapsed / gust.duration_s))
    return np.asarray(gust.amplitude_m_s, dtype=np.float64) * scale
