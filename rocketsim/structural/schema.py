"""Strict structural-analysis configuration schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

Vector3 = tuple[float, float, float]
LoadCaseName = Literal["landing_impact", "thrust_transient", "max_q", "leg_deploy"]


class ExternalSolverConfig(BaseModel):
    """External FEA solver command configuration."""

    model_config = ConfigDict(extra="forbid")

    calculix_executable: str = Field(min_length=1)
    gmsh_executable: str = Field(min_length=1)
    allow_internal_fallback: bool


class StructuralLoadCaseConfig(BaseModel):
    """Rules for extracting event-triggered load cases from telemetry."""

    model_config = ConfigDict(extra="forbid")

    enabled: tuple[LoadCaseName, ...] = Field(min_length=1)
    application_node: str = Field(min_length=1)
    gravity_m_s2: float = Field(gt=0.0)
    landing_stop_distance_m: float = Field(gt=0.0)
    thrust_axis_unit: Vector3
    max_q_reference_area_m2: float = Field(gt=0.0)
    max_q_lateral_coefficient: float = Field(gt=0.0)
    leg_deploy_time_s: float = Field(ge=0.0)
    leg_deploy_shock_force_n: float = Field(ge=0.0)

    @field_validator("thrust_axis_unit")
    @classmethod
    def thrust_axis_must_be_nonzero(cls, value: Vector3) -> Vector3:
        if np.linalg.norm(np.asarray(value, dtype=np.float64)) <= 0.0:
            msg = "thrust_axis_unit must be non-zero"
            raise ValueError(msg)
        return value


class MeshConvergenceConfig(BaseModel):
    """Internal FEA mesh-convergence refinement settings."""

    model_config = ConfigDict(extra="forbid")

    element_subdivisions: tuple[PositiveInt, ...] = Field(min_length=1)

    @field_validator("element_subdivisions")
    @classmethod
    def subdivisions_must_be_unique_and_sorted(
        cls,
        value: tuple[PositiveInt, ...],
    ) -> tuple[PositiveInt, ...]:
        if tuple(sorted(set(value))) != tuple(value):
            msg = "element_subdivisions must be unique and sorted"
            raise ValueError(msg)
        return value


class StructuralMaterialConfig(BaseModel):
    """Linear-elastic material properties for event-triggered FEA."""

    model_config = ConfigDict(extra="forbid")

    young_modulus_pa: float = Field(gt=0.0)
    allowable_stress_pa: float = Field(gt=0.0)
    density_kg_m3: float = Field(gt=0.0)


class StructuralNodeConfig(BaseModel):
    """One structural mesh node."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    position_m: Vector3
    fixed: bool

    @field_validator("id")
    @classmethod
    def id_must_be_slug(cls, value: str) -> str:
        if not value.replace("_", "-").replace("-", "").isalnum():
            msg = "node id must contain only letters, numbers, underscores, or hyphens"
            raise ValueError(msg)
        return value


class StructuralMemberConfig(BaseModel):
    """One axial truss/beam-equivalent member."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    from_node: str = Field(min_length=1)
    to_node: str = Field(min_length=1)
    material: str = Field(min_length=1)
    area_m2: float = Field(gt=0.0)


class StructuralData(BaseModel):
    """Validated payload under config/structural.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    solver_preference: Literal["calculix", "fenics", "internal_truss"]
    external_solver: ExternalSolverConfig
    load_cases: StructuralLoadCaseConfig
    mesh_convergence: MeshConvergenceConfig
    materials: dict[str, StructuralMaterialConfig] = Field(min_length=1)
    nodes: tuple[StructuralNodeConfig, ...] = Field(min_length=2)
    members: tuple[StructuralMemberConfig, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def references_must_exist(self) -> StructuralData:
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            msg = "structural node ids must be unique"
            raise ValueError(msg)
        member_ids = [member.id for member in self.members]
        if len(member_ids) != len(set(member_ids)):
            msg = "structural member ids must be unique"
            raise ValueError(msg)
        node_set = set(node_ids)
        material_set = set(self.materials)
        if self.load_cases.application_node not in node_set:
            msg = "load-case application_node must reference a configured node"
            raise ValueError(msg)
        if not any(node.fixed for node in self.nodes):
            msg = "structural model must include at least one fixed node"
            raise ValueError(msg)
        for member in self.members:
            if member.from_node not in node_set or member.to_node not in node_set:
                msg = "structural members must reference configured nodes"
                raise ValueError(msg)
            if member.from_node == member.to_node:
                msg = "structural members must connect distinct nodes"
                raise ValueError(msg)
            if member.material not in material_set:
                msg = "structural members must reference configured materials"
                raise ValueError(msg)
        return self


class StructuralConfig(BaseModel):
    """Versioned structural-analysis config document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: StructuralData


def load_structural_config(path: Path | str) -> StructuralConfig:
    """Load config/structural.yaml into a strict structural-analysis definition."""

    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{config_path} must contain a YAML mapping"
        raise TypeError(msg)
    return StructuralConfig.model_validate(raw)
