from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from rocketsim.environment import (
    EnvironmentModel,
    GustDefinition,
    LaunchRail,
    LaunchRailDefinition,
    WindDefinition,
    WindModel,
    gust_velocity,
    load_environment_definition,
)

ROOT = Path(__file__).resolve().parents[1]
ENV_CONFIG = ROOT / "config" / "environment.yaml"
ISA_GOLDEN = ROOT / "tests" / "golden" / "phase2_isa_reference.json"


def test_environment_config_loads() -> None:
    definition = load_environment_definition(ENV_CONFIG)

    assert definition.data.atmosphere.kind == "ISA"
    assert definition.data.launch_rail.length_m == pytest.approx(1.0)


def test_isa_matches_reference_table() -> None:
    model = EnvironmentModel.from_config_path(ENV_CONFIG)
    golden = json.loads(ISA_GOLDEN.read_text(encoding="utf-8"))

    for altitude_text, expected in golden.items():
        state = model.atmosphere.state_at(float(altitude_text))
        assert state.temperature_k == pytest.approx(expected["temperature_k"], rel=1.0e-12)
        assert state.pressure_pa == pytest.approx(expected["pressure_pa"], rel=1.0e-12)
        assert state.density_kg_m3 == pytest.approx(expected["density_kg_m3"], rel=1.0e-12)
        assert state.speed_of_sound_m_s == pytest.approx(
            expected["speed_of_sound_m_s"],
            rel=1.0e-12,
        )


@given(
    low=st.floats(min_value=0.0, max_value=9000.0, allow_nan=False, allow_infinity=False),
    high=st.floats(min_value=0.0, max_value=9000.0, allow_nan=False, allow_infinity=False),
)
def test_property_pressure_and_density_decrease_in_troposphere(low: float, high: float) -> None:
    model = EnvironmentModel.from_config_path(ENV_CONFIG)
    lower, higher = sorted((low, high))

    lower_state = model.atmosphere.state_at(lower)
    higher_state = model.atmosphere.state_at(higher)

    assert higher_state.pressure_pa <= lower_state.pressure_pa + 1.0e-9
    assert higher_state.density_kg_m3 <= lower_state.density_kg_m3 + 1.0e-12


def test_disabled_wind_is_zero() -> None:
    model = EnvironmentModel.from_config_path(ENV_CONFIG)

    np.testing.assert_array_equal(model.wind.velocity_at(100.0, 5.0), np.zeros(3))


def test_steady_wind_shear_and_gust_are_deterministic() -> None:
    gust = GustDefinition(start_s=2.0, duration_s=4.0, amplitude_m_s=(3.0, 0.0, 0.0))
    wind = WindModel(
        WindDefinition(
            enabled=True,
            steady_m_s=(5.0, 0.0, 0.0),
            shear_reference_altitude_m=10.0,
            shear_exponent=0.2,
            gusts=(gust,),
        )
    )

    at_reference = wind.velocity_at(10.0, 0.0)
    at_mid_gust = wind.velocity_at(10.0, 4.0)
    repeat = wind.velocity_at(10.0, 4.0)

    np.testing.assert_allclose(at_reference, (5.0, 0.0, 0.0))
    np.testing.assert_allclose(at_mid_gust, (8.0, 0.0, 0.0), atol=1.0e-12)
    np.testing.assert_array_equal(at_mid_gust, repeat)


def test_one_cosine_gust_is_zero_at_boundaries_and_peaks_midway() -> None:
    gust = GustDefinition(start_s=10.0, duration_s=2.0, amplitude_m_s=(0.0, 4.0, 0.0))

    np.testing.assert_allclose(gust_velocity(gust, 10.0), np.zeros(3))
    np.testing.assert_allclose(gust_velocity(gust, 11.0), (0.0, 4.0, 0.0))
    np.testing.assert_allclose(gust_velocity(gust, 12.0), np.zeros(3))


def test_launch_rail_constraint_and_exit_velocity_report() -> None:
    rail = LaunchRail(
        LaunchRailDefinition(
            length_m=2.0,
            angle_from_vertical_deg=30.0,
            minimum_exit_speed_mps=12.0,
        )
    )

    assert rail.is_constrained(1.5)
    assert not rail.is_constrained(2.0)
    np.testing.assert_allclose(rail.direction_m, (0.5, 0.0, np.sqrt(3.0) / 2.0), atol=1.0e-12)
    np.testing.assert_allclose(
        rail.position_at_distance(3.0),
        np.array((1.0, 0.0, np.sqrt(3.0))),
        atol=1.0e-12,
    )
    assert not rail.exit_report(11.9).is_sane
    assert rail.exit_report(12.0).is_sane


def test_invalid_gust_rejected() -> None:
    with pytest.raises(ValidationError, match="gust amplitude must be non-zero"):
        GustDefinition(start_s=0.0, duration_s=1.0, amplitude_m_s=(0.0, 0.0, 0.0))


def test_invalid_environment_yaml_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(TypeError, match="must contain a YAML mapping"):
        load_environment_definition(invalid)
