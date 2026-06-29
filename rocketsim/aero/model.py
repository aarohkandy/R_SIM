"""Live aerodynamic build-up model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from rocketsim.aero.schema import AeroDefinition
from rocketsim.vehicle.mass import MassProperties


@dataclass(frozen=True)
class AeroConfigurationState:
    """Runtime aerodynamic state; OpenRocket anchors never provide this at runtime."""

    mach: float
    leg_deploy_angle_deg: float
    cg_axial_m: float
    propellant_remaining_fraction: float
    co2_remaining_fraction: float


@dataclass(frozen=True)
class AeroResult:
    """Aerodynamic coefficients and stability data."""

    cp_axial_m: float
    cd: float
    normal_force_slope_per_rad: float
    static_margin_calibers: float
    reference_area_m2: float


class AeroModel:
    """Component build-up CP/Cd model as a function of live configuration state."""

    def __init__(self, definition: AeroDefinition) -> None:
        self.definition = definition

    @classmethod
    def from_config_path(cls, path: Path | str) -> AeroModel:
        return cls(load_aero_definition(path))

    def evaluate(self, state: AeroConfigurationState) -> AeroResult:
        """Compute live CP, Cd, and static margin."""

        if state.mach < 0.0:
            msg = "Mach must be non-negative"
            raise ValueError(msg)
        leg_fraction = deploy_angle_fraction(state.leg_deploy_angle_deg)
        geom = self.definition.data.geometry
        coeffs = self.definition.data.coefficients
        reference_area = math.pi * (0.5 * geom.body_diameter_m) ** 2

        body_cna = coeffs.body_normal_force_slope_per_rad
        leg_cna = (
            geom.leg_count
            * coeffs.leg_normal_force_slope_per_rad_each
            * leg_fraction
            * compressibility_factor(state.mach)
        )
        total_cna = body_cna + leg_cna
        cp_axial = (
            body_cna * geom.body_cp_axial_m + leg_cna * geom.leg_cp_axial_m
        ) / total_cna

        wetted_area = math.pi * geom.body_diameter_m * geom.body_length_m
        skin_cd = coeffs.skin_friction_coefficient * wetted_area / reference_area
        leg_cd = (
            geom.leg_count
            * coeffs.leg_drag_coefficient
            * geom.leg_reference_area_m2
            / reference_area
            * leg_fraction
        )
        depletion_empty_fraction = 1.0 - 0.5 * (
            state.propellant_remaining_fraction + state.co2_remaining_fraction
        )
        base_cd = (
            skin_cd
            + coeffs.pressure_drag_coefficient
            + coeffs.base_drag_coefficient
            + leg_cd
            + coeffs.depletion_drag_gain * max(0.0, depletion_empty_fraction)
        )
        cd = base_cd * (1.0 + coeffs.mach_drag_rise_factor * state.mach * state.mach)
        static_margin = (state.cg_axial_m - cp_axial) / geom.body_diameter_m

        return AeroResult(
            cp_axial_m=cp_axial,
            cd=cd,
            normal_force_slope_per_rad=total_cna,
            static_margin_calibers=static_margin,
            reference_area_m2=reference_area,
        )

    def state_from_mass_properties(
        self,
        mass_properties: MassProperties,
        mach: float,
        leg_deploy_angle_deg: float,
    ) -> AeroConfigurationState:
        """Build an aero state from live vehicle mass properties."""

        propellant = [
            state.remaining_fraction
            for state in mass_properties.part_states
            if state.state_tag == "propellant"
        ]
        co2 = [
            state.remaining_fraction
            for state in mass_properties.part_states
            if state.state_tag == "CO2"
        ]
        return AeroConfigurationState(
            mach=mach,
            leg_deploy_angle_deg=leg_deploy_angle_deg,
            cg_axial_m=float(mass_properties.center_of_mass_m[2]),
            propellant_remaining_fraction=float(np.mean(propellant)) if propellant else 1.0,
            co2_remaining_fraction=float(np.mean(co2)) if co2 else 1.0,
        )

    def swing_test_restoring_metric(self, state: AeroConfigurationState) -> float:
        """Return a deterministic restoring trend proxy for a modeled swing test."""

        result = self.evaluate(state)
        return result.normal_force_slope_per_rad * result.static_margin_calibers


def load_aero_definition(path: Path | str) -> AeroDefinition:
    """Load config/aero.yaml into a strict aero definition."""

    aero_path = Path(path)
    raw = yaml.safe_load(aero_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{aero_path} must contain a YAML mapping"
        raise TypeError(msg)
    return AeroDefinition.model_validate(raw)


def deploy_angle_fraction(angle_deg: float) -> float:
    """Map leg deployment angle to aerodynamic exposure fraction."""

    bounded_angle = min(max(angle_deg, 0.0), 90.0)
    return math.sin(math.radians(bounded_angle)) ** 2


def compressibility_factor(mach: float) -> float:
    """Subsonic Prandtl-Glauert-style normal-force slope factor."""

    bounded_mach = min(max(mach, 0.0), 0.95)
    return 1.0 / math.sqrt(1.0 - bounded_mach * bounded_mach)
