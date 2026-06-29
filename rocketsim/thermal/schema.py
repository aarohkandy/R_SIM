"""Strict thermal-network configuration schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator


class ThermalNodeConfig(BaseModel):
    """One lumped thermal node."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    material: str = Field(min_length=1)
    thermal_mass_j_per_k: float = Field(gt=0.0)
    initial_temperature_deg_c: float
    convection_area_m2: float = Field(ge=0.0)
    convection_h_base_w_m2_k: float = Field(ge=0.0)
    convection_h_per_m_s_w_m2_k: float = Field(ge=0.0)

    @field_validator("id")
    @classmethod
    def id_must_be_slug(cls, value: str) -> str:
        if not value.replace("_", "-").replace("-", "").isalnum():
            msg = "node id must contain only letters, numbers, underscores, or hyphens"
            raise ValueError(msg)
        return value


class ConductiveLinkConfig(BaseModel):
    """Conductive thermal conductance between two nodes."""

    model_config = ConfigDict(extra="forbid")

    from_node: str = Field(min_length=1)
    to_node: str = Field(min_length=1)
    conductance_w_per_k: float = Field(gt=0.0)


class RadiativeLinkConfig(BaseModel):
    """Radiative exchange from a source node to a target node."""

    model_config = ConfigDict(extra="forbid")

    from_node: str = Field(min_length=1)
    to_node: str = Field(min_length=1)
    area_m2: float = Field(gt=0.0)
    emissivity: float = Field(ge=0.0, le=1.0)
    view_factor: float = Field(ge=0.0, le=1.0)


class HeatSourceConfig(BaseModel):
    """Configured thermal input applied to a node."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    node: str = Field(min_length=1)
    kind: Literal["motor_thrust_scaled", "constant", "valve_power"]
    power_w: float = Field(ge=0.0)
    start_time_s: float = Field(ge=0.0)
    end_time_s: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def end_must_follow_start(self) -> HeatSourceConfig:
        if self.end_time_s is not None and self.end_time_s < self.start_time_s:
            msg = "heat source end_time_s must be greater than or equal to start_time_s"
            raise ValueError(msg)
        return self


class ThermalData(BaseModel):
    """Validated payload under config/thermal.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    ambient_temperature_deg_c: float
    material_limits_path: str = Field(min_length=1)
    max_step_s: float = Field(gt=0.0)
    nodes: tuple[ThermalNodeConfig, ...] = Field(min_length=1)
    conductive_links: tuple[ConductiveLinkConfig, ...] = Field(default_factory=tuple)
    radiative_links: tuple[RadiativeLinkConfig, ...] = Field(default_factory=tuple)
    heat_sources: tuple[HeatSourceConfig, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def references_must_exist(self) -> ThermalData:
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            msg = "thermal node ids must be unique"
            raise ValueError(msg)
        node_set = set(node_ids)
        for conductive_link in self.conductive_links:
            if (
                conductive_link.from_node not in node_set
                or conductive_link.to_node not in node_set
            ):
                msg = "thermal links must reference configured nodes"
                raise ValueError(msg)
            if conductive_link.from_node == conductive_link.to_node:
                msg = "thermal links must connect distinct nodes"
                raise ValueError(msg)
        for radiative_link in self.radiative_links:
            if radiative_link.from_node not in node_set or radiative_link.to_node not in node_set:
                msg = "thermal links must reference configured nodes"
                raise ValueError(msg)
            if radiative_link.from_node == radiative_link.to_node:
                msg = "thermal links must connect distinct nodes"
                raise ValueError(msg)
        for source in self.heat_sources:
            if source.node not in node_set:
                msg = "heat sources must reference configured nodes"
                raise ValueError(msg)
        return self


class ThermalConfig(BaseModel):
    """Versioned thermal-network config document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: ThermalData


class MaterialLimit(BaseModel):
    """A material temperature limit used for margin reporting."""

    model_config = ConfigDict(extra="forbid")

    heat_deflection_temperature_deg_c: float


class MaterialLimitsDocument(BaseModel):
    """Versioned material limit document from inputs/."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    materials: dict[str, MaterialLimit] = Field(min_length=1)


def load_thermal_config(path: Path | str) -> ThermalConfig:
    """Load config/thermal.yaml into a strict thermal definition."""

    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{config_path} must contain a YAML mapping"
        raise TypeError(msg)
    return ThermalConfig.model_validate(raw)


def load_material_limits(path: Path | str) -> MaterialLimitsDocument:
    """Load a material-limit YAML document."""

    limits_path = Path(path)
    raw = yaml.safe_load(limits_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{limits_path} must contain a YAML mapping"
        raise TypeError(msg)
    return MaterialLimitsDocument.model_validate(raw)
