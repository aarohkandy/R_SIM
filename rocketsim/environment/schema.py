"""Environment configuration schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

Vector3 = tuple[float, float, float]


class ISAParameters(BaseModel):
    """Configurable parameters for the International Standard Atmosphere model."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["ISA"]
    sea_level_temperature_k: float = Field(gt=0.0)
    sea_level_pressure_pa: float = Field(gt=0.0)
    sea_level_density_kg_m3: float = Field(gt=0.0)
    lapse_rate_k_per_m: float
    tropopause_altitude_m: float = Field(gt=0.0)
    gravity_m_s2: float = Field(gt=0.0)
    gas_constant_air_j_kg_k: float = Field(gt=0.0)
    heat_capacity_ratio: float = Field(gt=1.0)


class GustDefinition(BaseModel):
    """A deterministic 1-cosine gust."""

    model_config = ConfigDict(extra="forbid")

    start_s: float = Field(ge=0.0)
    duration_s: float = Field(gt=0.0)
    amplitude_m_s: Vector3

    @model_validator(mode="after")
    def amplitude_must_be_nonzero(self) -> GustDefinition:
        if self.amplitude_m_s == (0.0, 0.0, 0.0):
            msg = "gust amplitude must be non-zero"
            raise ValueError(msg)
        return self


class WindDefinition(BaseModel):
    """Steady wind, altitude shear, and deterministic gusts."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    steady_m_s: Vector3
    shear_reference_altitude_m: float = Field(gt=0.0)
    shear_exponent: float = Field(ge=0.0)
    gusts: tuple[GustDefinition, ...] = ()


class LaunchRailDefinition(BaseModel):
    """Launch rail geometry and exit-speed requirement."""

    model_config = ConfigDict(extra="forbid")

    length_m: float = Field(gt=0.0)
    angle_from_vertical_deg: float = Field(ge=-90.0, le=90.0)
    minimum_exit_speed_mps: float = Field(gt=0.0)


class EnvironmentData(BaseModel):
    """Validated environment payload under config/environment.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    atmosphere: ISAParameters
    wind: WindDefinition
    launch_rail: LaunchRailDefinition


class EnvironmentDefinition(BaseModel):
    """Versioned environment document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: EnvironmentData
