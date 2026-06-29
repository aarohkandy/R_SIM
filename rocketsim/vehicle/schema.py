"""Vehicle definition schemas for mass properties."""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

Vector3 = tuple[float, float, float]
Matrix3 = tuple[Vector3, Vector3, Vector3]
StateTag = Literal["fixed", "propellant", "CO2", "deployable-leg"]

ZERO_INERTIA: Matrix3 = (
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
)


def _interpolate_scalar(
    left_t: float,
    left_v: float,
    right_t: float,
    right_v: float,
    t_s: float,
) -> float:
    if right_t == left_t:
        return right_v
    fraction = (t_s - left_t) / (right_t - left_t)
    return left_v + fraction * (right_v - left_v)


def _interpolate_vector(
    left_t: float,
    left_v: Vector3,
    right_t: float,
    right_v: Vector3,
    t_s: float,
) -> Vector3:
    return (
        _interpolate_scalar(left_t, left_v[0], right_t, right_v[0], t_s),
        _interpolate_scalar(left_t, left_v[1], right_t, right_v[1], t_s),
        _interpolate_scalar(left_t, left_v[2], right_t, right_v[2], t_s),
    )


def _norm(vector: Vector3) -> float:
    return math.sqrt(sum(component * component for component in vector))


def _unit(vector: Vector3) -> Vector3:
    norm = _norm(vector)
    if norm <= 0.0:
        msg = "unit vector inputs must be non-zero"
        raise ValueError(msg)
    return (vector[0] / norm, vector[1] / norm, vector[2] / norm)


class DepletionPoint(BaseModel):
    """Remaining mass fraction at a time."""

    model_config = ConfigDict(extra="forbid")

    time_s: float = Field(ge=0.0)
    remaining_fraction: float = Field(ge=0.0, le=1.0)


class DepletionProfile(BaseModel):
    """Piecewise-linear, monotonic depletion schedule."""

    model_config = ConfigDict(extra="forbid")

    points: tuple[DepletionPoint, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_profile(self) -> DepletionProfile:
        previous_time = self.points[0].time_s
        previous_fraction = self.points[0].remaining_fraction
        for point in self.points[1:]:
            if point.time_s <= previous_time:
                msg = "depletion profile times must be strictly increasing"
                raise ValueError(msg)
            if point.remaining_fraction > previous_fraction:
                msg = "remaining fractions must be monotonically non-increasing"
                raise ValueError(msg)
            previous_time = point.time_s
            previous_fraction = point.remaining_fraction
        return self

    def remaining_fraction_at(self, t_s: float) -> float:
        """Return the clamped remaining mass fraction at time."""

        if t_s <= self.points[0].time_s:
            return self.points[0].remaining_fraction
        if t_s >= self.points[-1].time_s:
            return self.points[-1].remaining_fraction
        for left, right in zip(self.points, self.points[1:], strict=True):
            if left.time_s <= t_s <= right.time_s:
                return _interpolate_scalar(
                    left.time_s,
                    left.remaining_fraction,
                    right.time_s,
                    right.remaining_fraction,
                    t_s,
                )
        raise AssertionError("profile interpolation should have returned")


class PositionPoint(BaseModel):
    """Part center of mass at a time."""

    model_config = ConfigDict(extra="forbid")

    time_s: float = Field(ge=0.0)
    position_m: Vector3


class PositionProfile(BaseModel):
    """Piecewise-linear center-of-mass path."""

    model_config = ConfigDict(extra="forbid")

    points: tuple[PositionPoint, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_profile(self) -> PositionProfile:
        previous_time = self.points[0].time_s
        for point in self.points[1:]:
            if point.time_s <= previous_time:
                msg = "position profile times must be strictly increasing"
                raise ValueError(msg)
            previous_time = point.time_s
        return self

    def position_at(self, t_s: float) -> Vector3:
        """Return the clamped part center of mass at time."""

        if t_s <= self.points[0].time_s:
            return self.points[0].position_m
        if t_s >= self.points[-1].time_s:
            return self.points[-1].position_m
        for left, right in zip(self.points, self.points[1:], strict=True):
            if left.time_s <= t_s <= right.time_s:
                return _interpolate_vector(
                    left.time_s,
                    left.position_m,
                    right.time_s,
                    right.position_m,
                    t_s,
                )
        raise AssertionError("profile interpolation should have returned")


class DeployableLegKinematics(BaseModel):
    """Simple hinge + angle model for deployable-leg center of mass."""

    model_config = ConfigDict(extra="forbid")

    hinge_position_m: Vector3
    axial_unit: Vector3
    radial_unit: Vector3
    length_m: float = Field(gt=0.0)
    stowed_angle_deg: float
    deployed_angle_deg: float
    deploy_start_s: float = Field(ge=0.0)
    deploy_duration_s: float = Field(gt=0.0)

    @field_validator("axial_unit", "radial_unit")
    @classmethod
    def vectors_must_be_nonzero(cls, value: Vector3) -> Vector3:
        _unit(value)
        return value

    def deploy_fraction_at(self, t_s: float) -> float:
        """Return [0, 1] deployment progress."""

        if t_s <= self.deploy_start_s:
            return 0.0
        if t_s >= self.deploy_start_s + self.deploy_duration_s:
            return 1.0
        return (t_s - self.deploy_start_s) / self.deploy_duration_s

    def angle_deg_at(self, t_s: float) -> float:
        """Return current leg deployment angle in degrees."""

        fraction = self.deploy_fraction_at(t_s)
        return self.stowed_angle_deg + fraction * (self.deployed_angle_deg - self.stowed_angle_deg)

    def center_of_mass_at(self, t_s: float) -> Vector3:
        """Return leg center of mass from hinge, length, and deployment angle."""

        axial = np.asarray(_unit(self.axial_unit), dtype=np.float64)
        radial = np.asarray(_unit(self.radial_unit), dtype=np.float64)
        hinge = np.asarray(self.hinge_position_m, dtype=np.float64)
        angle = math.radians(self.angle_deg_at(t_s))
        direction = math.cos(angle) * axial + math.sin(angle) * radial
        center = hinge + 0.5 * self.length_m * direction
        return (float(center[0]), float(center[1]), float(center[2]))


class PartDefinition(BaseModel):
    """A mass-bearing vehicle part."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    material: str = Field(min_length=1)
    mass_kg: float = Field(gt=0.0)
    position_m: Vector3
    state_tag: StateTag
    inertia_kg_m2: Matrix3 = ZERO_INERTIA
    depletion: DepletionProfile | None = None
    position_profile: PositionProfile | None = None
    deployable_leg: DeployableLegKinematics | None = None

    @field_validator("inertia_kg_m2")
    @classmethod
    def inertia_must_be_symmetric(cls, value: Matrix3) -> Matrix3:
        matrix = np.asarray(value, dtype=np.float64)
        if matrix.shape != (3, 3):
            msg = "inertia tensor must be 3x3"
            raise ValueError(msg)
        if not np.allclose(matrix, matrix.T, atol=1.0e-12):
            msg = "inertia tensor must be symmetric"
            raise ValueError(msg)
        eigvals = np.linalg.eigvalsh(matrix)
        if np.any(eigvals < -1.0e-12):
            msg = "inertia tensor must be positive semidefinite"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_state_models(self) -> PartDefinition:
        if self.state_tag in {"propellant", "CO2"} and self.depletion is None:
            msg = f"{self.state_tag} parts require a depletion profile"
            raise ValueError(msg)
        if self.state_tag == "deployable-leg" and self.deployable_leg is None:
            msg = "deployable-leg parts require deployable_leg kinematics"
            raise ValueError(msg)
        return self

    def remaining_fraction_at(self, t_s: float) -> float:
        if self.depletion is None:
            return 1.0
        return self.depletion.remaining_fraction_at(t_s)

    def mass_at(self, t_s: float) -> float:
        return self.mass_kg * self.remaining_fraction_at(t_s)

    def position_at(self, t_s: float) -> Vector3:
        if self.deployable_leg is not None:
            return self.deployable_leg.center_of_mass_at(t_s)
        if self.position_profile is not None:
            return self.position_profile.position_at(t_s)
        return self.position_m


class VehicleDefinition(BaseModel):
    """Versioned vehicle parts document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    parts: tuple[PartDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def part_ids_must_be_unique(self) -> VehicleDefinition:
        ids = [part.id for part in self.parts]
        if len(ids) != len(set(ids)):
            msg = "part ids must be unique"
            raise ValueError(msg)
        return self
