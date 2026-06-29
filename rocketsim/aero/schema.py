"""Aerodynamic configuration schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class AeroGeometry(BaseModel):
    """Editable geometry used by the component build-up model."""

    model_config = ConfigDict(extra="forbid")

    body_diameter_m: float = Field(gt=0.0)
    body_length_m: float = Field(gt=0.0)
    body_cp_axial_m: float
    leg_count: int = Field(gt=0)
    leg_reference_area_m2: float = Field(gt=0.0)
    leg_cp_axial_m: float


class AeroCoefficients(BaseModel):
    """Editable empirical coefficients for the build-up model."""

    model_config = ConfigDict(extra="forbid")

    body_normal_force_slope_per_rad: float = Field(gt=0.0)
    leg_normal_force_slope_per_rad_each: float = Field(ge=0.0)
    skin_friction_coefficient: float = Field(ge=0.0)
    pressure_drag_coefficient: float = Field(ge=0.0)
    base_drag_coefficient: float = Field(ge=0.0)
    leg_drag_coefficient: float = Field(ge=0.0)
    mach_drag_rise_factor: float = Field(ge=0.0)
    depletion_drag_gain: float = Field(ge=0.0)


class AeroComparisonConfig(BaseModel):
    """OpenRocket anchor comparison settings."""

    model_config = ConfigDict(extra="forbid")

    openrocket_anchor_dir: str = Field(min_length=1)
    cp_tolerance_m: float = Field(gt=0.0)
    cd_tolerance: float = Field(gt=0.0)


class AeroData(BaseModel):
    """Validated payload under config/aero.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    geometry: AeroGeometry
    coefficients: AeroCoefficients
    comparison: AeroComparisonConfig
    notes: str = Field(min_length=1)


class AeroDefinition(BaseModel):
    """Versioned aero document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: AeroData
