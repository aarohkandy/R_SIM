"""Safe config/input editing helpers for the localhost workbench."""

from __future__ import annotations

import csv
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from rocketsim.actuation.schema import ActuationConfig
from rocketsim.aero.schema import AeroDefinition
from rocketsim.config import ConfigDocument
from rocketsim.control.schema import ControlConfig
from rocketsim.environment.schema import EnvironmentDefinition
from rocketsim.propulsion.coldgas import ColdGasConfig
from rocketsim.propulsion.solid import MotorConfig, parse_eng, parse_rse
from rocketsim.sensors.schema import SensorsConfig
from rocketsim.sim.schema import SimConfig
from rocketsim.structural.schema import StructuralConfig
from rocketsim.thermal.schema import ThermalConfig
from rocketsim.vehicle import VehicleModel, properties_as_dict
from rocketsim.vehicle.schema import VehicleDefinition


@dataclass(frozen=True)
class EditableFile:
    """One repo-confined file exposed through the workbench editor."""

    name: str
    label: str
    group: str
    relative_path: str
    language: str
    description: str
    validator: Callable[[str], dict[str, Any]]


def editable_files() -> tuple[EditableFile, ...]:
    """Return the known workbench-editable files."""

    return (
        EditableFile(
            name="bom",
            label="BOM / Parts",
            group="Rocket",
            relative_path="inputs/bom_placeholder.yaml",
            language="yaml",
            description="Masses, CG positions, propellant depletion, and deployable legs.",
            validator=_validate_vehicle_definition,
        ),
        EditableFile(
            name="vehicle",
            label="Vehicle Config",
            group="Rocket",
            relative_path="config/vehicle.yaml",
            language="yaml",
            description="Body geometry and paths to the editable BOM and materials files.",
            validator=_model_validator(ConfigDocument),
        ),
        EditableFile(
            name="materials",
            label="Materials",
            group="Rocket",
            relative_path="inputs/materials_placeholder.yaml",
            language="yaml",
            description="Thermal material limits used by thermal and structural post-processing.",
            validator=_validate_materials,
        ),
        EditableFile(
            name="motor",
            label="Motor Config",
            group="Propulsion",
            relative_path="config/motor.yaml",
            language="yaml",
            description="Solid motor curve path, ignition time, and declared impulse.",
            validator=_model_validator(MotorConfig),
        ),
        EditableFile(
            name="motor_curve",
            label="Motor Curve",
            group="Propulsion",
            relative_path="inputs/motor_D21_placeholder.eng",
            language="text",
            description="RASP .eng thrust curve used by the solid-motor model.",
            validator=_validate_motor_curve,
        ),
        EditableFile(
            name="coldgas",
            label="Cold Gas",
            group="Propulsion",
            relative_path="config/coldgas.yaml",
            language="yaml",
            description="CO2 tank, regulator, fixed nozzles, positions, and cant axes.",
            validator=_model_validator(ColdGasConfig),
        ),
        EditableFile(
            name="aero",
            label="Aerodynamics",
            group="Flight Model",
            relative_path="config/aero.yaml",
            language="yaml",
            description="Live CP/Cd build-up parameters and OpenRocket comparison anchors.",
            validator=_model_validator(AeroDefinition),
        ),
        EditableFile(
            name="environment",
            label="Environment",
            group="Flight Model",
            relative_path="config/environment.yaml",
            language="yaml",
            description="ISA atmosphere, wind, gusts, shear, and launch rail.",
            validator=_model_validator(EnvironmentDefinition),
        ),
        EditableFile(
            name="actuation",
            label="Actuation",
            group="Control",
            relative_path="config/actuation.yaml",
            language="yaml",
            description="Solenoid latency, pulse floor, allocator gains, and valve faults.",
            validator=_model_validator(ActuationConfig),
        ),
        EditableFile(
            name="control",
            label="Controller",
            group="Control",
            relative_path="config/control.yaml",
            language="yaml",
            description="Backend choice, loop timing, latency/jitter, and SIL gains.",
            validator=_model_validator(ControlConfig),
        ),
        EditableFile(
            name="sensors",
            label="Sensors",
            group="Electronics",
            relative_path="config/sensors.yaml",
            language="yaml",
            description="IMU and barometer rates, noise, bias, drift, scale, and lag.",
            validator=_model_validator(SensorsConfig),
        ),
        EditableFile(
            name="sim",
            label="Simulation",
            group="Runtime",
            relative_path="config/sim.yaml",
            language="yaml",
            description="Seed, fixed timestep, Renode quantum, e2e run settings, and plant knobs.",
            validator=_model_validator(SimConfig),
        ),
        EditableFile(
            name="thermal",
            label="Thermal",
            group="Post Flight",
            relative_path="config/thermal.yaml",
            language="yaml",
            description="Lumped-node thermal network, heat links, and heat sources.",
            validator=_model_validator(ThermalConfig),
        ),
        EditableFile(
            name="structural",
            label="Structural",
            group="Post Flight",
            relative_path="config/structural.yaml",
            language="yaml",
            description="Event-triggered load cases, FEA solver settings, nodes, and members.",
            validator=_model_validator(StructuralConfig),
        ),
        EditableFile(
            name="openrocket_anchor",
            label="OpenRocket Anchor",
            group="Validation",
            relative_path="inputs/openrocket/frozen_placeholder.csv",
            language="csv",
            description="Frozen-configuration CP/Cd comparison data. Never runtime aero.",
            validator=_validate_openrocket_anchor,
        ),
    )


def list_workbench_files(repo_root: Path) -> list[dict[str, Any]]:
    """Return metadata and validation status for every editable workbench file."""

    return [
        read_workbench_file(repo_root, item.name, include_text=False)
        for item in editable_files()
    ]


def read_workbench_file(
    repo_root: Path,
    name: str,
    *,
    include_text: bool = True,
) -> dict[str, Any]:
    """Read one whitelisted editable file."""

    item = _editable_or_raise(name)
    path = _resolve_editable_path(repo_root, item)
    text = path.read_text(encoding="utf-8")
    validation = validate_workbench_text(name, text)
    payload = _file_metadata(item, path)
    payload.update(validation)
    if include_text:
        payload["text"] = text
    return payload


def validate_workbench_text(name: str, text: str) -> dict[str, Any]:
    """Validate pasted editor text without saving it."""

    item = _editable_or_raise(name)
    try:
        parsed = item.validator(text)
    except (TypeError, ValueError, ValidationError, yaml.YAMLError, csv.Error) as exc:
        return {
            "valid": False,
            "message": _validation_message(exc),
            "summary": {},
            "document": None,
        }
    return {
        "valid": True,
        "message": "Validated against the simulation schema.",
        "summary": _summary_for(name, parsed),
        "document": parsed,
    }


def save_workbench_text(repo_root: Path, name: str, text: str) -> dict[str, Any]:
    """Validate and save one whitelisted editable file."""

    validation = validate_workbench_text(name, text)
    if not validation["valid"]:
        return validation
    item = _editable_or_raise(name)
    path = _resolve_editable_path(repo_root, item)
    path.write_text(text if text.endswith("\n") else f"{text}\n", encoding="utf-8")
    return read_workbench_file(repo_root, name)


def rocket_summary(repo_root: Path) -> dict[str, Any]:
    """Return an at-a-glance summary of the currently editable rocket definition."""

    bom_path = repo_root / EDITABLE_BY_NAME["bom"].relative_path
    motor_path = repo_root / EDITABLE_BY_NAME["motor_curve"].relative_path
    coldgas_text = (repo_root / EDITABLE_BY_NAME["coldgas"].relative_path).read_text(
        encoding="utf-8"
    )
    aero_text = (repo_root / EDITABLE_BY_NAME["aero"].relative_path).read_text(encoding="utf-8")
    sim_text = (repo_root / EDITABLE_BY_NAME["sim"].relative_path).read_text(encoding="utf-8")

    vehicle = VehicleModel.from_bom_path(bom_path)
    mass = vehicle.mass_properties(0.0)
    motor = _load_motor_curve_from_text(motor_path.suffix, motor_path.read_text(encoding="utf-8"))
    coldgas = ColdGasConfig.model_validate(_yaml_mapping(coldgas_text))
    aero = AeroDefinition.model_validate(_yaml_mapping(aero_text))
    sim = SimConfig.model_validate(_yaml_mapping(sim_text))

    mass_dict = properties_as_dict(mass)
    return {
        "wet_mass_kg": mass_dict["mass_kg"],
        "cg_m": mass_dict["center_of_mass_m"],
        "part_count": len(vehicle.definition.parts),
        "deployable_leg_count": sum(
            1 for part in vehicle.definition.parts if part.state_tag == "deployable-leg"
        ),
        "propellant_count": sum(
            1 for part in vehicle.definition.parts if part.state_tag == "propellant"
        ),
        "co2_part_count": sum(1 for part in vehicle.definition.parts if part.state_tag == "CO2"),
        "motor_designation": motor.metadata.designation,
        "motor_burn_time_s": motor.burn_time_s,
        "motor_total_impulse_ns": motor.total_impulse_ns,
        "co2_initial_mass_kg": coldgas.data.tank.initial_co2_mass_kg,
        "nozzle_count": len(coldgas.data.nozzles.items),
        "regulator_setpoint_pa": coldgas.data.regulator.setpoint_pa,
        "body_diameter_m": aero.data.geometry.body_diameter_m,
        "body_length_m": aero.data.geometry.body_length_m,
        "integrator_dt_s": sim.data.integrator_dt_s,
        "master_seed": sim.data.master_seed,
    }


def _file_metadata(item: EditableFile, path: Path) -> dict[str, Any]:
    return {
        "name": item.name,
        "label": item.label,
        "group": item.group,
        "path": item.relative_path,
        "language": item.language,
        "description": item.description,
        "exists": path.exists(),
    }


def _editable_or_raise(name: str) -> EditableFile:
    try:
        return EDITABLE_BY_NAME[name]
    except KeyError as exc:
        msg = f"unknown editable file: {name}"
        raise FileNotFoundError(msg) from exc


def _resolve_editable_path(repo_root: Path, item: EditableFile) -> Path:
    root = repo_root.resolve()
    path = (root / item.relative_path).resolve()
    if root not in path.parents:
        msg = f"editable path escaped repo: {item.relative_path}"
        raise FileNotFoundError(msg)
    if not path.exists() or not path.is_file():
        msg = f"editable file missing: {item.relative_path}"
        raise FileNotFoundError(msg)
    return path


def _model_validator(model: type[BaseModel]) -> Callable[[str], dict[str, Any]]:
    def validate(text: str) -> dict[str, Any]:
        document = model.model_validate(_yaml_mapping(text))
        return document.model_dump(mode="json")

    return validate


def _validate_vehicle_definition(text: str) -> dict[str, Any]:
    document = VehicleDefinition.model_validate(_yaml_mapping(text))
    return document.model_dump(mode="json")


def _validate_materials(text: str) -> dict[str, Any]:
    raw = _yaml_mapping(text)
    materials = raw.get("materials")
    if not isinstance(materials, dict) or not materials:
        msg = "materials file must contain a non-empty materials mapping"
        raise ValueError(msg)
    for name, material in materials.items():
        if not isinstance(name, str) or not name:
            msg = "material names must be non-empty strings"
            raise ValueError(msg)
        if not isinstance(material, dict):
            msg = f"material {name!r} must be a mapping"
            raise ValueError(msg)
        limit = material.get("heat_deflection_temperature_deg_c")
        if not isinstance(limit, int | float):
            msg = f"material {name!r} needs heat_deflection_temperature_deg_c"
            raise ValueError(msg)
    return raw


def _validate_motor_curve(text: str) -> dict[str, Any]:
    motor = _load_motor_curve_from_text(".eng", text)
    return {
        "metadata": {
            "designation": motor.metadata.designation,
            "diameter_mm": motor.metadata.diameter_mm,
            "length_mm": motor.metadata.length_mm,
            "propellant_mass_kg": motor.metadata.propellant_mass_kg,
            "total_mass_kg": motor.metadata.total_mass_kg,
            "manufacturer": motor.metadata.manufacturer,
        },
        "point_count": len(motor.points),
        "burn_time_s": motor.burn_time_s,
        "total_impulse_ns": motor.total_impulse_ns,
        "average_thrust_n": motor.average_thrust_n,
    }


def _validate_openrocket_anchor(text: str) -> dict[str, Any]:
    rows = list(csv.DictReader(text.splitlines()))
    required = {
        "mach",
        "leg_angle_deg",
        "propellant_remaining_fraction",
        "co2_remaining_fraction",
        "cg_axial_m",
        "cp_axial_m",
        "cd",
    }
    if not rows:
        msg = "OpenRocket anchor CSV must contain at least one data row"
        raise ValueError(msg)
    columns = set(rows[0])
    missing = sorted(required - columns)
    if missing:
        msg = f"OpenRocket anchor missing columns: {', '.join(missing)}"
        raise ValueError(msg)
    for row in rows:
        for column in required:
            float(row[column])
    return {"columns": sorted(columns), "row_count": len(rows)}


def _yaml_mapping(text: str) -> dict[str, Any]:
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        msg = "YAML text must contain a mapping"
        raise TypeError(msg)
    return raw


def _load_motor_curve_from_text(suffix: str, text: str) -> Any:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix) as handle:
        handle.write(text)
        handle.flush()
        if suffix.lower() == ".rse":
            return parse_rse(Path(handle.name))
        return parse_eng(Path(handle.name))


def _summary_for(name: str, parsed: dict[str, Any]) -> dict[str, Any]:
    data = parsed.get("data", {}) if isinstance(parsed.get("data"), dict) else {}
    if name == "bom":
        parts = parsed.get("parts", [])
        return {
            "parts": len(parts),
            "deployable_legs": sum(
                1 for part in parts if part.get("state_tag") == "deployable-leg"
            ),
            "nominal_mass_kg": sum(float(part.get("mass_kg", 0.0)) for part in parts),
        }
    if name == "vehicle":
        return {
            "diameter_m": data.get("body", {}).get("diameter_m"),
            "length_m": data.get("body", {}).get("length_m"),
            "parts_path": data.get("parts_path"),
        }
    if name == "materials":
        return {"materials": len(parsed.get("materials", {}))}
    if name == "motor_curve":
        return {
            "designation": parsed["metadata"]["designation"],
            "burn_time_s": parsed["burn_time_s"],
            "total_impulse_ns": parsed["total_impulse_ns"],
        }
    if name == "coldgas":
        return {
            "co2_mass_kg": data.get("tank", {}).get("initial_co2_mass_kg"),
            "nozzles": len(data.get("nozzles", {}).get("items", [])),
            "regulator_setpoint_pa": data.get("regulator", {}).get("setpoint_pa"),
        }
    if name == "control":
        return {
            "backend": data.get("backend"),
            "loop_rate_hz": data.get("loop_rate_hz"),
            "latency_s": data.get("latency_s"),
        }
    if name == "sim":
        return {
            "seed": data.get("master_seed"),
            "dt_s": data.get("integrator_dt_s"),
            "renode_quantum_s": data.get("renode_sync_quantum_s"),
        }
    if name == "openrocket_anchor":
        return {"rows": parsed["row_count"], "columns": len(parsed["columns"])}
    return {
        "schema_version": parsed.get("schema_version"),
        "placeholder": parsed.get("placeholder"),
    }


def _validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ()))
        message = str(first.get("msg", "validation failed"))
        return f"{location}: {message}" if location else message
    return str(exc)


EDITABLE_BY_NAME = {item.name: item for item in editable_files()}
