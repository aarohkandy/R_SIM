"""Mass property calculations for the vehicle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from numpy.typing import NDArray

from rocketsim.vehicle.schema import PartDefinition, VehicleDefinition


@dataclass(frozen=True)
class PartMassState:
    """Mass and center of mass for one part at a specific time."""

    id: str
    state_tag: str
    mass_kg: float
    nominal_mass_kg: float
    position_m: tuple[float, float, float]
    remaining_fraction: float


@dataclass(frozen=True)
class MassProperties:
    """Vehicle mass properties about the instantaneous center of mass."""

    mass_kg: float
    center_of_mass_m: NDArray[np.float64]
    inertia_tensor_kg_m2: NDArray[np.float64]
    part_states: tuple[PartMassState, ...]


class VehicleModel:
    """Config-driven mass property model."""

    def __init__(self, definition: VehicleDefinition) -> None:
        self.definition = definition

    @classmethod
    def from_bom_path(cls, path: Path | str) -> VehicleModel:
        return cls(load_vehicle_definition(path))

    def part_states_at(self, t_s: float) -> tuple[PartMassState, ...]:
        if t_s < 0.0:
            msg = "time must be non-negative"
            raise ValueError(msg)
        states: list[PartMassState] = []
        for part in self.definition.parts:
            remaining_fraction = part.remaining_fraction_at(t_s)
            states.append(
                PartMassState(
                    id=part.id,
                    state_tag=part.state_tag,
                    mass_kg=part.mass_at(t_s),
                    nominal_mass_kg=part.mass_kg,
                    position_m=part.position_at(t_s),
                    remaining_fraction=remaining_fraction,
                )
            )
        return tuple(states)

    def mass_properties(self, t_s: float) -> MassProperties:
        states = self.part_states_at(t_s)
        masses = np.asarray([state.mass_kg for state in states], dtype=np.float64)
        if np.any(masses < -1.0e-12):
            msg = "part masses must be non-negative"
            raise ValueError(msg)
        total_mass = float(np.sum(masses))
        if total_mass <= 0.0:
            msg = "vehicle mass must stay positive"
            raise ValueError(msg)

        positions = np.asarray([state.position_m for state in states], dtype=np.float64)
        center_of_mass = np.sum(masses[:, np.newaxis] * positions, axis=0) / total_mass
        inertia = inertia_tensor_about_point(self.definition.parts, states, center_of_mass)

        return MassProperties(
            mass_kg=total_mass,
            center_of_mass_m=center_of_mass,
            inertia_tensor_kg_m2=inertia,
            part_states=states,
        )


def load_vehicle_definition(path: Path | str) -> VehicleDefinition:
    """Load a strict vehicle/BOM definition from YAML."""

    vehicle_path = Path(path)
    raw = yaml.safe_load(vehicle_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{vehicle_path} must contain a YAML mapping"
        raise TypeError(msg)
    return VehicleDefinition.model_validate(raw)


def mass_properties(t_s: float, config_state: VehicleDefinition) -> MassProperties:
    """SPEC-facing convenience function for instantaneous vehicle mass properties."""

    return VehicleModel(config_state).mass_properties(t_s)


def inertia_tensor_about_point(
    parts: tuple[PartDefinition, ...],
    states: tuple[PartMassState, ...],
    reference_point_m: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Compute the full inertia tensor about a reference point."""

    inertia = np.zeros((3, 3), dtype=np.float64)
    identity = np.eye(3, dtype=np.float64)
    for part, state in zip(parts, states, strict=True):
        mass = state.mass_kg
        if mass <= 0.0:
            continue
        position = np.asarray(state.position_m, dtype=np.float64)
        offset = position - reference_point_m
        intrinsic = np.asarray(part.inertia_kg_m2, dtype=np.float64) * (mass / part.mass_kg)
        parallel_axis = mass * ((float(offset @ offset) * identity) - np.outer(offset, offset))
        inertia += intrinsic + parallel_axis
    return np.asarray(0.5 * (inertia + inertia.T), dtype=np.float64)


def properties_as_dict(properties: MassProperties) -> dict[str, Any]:
    """Return deterministic, JSON-friendly mass property data for reports/goldens."""

    return {
        "mass_kg": properties.mass_kg,
        "center_of_mass_m": properties.center_of_mass_m.tolist(),
        "inertia_tensor_kg_m2": properties.inertia_tensor_kg_m2.tolist(),
        "part_states": [
            {
                "id": state.id,
                "state_tag": state.state_tag,
                "mass_kg": state.mass_kg,
                "position_m": list(state.position_m),
                "remaining_fraction": state.remaining_fraction,
            }
            for state in properties.part_states
        ],
    }
