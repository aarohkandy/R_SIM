"""Strict simulation configuration schema."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

Vector3 = tuple[float, float, float]


class DynamicsSettings(BaseModel):
    """Runtime settings for the fixed-step rigid-body plant."""

    model_config = ConfigDict(extra="forbid")

    minimum_aero_speed_m_s: float = Field(gt=0.0)
    angular_damping_n_m_s: float = Field(ge=0.0)
    motor_thrust_axis_unit: Vector3
    motor_thrust_position_m: Vector3

    @field_validator("motor_thrust_axis_unit")
    @classmethod
    def motor_axis_must_be_nonzero(cls, value: Vector3) -> Vector3:
        if np.linalg.norm(np.asarray(value, dtype=np.float64)) <= 0.0:
            msg = "motor thrust axis must be non-zero"
            raise ValueError(msg)
        return value


class SimData(BaseModel):
    """Validated payload under config/sim.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    master_seed: int = Field(ge=0)
    integrator_dt_s: float = Field(gt=0.0)
    renode_sync_quantum_s: float = Field(gt=0.0)
    end_condition: Literal["touchdown"]
    dynamics: DynamicsSettings


class SimConfig(BaseModel):
    """Versioned master simulation config."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: SimData


def load_sim_config(path: Path | str) -> SimConfig:
    """Load config/sim.yaml into a strict sim definition."""

    sim_path = Path(path)
    raw = yaml.safe_load(sim_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{sim_path} must contain a YAML mapping"
        raise TypeError(msg)
    return SimConfig.model_validate(raw)
