"""Safe config/input editing helpers for the localhost workbench."""

from __future__ import annotations

import csv
import math
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

PSI_TO_PA = 6894.757293168


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


def rocket_builder_state(repo_root: Path) -> dict[str, Any]:
    """Return user-facing rocket-builder values backed by validated config files."""

    docs = _load_builder_documents(repo_root)
    vehicle = docs["vehicle"]
    bom = docs["bom"]
    motor = docs["motor"]
    coldgas = docs["coldgas"]
    aero = docs["aero"]
    control = docs["control"]
    sim = docs["sim"]
    nozzles = coldgas["data"]["nozzles"]["items"]
    first_nozzle = nozzles[0] if nozzles else {}
    return {
        "valid": all(
            read_workbench_file(repo_root, name, include_text=False)["valid"]
            for name in ("vehicle", "bom", "motor", "coldgas", "aero", "control", "sim")
        ),
        "values": {
            "body_diameter_mm": vehicle["data"]["body"]["diameter_m"] * 1000.0,
            "body_length_mm": vehicle["data"]["body"]["length_m"] * 1000.0,
            "target_wet_mass_kg": vehicle["data"]["target_wet_mass_kg"],
            "co2_mass_g": coldgas["data"]["tank"]["initial_co2_mass_kg"] * 1000.0,
            "regulator_setpoint_psi": coldgas["data"]["regulator"]["setpoint_pa"] / PSI_TO_PA,
            "nozzle_throat_area_mm2": first_nozzle.get("throat_area_m2", 0.0) * 1_000_000.0,
            "control_loop_rate_hz": control["data"]["loop_rate_hz"],
            "landing_burn_altitude_m": control["data"]["sil"]["landing_burn_altitude_m"],
            "master_seed": sim["data"]["master_seed"],
            "integrator_dt_ms": sim["data"]["integrator_dt_s"] * 1000.0,
            "motor_curve_path": motor["data"]["thrust_curve_path"],
        },
        "computed": {
            "part_count": len(bom["parts"]),
            "co2_parts": sum(1 for part in bom["parts"] if part.get("state_tag") == "CO2"),
            "nozzle_count": len(nozzles),
            "aero_body_diameter_mm": aero["data"]["geometry"]["body_diameter_m"] * 1000.0,
            "aero_body_length_mm": aero["data"]["geometry"]["body_length_m"] * 1000.0,
        },
        "sources": {
            "body": ["config/vehicle.yaml", "config/aero.yaml"],
            "mass": ["config/vehicle.yaml", "inputs/bom_placeholder.yaml"],
            "propulsion": ["config/coldgas.yaml", "config/motor.yaml"],
            "control": ["config/control.yaml"],
            "runtime": ["config/sim.yaml"],
        },
    }


def save_rocket_builder(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply rocket-builder values to the underlying editable config files."""

    docs = _load_builder_documents(repo_root)
    body_diameter_m = _positive_payload_float(payload, "body_diameter_mm") / 1000.0
    body_length_m = _positive_payload_float(payload, "body_length_mm") / 1000.0
    target_wet_mass_kg = _positive_payload_float(payload, "target_wet_mass_kg")
    co2_mass_kg = _positive_payload_float(payload, "co2_mass_g") / 1000.0
    regulator_setpoint_pa = _positive_payload_float(payload, "regulator_setpoint_psi") * PSI_TO_PA
    nozzle_throat_area_m2 = (
        _positive_payload_float(payload, "nozzle_throat_area_mm2") / 1_000_000.0
    )
    control_loop_rate_hz = _positive_payload_float(payload, "control_loop_rate_hz")
    landing_burn_altitude_m = _positive_payload_float(payload, "landing_burn_altitude_m")
    master_seed = _nonnegative_payload_int(payload, "master_seed")
    integrator_dt_s = _positive_payload_float(payload, "integrator_dt_ms") / 1000.0
    motor_curve_path = _payload_text(payload, "motor_curve_path")

    vehicle = docs["vehicle"]
    vehicle["data"]["body"]["diameter_m"] = body_diameter_m
    vehicle["data"]["body"]["length_m"] = body_length_m
    vehicle["data"]["target_wet_mass_kg"] = target_wet_mass_kg

    aero = docs["aero"]
    aero["data"]["geometry"]["body_diameter_m"] = body_diameter_m
    aero["data"]["geometry"]["body_length_m"] = body_length_m

    bom = docs["bom"]
    co2_parts = [part for part in bom["parts"] if part.get("state_tag") == "CO2"]
    if not co2_parts:
        msg = "BOM must contain at least one CO2 part to update CO2 mass"
        raise ValueError(msg)
    co2_parts[0]["mass_kg"] = co2_mass_kg

    coldgas = docs["coldgas"]
    coldgas["data"]["tank"]["initial_co2_mass_kg"] = co2_mass_kg
    coldgas["data"]["regulator"]["setpoint_pa"] = regulator_setpoint_pa
    for nozzle in coldgas["data"]["nozzles"]["items"]:
        nozzle["throat_area_m2"] = nozzle_throat_area_m2

    motor = docs["motor"]
    motor["data"]["thrust_curve_path"] = motor_curve_path

    control = docs["control"]
    control["data"]["loop_rate_hz"] = control_loop_rate_hz
    control["data"]["sil"]["landing_burn_altitude_m"] = landing_burn_altitude_m

    sim = docs["sim"]
    sim["data"]["master_seed"] = master_seed
    sim["data"]["integrator_dt_s"] = integrator_dt_s

    changed = {
        "vehicle": vehicle,
        "bom": bom,
        "motor": motor,
        "coldgas": coldgas,
        "aero": aero,
        "control": control,
        "sim": sim,
    }
    dumped = {name: _dump_yaml(document) for name, document in changed.items()}
    validation = {name: validate_workbench_text(name, text) for name, text in dumped.items()}
    invalid = {name: result for name, result in validation.items() if not result["valid"]}
    if invalid:
        name, result = next(iter(invalid.items()))
        msg = f"{name}: {result['message']}"
        raise ValueError(msg)
    for name, text in dumped.items():
        item = _editable_or_raise(name)
        _resolve_editable_path(repo_root, item).write_text(text, encoding="utf-8")
    state = rocket_builder_state(repo_root)
    state["updated_files"] = sorted(
        _editable_or_raise(name).relative_path for name in changed
    )
    return state


def rocket_parts_state(repo_root: Path) -> dict[str, Any]:
    """Return editable BOM part rows for the localhost rocket builder."""

    bom_path = _resolve_editable_path(repo_root, _editable_or_raise("bom"))
    bom = _yaml_mapping(bom_path.read_text(encoding="utf-8"))
    document = VehicleDefinition.model_validate(bom)
    rows = [_part_row(part.model_dump(mode="json")) for part in document.parts]
    total_mass_kg = sum(row["mass_kg"] for row in rows)
    return {
        "valid": True,
        "path": _editable_or_raise("bom").relative_path,
        "total_mass_kg": total_mass_kg,
        "part_count": len(rows),
        "rows": rows,
        "state_counts": {
            state_tag: sum(1 for row in rows if row["state_tag"] == state_tag)
            for state_tag in ("fixed", "propellant", "CO2", "deployable-leg")
        },
    }


def save_rocket_parts(repo_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Save edited BOM part rows while preserving advanced per-part model data."""

    rows = payload.get("parts")
    if not isinstance(rows, list) or not rows:
        msg = "parts payload must contain a non-empty parts list"
        raise ValueError(msg)

    bom_path = _resolve_editable_path(repo_root, _editable_or_raise("bom"))
    bom = _yaml_mapping(bom_path.read_text(encoding="utf-8"))
    current_parts = bom.get("parts")
    if not isinstance(current_parts, list):
        msg = "BOM document must contain a parts list"
        raise ValueError(msg)
    by_id = {
        part.get("id"): part
        for part in current_parts
        if isinstance(part, dict) and isinstance(part.get("id"), str)
    }

    edited_parts: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            msg = "each part row must be a mapping"
            raise TypeError(msg)
        original_id = _payload_text(row, "original_id")
        base = by_id.get(original_id)
        if base is None:
            msg = f"unknown original part id: {original_id}"
            raise ValueError(msg)
        part = dict(base)
        part["id"] = _payload_text(row, "id")
        part["material"] = _payload_text(row, "material")
        part["state_tag"] = _payload_state_tag(row)
        part["mass_kg"] = _positive_payload_float(row, "mass_kg")
        part["position_m"] = [
            _finite_payload_float(row, "position_x_m"),
            _finite_payload_float(row, "position_y_m"),
            _finite_payload_float(row, "position_z_m"),
        ]
        edited_parts.append(part)

    bom["parts"] = edited_parts
    dumped = _dump_yaml(bom)
    validation = validate_workbench_text("bom", dumped)
    if not validation["valid"]:
        raise ValueError(validation["message"])
    bom_path.write_text(dumped, encoding="utf-8")
    state = rocket_parts_state(repo_root)
    state["updated_file"] = _editable_or_raise("bom").relative_path
    return state


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


def _load_builder_documents(repo_root: Path) -> dict[str, dict[str, Any]]:
    return {
        name: _yaml_mapping(
            _resolve_editable_path(repo_root, _editable_or_raise(name)).read_text(
                encoding="utf-8"
            )
        )
        for name in ("vehicle", "bom", "motor", "coldgas", "aero", "control", "sim")
    }


def _dump_yaml(document: dict[str, Any]) -> str:
    return yaml.safe_dump(
        document,
        allow_unicode=False,
        default_flow_style=False,
        sort_keys=False,
    )


def _positive_payload_float(payload: dict[str, Any], key: str) -> float:
    value = _required_payload_value(payload, key)
    if isinstance(value, bool):
        msg = f"{key} must be a number"
        raise TypeError(msg)
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        msg = f"{key} must be a positive number"
        raise ValueError(msg)
    return number


def _nonnegative_payload_int(payload: dict[str, Any], key: str) -> int:
    value = _required_payload_value(payload, key)
    if isinstance(value, bool):
        msg = f"{key} must be an integer"
        raise TypeError(msg)
    number = int(value)
    if number < 0:
        msg = f"{key} must be non-negative"
        raise ValueError(msg)
    return number


def _payload_text(payload: dict[str, Any], key: str) -> str:
    value = _required_payload_value(payload, key)
    if not isinstance(value, str) or not value.strip():
        msg = f"{key} must be non-empty text"
        raise ValueError(msg)
    return value.strip()


def _finite_payload_float(payload: dict[str, Any], key: str) -> float:
    value = _required_payload_value(payload, key)
    if isinstance(value, bool):
        msg = f"{key} must be a number"
        raise TypeError(msg)
    number = float(value)
    if not math.isfinite(number):
        msg = f"{key} must be finite"
        raise ValueError(msg)
    return number


def _payload_state_tag(payload: dict[str, Any]) -> str:
    value = _payload_text(payload, "state_tag")
    if value not in ("fixed", "propellant", "CO2", "deployable-leg"):
        msg = "state_tag must be fixed, propellant, CO2, or deployable-leg"
        raise ValueError(msg)
    return value


def _required_payload_value(payload: dict[str, Any], key: str) -> Any:
    if key not in payload or payload[key] in (None, ""):
        msg = f"{key} is required"
        raise ValueError(msg)
    return payload[key]


def _load_motor_curve_from_text(suffix: str, text: str) -> Any:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix) as handle:
        handle.write(text)
        handle.flush()
        if suffix.lower() == ".rse":
            return parse_rse(Path(handle.name))
        return parse_eng(Path(handle.name))


def _part_row(part: dict[str, Any]) -> dict[str, Any]:
    position = part.get("position_m", [0.0, 0.0, 0.0])
    advanced = [
        key
        for key in ("inertia_kg_m2", "depletion", "position_profile", "deployable_leg")
        if part.get(key) not in (None, ZERO_ADVANCED.get(key))
    ]
    return {
        "original_id": part["id"],
        "id": part["id"],
        "material": part["material"],
        "state_tag": part["state_tag"],
        "mass_kg": float(part["mass_kg"]),
        "position_x_m": float(position[0]),
        "position_y_m": float(position[1]),
        "position_z_m": float(position[2]),
        "advanced": advanced,
    }


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

ZERO_ADVANCED = {
    "inertia_kg_m2": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
}
