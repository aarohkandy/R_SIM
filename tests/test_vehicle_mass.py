from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from rocketsim.vehicle import (
    DepletionProfile,
    DeployableLegKinematics,
    PartDefinition,
    VehicleDefinition,
    VehicleModel,
    load_vehicle_definition,
    mass_properties,
    properties_as_dict,
)

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden" / "phase1_mass_properties.json"


def canonical_vehicle() -> VehicleDefinition:
    return VehicleDefinition(
        schema_version=1,
        name="canonical",
        description="Hand-checkable two point masses with one depleting mass.",
        placeholder=False,
        parts=(
            PartDefinition(
                id="fixed",
                material="test",
                mass_kg=2.0,
                position_m=(1.0, 0.0, 0.0),
                state_tag="fixed",
            ),
            PartDefinition(
                id="propellant",
                material="test",
                mass_kg=1.0,
                position_m=(-1.0, 0.0, 0.0),
                state_tag="propellant",
                depletion=DepletionProfile.model_validate(
                    {
                        "points": [
                            {"time_s": 0.0, "remaining_fraction": 1.0},
                            {"time_s": 10.0, "remaining_fraction": 0.0},
                        ]
                    }
                ),
            ),
        ),
    )


def test_known_parts_match_hand_checked_center_of_mass_and_inertia() -> None:
    vehicle = VehicleModel(canonical_vehicle())

    props = vehicle.mass_properties(0.0)

    assert props.mass_kg == pytest.approx(3.0)
    np.testing.assert_allclose(props.center_of_mass_m, np.array([1.0 / 3.0, 0.0, 0.0]))
    np.testing.assert_allclose(
        props.inertia_tensor_kg_m2,
        np.diag([0.0, 8.0 / 3.0, 8.0 / 3.0]),
        atol=1.0e-12,
    )


def test_depletion_changes_mass_and_center_of_mass_monotonically() -> None:
    vehicle = VehicleModel(canonical_vehicle())
    times = np.linspace(0.0, 10.0, 11)
    masses = [vehicle.mass_properties(float(t)).mass_kg for t in times]
    cg_x = [vehicle.mass_properties(float(t)).center_of_mass_m[0] for t in times]

    assert masses == sorted(masses, reverse=True)
    assert cg_x == sorted(cg_x)
    assert masses[0] == pytest.approx(3.0)
    assert masses[-1] == pytest.approx(2.0)


def test_spec_facing_mass_properties_function() -> None:
    props = mass_properties(5.0, canonical_vehicle())

    assert props.mass_kg == pytest.approx(2.5)
    np.testing.assert_allclose(props.center_of_mass_m, np.array([0.6, 0.0, 0.0]))
    np.testing.assert_allclose(props.inertia_tensor_kg_m2, np.diag([0.0, 1.6, 1.6]))


def test_deployable_leg_moves_continuously_and_changes_inertia() -> None:
    leg = DeployableLegKinematics(
        hinge_position_m=(0.0, 0.0, 0.0),
        axial_unit=(0.0, 0.0, -1.0),
        radial_unit=(1.0, 0.0, 0.0),
        length_m=2.0,
        stowed_angle_deg=0.0,
        deployed_angle_deg=90.0,
        deploy_start_s=1.0,
        deploy_duration_s=2.0,
    )
    vehicle = VehicleDefinition(
        schema_version=1,
        name="leg_case",
        description="One fixed mass and one deployable leg.",
        placeholder=False,
        parts=(
            PartDefinition(
                id="body",
                material="test",
                mass_kg=1.0,
                position_m=(0.0, 0.0, 0.0),
                state_tag="fixed",
            ),
            PartDefinition(
                id="leg",
                material="test",
                mass_kg=1.0,
                position_m=(0.0, 0.0, -1.0),
                state_tag="deployable-leg",
                deployable_leg=leg,
            ),
        ),
    )
    model = VehicleModel(vehicle)

    stowed = model.mass_properties(0.0)
    mid = model.mass_properties(2.0)
    deployed = model.mass_properties(3.0)

    np.testing.assert_allclose(stowed.part_states[1].position_m, (0.0, 0.0, -1.0), atol=1.0e-12)
    np.testing.assert_allclose(
        mid.part_states[1].position_m,
        (math.sqrt(0.5), 0.0, -math.sqrt(0.5)),
        atol=1.0e-12,
    )
    np.testing.assert_allclose(deployed.part_states[1].position_m, (1.0, 0.0, 0.0), atol=1.0e-12)
    assert not np.allclose(stowed.inertia_tensor_kg_m2, deployed.inertia_tensor_kg_m2)


def test_placeholder_bom_loads_and_depletes() -> None:
    model = VehicleModel.from_bom_path(ROOT / "inputs" / "bom_placeholder.yaml")

    initial = model.mass_properties(0.0)
    later = model.mass_properties(15.0)

    assert later.mass_kg < initial.mass_kg
    assert len(initial.part_states) == 8
    assert {state.state_tag for state in initial.part_states} >= {
        "fixed",
        "propellant",
        "CO2",
        "deployable-leg",
    }


def test_regression_golden_mass_properties() -> None:
    model = VehicleModel(canonical_vehicle())
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    for key, time_s in {"canonical_t0": 0.0, "canonical_midburn": 5.0}.items():
        props = properties_as_dict(model.mass_properties(time_s))
        assert props["mass_kg"] == pytest.approx(golden[key]["mass_kg"])
        np.testing.assert_allclose(props["center_of_mass_m"], golden[key]["center_of_mass_m"])
        np.testing.assert_allclose(
            props["inertia_tensor_kg_m2"],
            golden[key]["inertia_tensor_kg_m2"],
        )


@given(
    t1=st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    t2=st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False),
)
def test_property_total_mass_never_increases_with_depletion(t1: float, t2: float) -> None:
    model = VehicleModel.from_bom_path(ROOT / "inputs" / "bom_placeholder.yaml")
    earlier, later = sorted((t1, t2))

    earlier_mass = model.mass_properties(earlier).mass_kg
    later_mass = model.mass_properties(later).mass_kg

    assert later_mass <= earlier_mass + 1.0e-12


@given(t_s=st.floats(min_value=0.0, max_value=20.0, allow_nan=False, allow_infinity=False))
def test_property_inertia_is_symmetric_positive_semidefinite(t_s: float) -> None:
    model = VehicleModel.from_bom_path(ROOT / "inputs" / "bom_placeholder.yaml")
    inertia = model.mass_properties(t_s).inertia_tensor_kg_m2

    np.testing.assert_allclose(inertia, inertia.T, atol=1.0e-12)
    assert np.all(np.linalg.eigvalsh(inertia) >= -1.0e-12)


def test_invalid_depletion_profile_rejected() -> None:
    with pytest.raises(ValidationError, match="monotonically non-increasing"):
        DepletionProfile.model_validate(
            {
                "points": [
                    {"time_s": 0.0, "remaining_fraction": 0.5},
                    {"time_s": 1.0, "remaining_fraction": 0.6},
                ]
            }
        )


def test_depleting_parts_require_depletion_profile() -> None:
    with pytest.raises(ValidationError, match="require a depletion profile"):
        PartDefinition(
            id="co2",
            material="carbon_dioxide",
            mass_kg=1.0,
            position_m=(0.0, 0.0, 0.0),
            state_tag="CO2",
        )


def test_deployable_legs_require_kinematics() -> None:
    with pytest.raises(ValidationError, match="require deployable_leg kinematics"):
        PartDefinition(
            id="leg",
            material="petg",
            mass_kg=1.0,
            position_m=(0.0, 0.0, 0.0),
            state_tag="deployable-leg",
        )


def test_duplicate_part_ids_rejected() -> None:
    part = PartDefinition(
        id="duplicate",
        material="test",
        mass_kg=1.0,
        position_m=(0.0, 0.0, 0.0),
        state_tag="fixed",
    )

    with pytest.raises(ValidationError, match="part ids must be unique"):
        VehicleDefinition(
            schema_version=1,
            name="duplicate_case",
            description="Invalid duplicate ids.",
            placeholder=False,
            parts=(part, part),
        )


def test_invalid_bom_yaml_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(TypeError, match="must contain a YAML mapping"):
        load_vehicle_definition(invalid)
