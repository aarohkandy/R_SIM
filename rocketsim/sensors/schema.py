"""Strict sensor configuration schemas."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

Vector3 = tuple[float, float, float]
Matrix3 = tuple[Vector3, Vector3, Vector3]


class IMUConfig(BaseModel):
    """IMU noise, calibration, and sample-rate settings."""

    model_config = ConfigDict(extra="forbid")

    sample_rate_hz: float = Field(gt=0.0)
    accel_noise_density_m_s2_per_sqrt_hz: float = Field(ge=0.0)
    gyro_noise_density_rad_s_per_sqrt_hz: float = Field(ge=0.0)
    accel_bias_initial_m_s2: Vector3
    gyro_bias_initial_rad_s: Vector3
    accel_bias_random_walk_m_s2_per_sqrt_s: float = Field(ge=0.0)
    gyro_bias_random_walk_rad_s_per_sqrt_s: float = Field(ge=0.0)
    accel_scale_factor: Vector3
    gyro_scale_factor: Vector3
    misalignment_matrix: Matrix3
    accel_saturation_m_s2: float = Field(gt=0.0)
    gyro_saturation_rad_s: float = Field(gt=0.0)

    @field_validator("misalignment_matrix")
    @classmethod
    def misalignment_must_be_3x3(cls, value: Matrix3) -> Matrix3:
        matrix = np.asarray(value, dtype=np.float64)
        if matrix.shape != (3, 3):
            msg = "misalignment_matrix must be 3x3"
            raise ValueError(msg)
        if not np.all(np.isfinite(matrix)):
            msg = "misalignment_matrix must be finite"
            raise ValueError(msg)
        return value


class BarometerConfig(BaseModel):
    """Barometer noise, bias, lag, and sample-rate settings."""

    model_config = ConfigDict(extra="forbid")

    sample_rate_hz: float = Field(gt=0.0)
    pressure_noise_density_pa_per_sqrt_hz: float = Field(ge=0.0)
    pressure_bias_initial_pa: float
    pressure_bias_random_walk_pa_per_sqrt_s: float = Field(ge=0.0)
    lag_time_constant_s: float = Field(gt=0.0)
    pressure_min_pa: float = Field(gt=0.0)
    pressure_max_pa: float = Field(gt=0.0)

    @model_validator(mode="after")
    def pressure_range_must_be_ordered(self) -> BarometerConfig:
        if self.pressure_min_pa >= self.pressure_max_pa:
            msg = "pressure_min_pa must be less than pressure_max_pa"
            raise ValueError(msg)
        return self


class DisabledSensorConfig(BaseModel):
    """Configuration for deferred sensors kept behind explicit stubs."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool


class SensorsData(BaseModel):
    """Validated payload under config/sensors.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    noise_enabled: bool
    imu: IMUConfig
    barometer: BarometerConfig
    tof_rangefinder: DisabledSensorConfig
    pressure_transducer: DisabledSensorConfig


class SensorsConfig(BaseModel):
    """Versioned sensor configuration document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: SensorsData


def load_sensors_config(path: Path | str) -> SensorsConfig:
    """Load config/sensors.yaml into a strict sensor definition."""

    sensors_path = Path(path)
    raw = yaml.safe_load(sensors_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{sensors_path} must contain a YAML mapping"
        raise TypeError(msg)
    return SensorsConfig.model_validate(raw)
