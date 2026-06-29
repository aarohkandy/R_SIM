"""Strict simulation configuration schema."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]


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


class E2ESettings(BaseModel):
    """End-to-end SIL flight-run settings."""

    model_config = ConfigDict(extra="forbid")

    output_root: str = Field(min_length=1)
    run_id_prefix: str = Field(min_length=1)
    max_time_s: float = Field(gt=0.0)
    touchdown_altitude_m: float
    initial_position_m: Vector3
    initial_velocity_m_s: Vector3
    initial_attitude_quat: Quaternion
    initial_angular_velocity_rad_s: Vector3
    rail_exit_latch_margin_m: float = Field(ge=0.0)

    @field_validator("initial_attitude_quat")
    @classmethod
    def initial_attitude_must_be_nonzero(cls, value: Quaternion) -> Quaternion:
        if np.linalg.norm(np.asarray(value, dtype=np.float64)) <= 0.0:
            msg = "initial attitude quaternion must be non-zero"
            raise ValueError(msg)
        return value


class Phase13Settings(BaseModel):
    """Convergence and cross-validation study settings."""

    model_config = ConfigDict(extra="forbid")

    output_dir: str = Field(min_length=1)
    integrator_dt_values_s: tuple[float, ...] = Field(min_length=2)
    renode_sync_quantum_values_s: tuple[float, ...] = Field(min_length=2)
    landing_metric_relative_tolerance: float = Field(gt=0.0)
    landing_metric_absolute_tolerance: float = Field(ge=0.0)
    ballistic_validation_duration_s: float = Field(gt=0.0)
    rocketpy_reference_required: bool

    @field_validator("integrator_dt_values_s", "renode_sync_quantum_values_s")
    @classmethod
    def values_must_be_positive_and_strictly_decreasing(
        cls,
        value: tuple[float, ...],
    ) -> tuple[float, ...]:
        if any(item <= 0.0 for item in value):
            msg = "phase 13 timestep values must be positive"
            raise ValueError(msg)
        if any(right >= left for left, right in zip(value, value[1:], strict=False)):
            msg = "phase 13 timestep values must be strictly decreasing"
            raise ValueError(msg)
        return value


class MonteCarloDispersions(BaseModel):
    """Phase-14 input dispersion widths for the native-SIL Monte Carlo."""

    model_config = ConfigDict(extra="forbid")

    wind_xy_std_m_s: float = Field(ge=0.0)
    mass_scale_std_fraction: float = Field(ge=0.0)
    cg_shift_std_m: Vector3
    nozzle_cant_std_deg: float = Field(ge=0.0)
    valve_latency_std_s: float = Field(ge=0.0)
    sensor_seed_enabled: bool

    @field_validator("cg_shift_std_m")
    @classmethod
    def cg_shift_stds_must_be_nonnegative(cls, value: Vector3) -> Vector3:
        if any(component < 0.0 for component in value):
            msg = "phase 14 CG-shift standard deviations must be non-negative"
            raise ValueError(msg)
        return value


class Phase14Settings(BaseModel):
    """Large-N Monte Carlo study settings."""

    model_config = ConfigDict(extra="forbid")

    output_dir: str = Field(min_length=1)
    target_runs: int = Field(ge=1000)
    batch_size: int = Field(gt=0)
    stability_window_batches: int = Field(gt=0)
    percentile_stability_tolerance: float = Field(gt=0.0)
    retained_bundle_stride: int = Field(ge=0)
    histogram_bins: int = Field(gt=0)
    percentiles: tuple[float, ...] = Field(min_length=1)
    dispersions: MonteCarloDispersions

    @field_validator("percentiles")
    @classmethod
    def percentiles_must_be_in_range(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        if any(percentile < 0.0 or percentile > 100.0 for percentile in value):
            msg = "phase 14 percentiles must be between 0 and 100"
            raise ValueError(msg)
        return value


class SimData(BaseModel):
    """Validated payload under config/sim.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    master_seed: int = Field(ge=0)
    integrator_dt_s: float = Field(gt=0.0)
    renode_sync_quantum_s: float = Field(gt=0.0)
    end_condition: Literal["touchdown"]
    e2e: E2ESettings
    phase13: Phase13Settings
    phase14: Phase14Settings
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
