"""Solid motor thrust curve parsing and mass-flow coupling."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from rocketsim.vehicle.schema import DepletionPoint, DepletionProfile

Vector3 = tuple[float, float, float]


class MotorConfigData(BaseModel):
    """Validated motor config payload."""

    model_config = ConfigDict(extra="forbid")

    thrust_curve_path: str = Field(min_length=1)
    ignition_time_s: float = Field(ge=0.0)
    declared_total_impulse_ns: float | None = Field(default=None, gt=0.0)
    notes: str = Field(min_length=1)


class MotorConfig(BaseModel):
    """Versioned motor config document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: MotorConfigData


@dataclass(frozen=True)
class MotorMetadata:
    """Motor header metadata."""

    designation: str
    diameter_mm: float
    length_mm: float
    delays: str
    propellant_mass_kg: float
    total_mass_kg: float
    manufacturer: str
    declared_total_impulse_ns: float | None = None


@dataclass(frozen=True)
class ThrustCurvePoint:
    """One thrust curve sample."""

    time_s: float
    thrust_n: float


@dataclass(frozen=True)
class SolidMotor:
    """Solid motor thrust and propellant depletion model."""

    metadata: MotorMetadata
    points: tuple[ThrustCurvePoint, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            msg = "solid motor thrust curve requires at least two points"
            raise ValueError(msg)
        times = np.asarray([point.time_s for point in self.points], dtype=np.float64)
        thrust = np.asarray([point.thrust_n for point in self.points], dtype=np.float64)
        if np.any(times < 0.0):
            msg = "thrust curve times must be non-negative"
            raise ValueError(msg)
        if np.any(np.diff(times) <= 0.0):
            msg = "thrust curve times must be strictly increasing"
            raise ValueError(msg)
        if np.any(thrust < 0.0):
            msg = "thrust values must be non-negative"
            raise ValueError(msg)

    @property
    def times_s(self) -> NDArray[np.float64]:
        return np.asarray([point.time_s for point in self.points], dtype=np.float64)

    @property
    def thrusts_n(self) -> NDArray[np.float64]:
        return np.asarray([point.thrust_n for point in self.points], dtype=np.float64)

    @property
    def burn_time_s(self) -> float:
        return self.points[-1].time_s

    @property
    def total_impulse_ns(self) -> float:
        return float(np.trapezoid(self.thrusts_n, self.times_s))

    @property
    def average_thrust_n(self) -> float:
        if self.burn_time_s <= 0.0:
            return 0.0
        return self.total_impulse_ns / self.burn_time_s

    def thrust_at(self, t_s: float) -> float:
        """Linearly interpolate thrust, clamped to zero outside the burn."""

        if t_s < self.points[0].time_s or t_s > self.points[-1].time_s:
            return 0.0
        return float(np.interp(t_s, self.times_s, self.thrusts_n))

    def cumulative_impulse_at(self, t_s: float) -> float:
        """Integrate thrust from ignition to time with trapezoids."""

        if t_s <= self.points[0].time_s:
            return 0.0
        if t_s >= self.points[-1].time_s:
            return self.total_impulse_ns

        times = self.times_s
        thrusts = self.thrusts_n
        insertion_index = int(np.searchsorted(times, t_s, side="right"))
        clipped_times = np.concatenate((times[:insertion_index], np.asarray([t_s])))
        clipped_thrusts = np.concatenate(
            (thrusts[:insertion_index], np.asarray([self.thrust_at(t_s)]))
        )
        return float(np.trapezoid(clipped_thrusts, clipped_times))

    def propellant_remaining_mass_kg(self, t_s: float) -> float:
        """Propellant remaining assuming mass flow follows delivered impulse."""

        if self.total_impulse_ns <= 0.0:
            msg = "total impulse must be positive to compute propellant depletion"
            raise ValueError(msg)
        burned_fraction = self.cumulative_impulse_at(t_s) / self.total_impulse_ns
        remaining = self.metadata.propellant_mass_kg * (1.0 - min(max(burned_fraction, 0.0), 1.0))
        return max(0.0, remaining)

    def mass_flow_kg_s(self, t_s: float) -> float:
        """Return positive propellant mass-flow rate during burn."""

        if self.total_impulse_ns <= 0.0:
            msg = "total impulse must be positive to compute mass flow"
            raise ValueError(msg)
        return self.metadata.propellant_mass_kg * self.thrust_at(t_s) / self.total_impulse_ns

    def thrust_force_body_n(
        self,
        t_s: float,
        axis: Vector3 = (0.0, 0.0, 1.0),
    ) -> NDArray[np.float64]:
        """Return thrust vector along a body-axis direction."""

        vector = np.asarray(axis, dtype=np.float64)
        norm = float(np.linalg.norm(vector))
        if norm <= 0.0:
            msg = "thrust axis must be non-zero"
            raise ValueError(msg)
        return vector / norm * self.thrust_at(t_s)

    def depletion_profile(self) -> DepletionProfile:
        """Convert cumulative impulse to a vehicle-compatible depletion profile."""

        total_impulse = self.total_impulse_ns
        if total_impulse <= 0.0:
            msg = "total impulse must be positive to create depletion profile"
            raise ValueError(msg)
        return DepletionProfile(
            points=tuple(
                DepletionPoint(
                    time_s=point.time_s,
                    remaining_fraction=1.0
                    - self.cumulative_impulse_at(point.time_s) / total_impulse,
                )
                for point in self.points
            )
        )

    def assert_declared_impulse_matches(self, tolerance_ns: float) -> None:
        """Raise if an available declared impulse disagrees with curve integration."""

        declared = self.metadata.declared_total_impulse_ns
        if declared is None:
            return
        delta = abs(self.total_impulse_ns - declared)
        if delta > tolerance_ns:
            msg = (
                f"integrated impulse {self.total_impulse_ns:.6g} N*s differs from "
                f"declared {declared:.6g} N*s by {delta:.6g} N*s"
            )
            raise ValueError(msg)


def load_motor_config(path: Path | str) -> MotorConfig:
    """Load config/motor.yaml."""

    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{config_path} must contain a YAML mapping"
        raise TypeError(msg)
    return MotorConfig.model_validate(raw)


def load_solid_motor(
    path: Path | str,
    declared_total_impulse_ns: float | None = None,
) -> SolidMotor:
    """Load `.eng` or `.rse` solid motor files."""

    motor_path = Path(path)
    suffix = motor_path.suffix.lower()
    if suffix == ".eng":
        return parse_eng(motor_path, declared_total_impulse_ns=declared_total_impulse_ns)
    if suffix == ".rse":
        return parse_rse(motor_path, declared_total_impulse_ns=declared_total_impulse_ns)
    msg = f"unsupported motor file extension: {suffix}"
    raise ValueError(msg)


def load_configured_motor(config_path: Path | str) -> SolidMotor:
    """Load the motor referenced by config/motor.yaml."""

    config = load_motor_config(config_path)
    root = Path(config_path).resolve().parent.parent
    motor_path = root / config.data.thrust_curve_path
    return load_solid_motor(
        motor_path,
        declared_total_impulse_ns=config.data.declared_total_impulse_ns,
    )


def parse_eng(path: Path | str, declared_total_impulse_ns: float | None = None) -> SolidMotor:
    """Parse a RASP `.eng` thrust curve."""

    lines = [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(";")
    ]
    if len(lines) < 3:
        msg = "RASP .eng file requires a header and at least two data points"
        raise ValueError(msg)

    header = lines[0].split()
    if len(header) < 6:
        msg = (
            "RASP .eng header must include designation, diameter, length, delays, "
            "propellant mass, total mass"
        )
        raise ValueError(msg)
    metadata = MotorMetadata(
        designation=header[0],
        diameter_mm=float(header[1]),
        length_mm=float(header[2]),
        delays=header[3],
        propellant_mass_kg=float(header[4]),
        total_mass_kg=float(header[5]),
        manufacturer=" ".join(header[6:]) if len(header) > 6 else "",
        declared_total_impulse_ns=declared_total_impulse_ns,
    )
    points = tuple(_parse_time_thrust_line(line) for line in lines[1:])
    return SolidMotor(metadata=metadata, points=points)


def parse_rse(path: Path | str, declared_total_impulse_ns: float | None = None) -> SolidMotor:
    """Parse a minimal RockSim `.rse` XML motor file."""

    root = ET.parse(path).getroot()
    engine = next((item for item in root.iter() if _local_name(item.tag) == "engine"), None)
    if engine is None:
        msg = "RSE file does not contain an engine element"
        raise ValueError(msg)

    designation = engine.attrib.get("code") or engine.attrib.get("name") or "UNKNOWN"
    propellant_mass_kg = _grams_to_kg(_required_float(engine, "propWt"))
    total_mass_kg = _grams_to_kg(_required_float(engine, "initWt"))
    metadata = MotorMetadata(
        designation=designation,
        diameter_mm=_required_float(engine, "dia"),
        length_mm=_required_float(engine, "len"),
        delays=engine.attrib.get("delays", ""),
        propellant_mass_kg=propellant_mass_kg,
        total_mass_kg=total_mass_kg,
        manufacturer=engine.attrib.get("mfg", ""),
        declared_total_impulse_ns=declared_total_impulse_ns
        if declared_total_impulse_ns is not None
        else _optional_float(engine, "Itot"),
    )
    points = tuple(
        ThrustCurvePoint(time_s=_required_float(item, "t"), thrust_n=_required_float(item, "f"))
        for item in root.iter()
        if _local_name(item.tag) == "eng-data"
    )
    return SolidMotor(metadata=metadata, points=points)


def _parse_time_thrust_line(line: str) -> ThrustCurvePoint:
    columns = line.split()
    if len(columns) < 2:
        msg = f"invalid thrust data row: {line}"
        raise ValueError(msg)
    return ThrustCurvePoint(time_s=float(columns[0]), thrust_n=float(columns[1]))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _required_float(element: ET.Element[str], key: str) -> float:
    value = element.attrib.get(key)
    if value is None:
        msg = f"RSE engine is missing required attribute {key}"
        raise ValueError(msg)
    return float(value)


def _optional_float(element: ET.Element[str], key: str) -> float | None:
    value = element.attrib.get(key)
    if value is None:
        return None
    return float(value)


def _grams_to_kg(value: float) -> float:
    return value / 1000.0


def impulse_class_bounds(designation: str) -> tuple[float, float] | None:
    """Return N*s bounds for the motor class letter in a designation."""

    match = re.match(r"([A-Z]+)", designation.upper())
    if match is None:
        return None
    classes = {
        "A": (1.26, 2.5),
        "B": (2.51, 5.0),
        "C": (5.01, 10.0),
        "D": (10.01, 20.0),
        "E": (20.01, 40.0),
        "F": (40.01, 80.0),
        "G": (80.01, 160.0),
        "H": (160.01, 320.0),
    }
    return classes.get(match.group(1)[0])
