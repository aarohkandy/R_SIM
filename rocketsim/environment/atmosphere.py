"""ISA atmosphere model."""

from __future__ import annotations

import math
from dataclasses import dataclass

from rocketsim.environment.schema import ISAParameters


@dataclass(frozen=True)
class AtmosphereState:
    """Atmospheric conditions at an altitude."""

    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    speed_of_sound_m_s: float


class ISAAtmosphere:
    """International Standard Atmosphere through the lower stratosphere."""

    def __init__(self, parameters: ISAParameters) -> None:
        self.parameters = parameters

    def state_at(self, altitude_m: float) -> AtmosphereState:
        """Return ISA state for geometric altitude in meters."""

        p = self.parameters
        altitude = max(0.0, altitude_m)
        if altitude <= p.tropopause_altitude_m:
            temperature = p.sea_level_temperature_k + p.lapse_rate_k_per_m * altitude
            pressure = p.sea_level_pressure_pa * (
                temperature / p.sea_level_temperature_k
            ) ** (-p.gravity_m_s2 / (p.lapse_rate_k_per_m * p.gas_constant_air_j_kg_k))
        else:
            tropopause_temperature = (
                p.sea_level_temperature_k + p.lapse_rate_k_per_m * p.tropopause_altitude_m
            )
            tropopause_pressure = p.sea_level_pressure_pa * (
                tropopause_temperature / p.sea_level_temperature_k
            ) ** (-p.gravity_m_s2 / (p.lapse_rate_k_per_m * p.gas_constant_air_j_kg_k))
            temperature = tropopause_temperature
            pressure = tropopause_pressure * math.exp(
                -p.gravity_m_s2
                * (altitude - p.tropopause_altitude_m)
                / (p.gas_constant_air_j_kg_k * temperature)
            )
        density = pressure / (p.gas_constant_air_j_kg_k * temperature)
        speed_of_sound = math.sqrt(p.heat_capacity_ratio * p.gas_constant_air_j_kg_k * temperature)
        return AtmosphereState(
            altitude_m=altitude_m,
            temperature_k=temperature,
            pressure_pa=pressure,
            density_kg_m3=density,
            speed_of_sound_m_s=speed_of_sound,
        )
