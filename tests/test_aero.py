from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rocketsim.aero import (
    AeroConfigurationState,
    AeroModel,
    compare_to_openrocket,
    compressibility_factor,
    deploy_angle_fraction,
    load_aero_definition,
    load_openrocket_anchors,
)
from rocketsim.vehicle import VehicleModel

ROOT = Path(__file__).resolve().parents[1]
AERO_CONFIG = ROOT / "config" / "aero.yaml"
BOM = ROOT / "inputs" / "bom_placeholder.yaml"
ANCHORS = ROOT / "inputs" / "openrocket" / "frozen_placeholder.csv"
GOLDEN = ROOT / "tests" / "golden" / "phase3_aero_reference.json"


def aero_states() -> dict[str, AeroConfigurationState]:
    return {
        "stowed_low_mach": AeroConfigurationState(
            mach=0.05,
            leg_deploy_angle_deg=0.0,
            cg_axial_m=0.0,
            propellant_remaining_fraction=1.0,
            co2_remaining_fraction=1.0,
        ),
        "mid_deploy": AeroConfigurationState(
            mach=0.10,
            leg_deploy_angle_deg=45.0,
            cg_axial_m=0.01,
            propellant_remaining_fraction=0.8,
            co2_remaining_fraction=0.9,
        ),
        "deployed_depleted": AeroConfigurationState(
            mach=0.20,
            leg_deploy_angle_deg=75.0,
            cg_axial_m=0.04,
            propellant_remaining_fraction=0.2,
            co2_remaining_fraction=0.5,
        ),
    }


def test_aero_config_loads() -> None:
    definition = load_aero_definition(AERO_CONFIG)

    assert definition.data.geometry.body_diameter_m == pytest.approx(0.063)
    assert definition.data.comparison.openrocket_anchor_dir == "inputs/openrocket"


def test_component_build_up_matches_golden_reference() -> None:
    model = AeroModel.from_config_path(AERO_CONFIG)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    for name, state in aero_states().items():
        result = model.evaluate(state)
        expected = golden[name]
        assert result.cp_axial_m == pytest.approx(expected["cp_axial_m"])
        assert result.cd == pytest.approx(expected["cd"])
        assert result.normal_force_slope_per_rad == pytest.approx(
            expected["normal_force_slope_per_rad"]
        )
        assert result.static_margin_calibers == pytest.approx(expected["static_margin_calibers"])
        assert result.reference_area_m2 == pytest.approx(expected["reference_area_m2"])


def test_leg_deployment_moves_cp_aft_and_increases_drag() -> None:
    model = AeroModel.from_config_path(AERO_CONFIG)
    stowed = model.evaluate(aero_states()["stowed_low_mach"])
    deployed = model.evaluate(aero_states()["deployed_depleted"])

    assert deployed.cp_axial_m < stowed.cp_axial_m
    assert deployed.cd > stowed.cd
    assert deployed.normal_force_slope_per_rad > stowed.normal_force_slope_per_rad


def test_depletion_changes_drag_and_static_margin_uses_live_cg() -> None:
    model = AeroModel.from_config_path(AERO_CONFIG)
    full = model.evaluate(
        AeroConfigurationState(
            mach=0.1,
            leg_deploy_angle_deg=45.0,
            cg_axial_m=0.0,
            propellant_remaining_fraction=1.0,
            co2_remaining_fraction=1.0,
        )
    )
    depleted = model.evaluate(
        AeroConfigurationState(
            mach=0.1,
            leg_deploy_angle_deg=45.0,
            cg_axial_m=0.04,
            propellant_remaining_fraction=0.0,
            co2_remaining_fraction=0.0,
        )
    )

    assert depleted.cd > full.cd
    assert depleted.static_margin_calibers > full.static_margin_calibers


def test_openrocket_anchor_comparison_is_within_tolerance() -> None:
    model = AeroModel.from_config_path(AERO_CONFIG)
    anchors = load_openrocket_anchors(ANCHORS)
    report = compare_to_openrocket(model, anchors)

    assert len(report.rows) == 3
    assert report.all_within_tolerance
    assert all(
        abs(row.cp_delta_m) <= model.definition.data.comparison.cp_tolerance_m
        for row in report.rows
    )
    assert all(
        abs(row.cd_delta) <= model.definition.data.comparison.cd_tolerance for row in report.rows
    )


def test_aero_state_from_vehicle_mass_properties_uses_live_depletion() -> None:
    aero = AeroModel.from_config_path(AERO_CONFIG)
    vehicle = VehicleModel.from_bom_path(BOM)

    initial = aero.state_from_mass_properties(
        vehicle.mass_properties(0.0),
        mach=0.1,
        leg_deploy_angle_deg=0.0,
    )
    later = aero.state_from_mass_properties(
        vehicle.mass_properties(15.0),
        mach=0.1,
        leg_deploy_angle_deg=75.0,
    )

    assert later.propellant_remaining_fraction < initial.propellant_remaining_fraction
    assert later.co2_remaining_fraction < initial.co2_remaining_fraction
    assert later.cg_axial_m != pytest.approx(initial.cg_axial_m)


def test_swing_test_restoring_metric_increases_with_static_margin() -> None:
    model = AeroModel.from_config_path(AERO_CONFIG)

    assert model.swing_test_restoring_metric(
        aero_states()["deployed_depleted"]
    ) > model.swing_test_restoring_metric(
        aero_states()["stowed_low_mach"],
    )


@given(angle=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False))
def test_property_deploy_angle_fraction_is_bounded(angle: float) -> None:
    fraction = deploy_angle_fraction(angle)

    assert 0.0 <= fraction <= 1.0


@given(mach=st.floats(min_value=0.0, max_value=0.94, allow_nan=False, allow_infinity=False))
def test_property_compressibility_factor_is_positive(mach: float) -> None:
    assert compressibility_factor(mach) >= 1.0


@given(
    mach=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
    angle=st.floats(min_value=0.0, max_value=90.0, allow_nan=False, allow_infinity=False),
    prop=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    co2=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_property_coefficients_stay_physical(
    mach: float,
    angle: float,
    prop: float,
    co2: float,
) -> None:
    model = AeroModel.from_config_path(AERO_CONFIG)
    result = model.evaluate(
        AeroConfigurationState(
            mach=mach,
            leg_deploy_angle_deg=angle,
            cg_axial_m=0.0,
            propellant_remaining_fraction=prop,
            co2_remaining_fraction=co2,
        )
    )

    assert np.isfinite(result.cp_axial_m)
    assert result.cd > 0.0
    assert result.normal_force_slope_per_rad > 0.0


def test_negative_mach_rejected() -> None:
    model = AeroModel.from_config_path(AERO_CONFIG)

    with pytest.raises(ValueError, match="Mach must be non-negative"):
        model.evaluate(
            AeroConfigurationState(
                mach=-0.1,
                leg_deploy_angle_deg=0.0,
                cg_axial_m=0.0,
                propellant_remaining_fraction=1.0,
                co2_remaining_fraction=1.0,
            )
        )


def test_invalid_openrocket_anchor_rejected(tmp_path: Path) -> None:
    bad_anchor = tmp_path / "bad.csv"
    bad_anchor.write_text("mach,cd\n0.1,0.4\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required OpenRocket anchor columns"):
        load_openrocket_anchors(bad_anchor)


def test_invalid_aero_yaml_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(TypeError, match="must contain a YAML mapping"):
        load_aero_definition(invalid)
