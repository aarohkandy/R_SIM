"""Strict actuation configuration schemas."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


class AllocationConfig(BaseModel):
    """Control-allocation scaling parameters."""

    model_config = ConfigDict(extra="forbid")

    collective_gain: float = Field(gt=0.0)
    torque_gain: float = Field(gt=0.0)


class FaultInjectionConfig(BaseModel):
    """Explicit valve fault configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    stuck_open: tuple[int, ...] = ()
    stuck_closed: tuple[int, ...] = ()


class ActuationData(BaseModel):
    """Validated payload under config/actuation.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    valve_count: int = Field(gt=0)
    open_latency_s: float = Field(ge=0.0)
    close_latency_s: float = Field(ge=0.0)
    min_reliable_pulse_s: float = Field(gt=0.0)
    allocation: AllocationConfig
    fault_injection: FaultInjectionConfig

    @model_validator(mode="after")
    def fault_indices_must_be_in_range(self) -> ActuationData:
        indices = self.fault_injection.stuck_open + self.fault_injection.stuck_closed
        for index in indices:
            if index < 0 or index >= self.valve_count:
                msg = "fault valve indices must be within valve_count"
                raise ValueError(msg)
        return self


class ActuationConfig(BaseModel):
    """Versioned actuation config document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: ActuationData


def load_actuation_config(path: Path | str) -> ActuationConfig:
    """Load config/actuation.yaml into a strict actuation definition."""

    actuation_path = Path(path)
    raw = yaml.safe_load(actuation_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{actuation_path} must contain a YAML mapping"
        raise TypeError(msg)
    return ActuationConfig.model_validate(raw)
