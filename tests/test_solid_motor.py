from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rocketsim.propulsion import (
    SolidMotor,
    ThrustCurvePoint,
    impulse_class_bounds,
    load_configured_motor,
    load_motor_config,
    load_solid_motor,
    parse_eng,
    parse_rse,
)
from rocketsim.vehicle import PartDefinition, VehicleDefinition, VehicleModel

ROOT = Path(__file__).resolve().parents[1]
MOTOR_CONFIG = ROOT / "config" / "motor.yaml"
MOTOR_ENG = ROOT / "inputs" / "motor_D21_placeholder.eng"
GOLDEN = ROOT / "tests" / "golden" / "phase4_solid_motor.json"


def test_motor_config_loads() -> None:
    config = load_motor_config(MOTOR_CONFIG)

    assert config.data.thrust_curve_path == "inputs/motor_D21_placeholder.eng"
    assert config.data.declared_total_impulse_ns == pytest.approx(20.1)


def test_parse_eng_placeholder_and_impulse_matches_declared() -> None:
    motor = load_configured_motor(MOTOR_CONFIG)

    assert motor.metadata.designation == "D21_PLACEHOLDER"
    assert motor.metadata.propellant_mass_kg == pytest.approx(0.025)
    assert motor.metadata.total_mass_kg == pytest.approx(0.05)
    assert motor.total_impulse_ns == pytest.approx(20.1)
    motor.assert_declared_impulse_matches(tolerance_ns=1.0e-9)


def test_solid_motor_matches_golden_reference() -> None:
    motor = load_configured_motor(MOTOR_CONFIG)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert motor.metadata.designation == golden["designation"]
    assert motor.total_impulse_ns == pytest.approx(golden["total_impulse_ns"])
    assert motor.average_thrust_n == pytest.approx(golden["average_thrust_n"])
    for time_text, expected in golden["samples"].items():
        t_s = float(time_text)
        assert motor.thrust_at(t_s) == pytest.approx(expected["thrust_n"])
        assert motor.cumulative_impulse_at(t_s) == pytest.approx(
            expected["cumulative_impulse_ns"]
        )
        assert motor.propellant_remaining_mass_kg(t_s) == pytest.approx(
            expected["propellant_remaining_kg"]
        )
        assert motor.mass_flow_kg_s(t_s) == pytest.approx(expected["mass_flow_kg_s"])


def test_thrust_force_is_along_body_axis() -> None:
    motor = load_configured_motor(MOTOR_CONFIG)

    np.testing.assert_allclose(motor.thrust_force_body_n(0.3), (0.0, 0.0, 24.0))
    np.testing.assert_allclose(
        motor.thrust_force_body_n(0.3, axis=(0.0, 2.0, 0.0)),
        (0.0, 24.0, 0.0),
    )


def test_depletion_profile_couples_to_vehicle_mass_properties() -> None:
    motor = load_configured_motor(MOTOR_CONFIG)
    propellant = PartDefinition(
        id="motor_propellant",
        material="propellant",
        mass_kg=motor.metadata.propellant_mass_kg,
        position_m=(0.0, 0.0, -0.1),
        state_tag="propellant",
        depletion=motor.depletion_profile(),
    )
    shell = PartDefinition(
        id="shell",
        material="case",
        mass_kg=0.1,
        position_m=(0.0, 0.0, 0.0),
        state_tag="fixed",
    )
    vehicle = VehicleModel(
        VehicleDefinition(
            schema_version=1,
            name="motor_coupling",
            description="Motor depletion coupling.",
            placeholder=False,
            parts=(shell, propellant),
        )
    )

    initial = vehicle.mass_properties(0.0)
    burnout = vehicle.mass_properties(motor.burn_time_s)

    assert burnout.mass_kg == pytest.approx(initial.mass_kg - motor.metadata.propellant_mass_kg)
    assert burnout.part_states[1].remaining_fraction == pytest.approx(0.0)


def test_parse_minimal_rse(tmp_path: Path) -> None:
    rse = tmp_path / "test.rse"
    rse.write_text(
        """<?xml version="1.0"?>
<engine-database>
  <engine-list>
    <engine code="T10" mfg="Test" dia="18" len="70" initWt="100" propWt="20" Itot="10.0">
      <data>
        <eng-data t="0.0" f="0.0"/>
        <eng-data t="1.0" f="10.0"/>
        <eng-data t="2.0" f="0.0"/>
      </data>
    </engine>
  </engine-list>
</engine-database>
""",
        encoding="utf-8",
    )

    motor = parse_rse(rse)

    assert motor.metadata.designation == "T10"
    assert motor.metadata.propellant_mass_kg == pytest.approx(0.02)
    assert motor.metadata.total_mass_kg == pytest.approx(0.1)
    assert motor.total_impulse_ns == pytest.approx(10.0)
    motor.assert_declared_impulse_matches(tolerance_ns=1.0e-9)


@given(t_s=st.floats(min_value=0.0, max_value=1.2, allow_nan=False, allow_infinity=False))
def test_property_remaining_propellant_is_monotonic(t_s: float) -> None:
    motor = load_configured_motor(MOTOR_CONFIG)
    later = min(t_s + 0.001, motor.burn_time_s)

    assert (
        motor.propellant_remaining_mass_kg(later)
        <= motor.propellant_remaining_mass_kg(t_s) + 1.0e-12
    )


@given(t_s=st.floats(min_value=-1.0, max_value=2.0, allow_nan=False, allow_infinity=False))
def test_property_thrust_and_mass_flow_are_non_negative(t_s: float) -> None:
    motor = load_configured_motor(MOTOR_CONFIG)

    assert motor.thrust_at(t_s) >= 0.0
    assert motor.mass_flow_kg_s(t_s) >= 0.0


def test_impulse_class_bounds() -> None:
    assert impulse_class_bounds("D21") == (10.01, 20.0)
    assert impulse_class_bounds("UNKNOWN") is None


def test_declared_impulse_mismatch_rejected() -> None:
    motor = parse_eng(MOTOR_ENG, declared_total_impulse_ns=10.0)

    with pytest.raises(ValueError, match="differs from declared"):
        motor.assert_declared_impulse_matches(tolerance_ns=0.1)


def test_invalid_motor_extension_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.txt"
    bad.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported motor file extension"):
        load_solid_motor(bad)


def test_invalid_thrust_curve_rejected() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        SolidMotor(
            metadata=load_configured_motor(MOTOR_CONFIG).metadata,
            points=(
                ThrustCurvePoint(time_s=0.0, thrust_n=0.0),
                ThrustCurvePoint(time_s=0.0, thrust_n=1.0),
            ),
        )


def test_zero_thrust_axis_rejected() -> None:
    motor = load_configured_motor(MOTOR_CONFIG)

    with pytest.raises(ValueError, match="thrust axis must be non-zero"):
        motor.thrust_force_body_n(0.1, axis=(0.0, 0.0, 0.0))
