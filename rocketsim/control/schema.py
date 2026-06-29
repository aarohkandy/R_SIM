"""Strict controller configuration schemas."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


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


class RenodeMachineConfig(BaseModel):
    """One Renode machine expected in the HIL co-sim."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["esp32", "teensy"]
    elf_path: str = Field(min_length=1)
    platform_repl_path: str = Field(min_length=1)
    platform_verified: bool
    role: str = Field(min_length=1)


class RenodeInterMcuLinkConfig(BaseModel):
    """Configured wired link between emulated flight-computer nodes."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["uart", "spi", "i2c"]
    teensy_endpoint: str = Field(min_length=1)
    esp32_endpoint: str = Field(min_length=1)
    baud_rate: int | None = Field(default=None, gt=0)


class RenodeSensorInjectionConfig(BaseModel):
    """Plant-to-MCU sensor injection channel description."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["external_control", "resd"]
    imu_channel: str = Field(min_length=1)
    barometer_channel: str = Field(min_length=1)
    pressure_transducer_channel: str = Field(min_length=1)
    tof_channel: str = Field(min_length=1)


class RenodeActuationConfig(BaseModel):
    """MCU-to-plant actuation channel description."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["gpio", "pwm"]
    source_machine: Literal["teensy"]
    solenoid_lines: tuple[str, ...] = Field(min_length=3)


class RenodeHilConfig(BaseModel):
    """Backend-B Renode HIL bring-up configuration."""

    model_config = ConfigDict(extra="forbid")

    renode_executable: str = Field(min_length=1)
    python_bridge_module: str = Field(min_length=1)
    script_path: str = Field(min_length=1)
    status_output_dir: str = Field(min_length=1)
    sync_timeout_s: float = Field(gt=0.0)
    loop_overrun_margin_s: float = Field(ge=0.0)
    machines: tuple[RenodeMachineConfig, ...] = Field(min_length=2)
    sensor_injection: RenodeSensorInjectionConfig
    actuation: RenodeActuationConfig
    inter_mcu_link: RenodeInterMcuLinkConfig

    @model_validator(mode="after")
    def machines_must_include_esp32_and_teensy(self) -> RenodeHilConfig:
        names = {machine.name for machine in self.machines}
        if names != {"esp32", "teensy"}:
            msg = "Renode HIL machines must include exactly esp32 and teensy"
            raise ValueError(msg)
        if len({machine.name for machine in self.machines}) != len(self.machines):
            msg = "Renode HIL machine names must be unique"
            raise ValueError(msg)
        return self


class ControlData(BaseModel):
    """Validated payload under config/control.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["sil", "renode"]
    loop_rate_hz: float = Field(gt=0.0)
    latency_s: float = Field(ge=0.0)
    jitter_s: float = Field(ge=0.0)
    control_law: Literal["pd"]
    sil: SILControllerConfig
    renode: RenodeHilConfig


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
