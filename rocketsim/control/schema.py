"""Strict controller configuration schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class SILControllerConfig(BaseModel):
    """Native-SIL controller gains and gates."""

    model_config = ConfigDict(extra="forbid")

    control_start_time_s: float = Field(ge=0.0)
    landing_burn_altitude_m: float = Field(gt=0.0)
    target_descent_rate_m_s: float
    descent_rate_kp: float = Field(ge=0.0)
    altitude_kp: float = Field(ge=0.0)
    attitude_accel_kp: float = Field(ge=0.0)
    angular_rate_kd: float = Field(ge=0.0)
    max_collective_duty: float = Field(ge=0.0, le=1.0)
    max_torque_duty: float = Field(ge=0.0, le=1.0)
    pwm_frequency_hz: float = Field(gt=0.0)


class ControlData(BaseModel):
    """Validated payload under config/control.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["sil", "renode"]
    loop_rate_hz: float = Field(gt=0.0)
    latency_s: float = Field(ge=0.0)
    jitter_s: float = Field(ge=0.0)
    control_law: Literal["pd"]
    sil: SILControllerConfig


class ControlConfig(BaseModel):
    """Versioned controller config document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: ControlData


def load_control_config(path: Path | str) -> ControlConfig:
    """Load config/control.yaml into a strict controller definition."""

    control_path = Path(path)
    raw = yaml.safe_load(control_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{control_path} must contain a YAML mapping"
        raise TypeError(msg)
    return ControlConfig.model_validate(raw)
