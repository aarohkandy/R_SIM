from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rocketsim.propulsion import (
    ColdGasConfig,
    ColdGasSystem,
    co2_gamma_and_specific_gas_constant,
    co2_saturation_pressure_pa,
    load_coldgas_config,
)
from rocketsim.vehicle import DepletionProfile, PartDefinition, VehicleDefinition, VehicleModel

ROOT = Path(__file__).resolve().parents[1]
COLDGAS_CONFIG = ROOT / "config" / "coldgas.yaml"
GOLDEN = ROOT / "tests" / "golden" / "phase5_coldgas.json"


def system() -> ColdGasSystem:
    return ColdGasSystem.from_config_path(COLDGAS_CONFIG)


def test_coldgas_config_loads() -> None:
    config = load_coldgas_config(COLDGAS_CONFIG)

    assert config.data.tank.initial_co2_mass_kg == pytest.approx(0.088)
    assert len(config.data.nozzles.items) == 3


def test_coolprop_reference_properties_match_golden() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    gamma, specific_r = co2_gamma_and_specific_gas_constant(293.15, 827371.0)

    assert co2_saturation_pressure_pa(293.15) == pytest.approx(
        golden["saturation_pressure_293_15_pa"]
    )
    assert gamma == pytest.approx(golden["gamma_at_regulator"])
    assert specific_r == pytest.approx(golden["specific_gas_constant_j_kg_k"])


def test_initial_state_is_saturated_liquid_vapor() -> None:
    state = system().initial_state()
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["initial"]

    assert state.liquid_mass_kg > 0.0
    assert state.vapor_mass_kg > 0.0
    assert state.pressure_pa == pytest.approx(co2_saturation_pressure_pa(state.temperature_k))
    assert state.total_mass_kg == pytest.approx(golden["total_mass_kg"])
    assert state.liquid_mass_kg == pytest.approx(golden["liquid_mass_kg"])
    assert state.vapor_mass_kg == pytest.approx(golden["vapor_mass_kg"])


def test_single_nozzle_thrust_matches_golden_and_isp_is_sane() -> None:
    coldgas = system()
    forces = coldgas.thrust_and_torque((True, False, False), 0.0, coldgas.initial_state())
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["one_nozzle"]
    isp_s = forces.total_thrust_n / (forces.total_mass_flow_kg_s * 9.80665)

    assert forces.total_mass_flow_kg_s == pytest.approx(golden["mass_flow_kg_s"])
    assert forces.total_thrust_n == pytest.approx(golden["thrust_n"])
    np.testing.assert_allclose(forces.force_body_n, golden["force_body_n"])
    np.testing.assert_allclose(forces.torque_body_n, golden["torque_body_n"])
    assert forces.regulator.output_pressure_pa == pytest.approx(golden["output_pressure_pa"])
    assert 20.0 <= isp_s <= 100.0
    assert forces.flows[0].choked


def test_three_nozzle_step_cools_and_closes_mass_energy_balance() -> None:
    coldgas = system()
    initial = coldgas.initial_state()
    result = coldgas.step(initial, (True, True, True), 0.1)
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["three_nozzle_step_0_1s"]

    assert result.mass_out_kg == pytest.approx(golden["mass_out_kg"])
    assert result.state.total_mass_kg < initial.total_mass_kg
    assert result.state.temperature_k < initial.temperature_k
    assert result.state.pressure_pa == pytest.approx(
        co2_saturation_pressure_pa(result.state.temperature_k)
    )
    assert abs(result.mass_balance_residual_kg) <= 1.0e-12
    assert abs(result.energy_balance_residual_j) <= 1.0e-6
    assert result.state.temperature_k == pytest.approx(golden["temperature_k"])
    assert result.state.pressure_pa == pytest.approx(golden["pressure_pa"])


def test_pressure_sag_exhibits_when_draw_exceeds_supply() -> None:
    base = load_coldgas_config(COLDGAS_CONFIG).model_dump(mode="python")
    for nozzle in base["data"]["nozzles"]["items"]:
        nozzle["throat_area_m2"] = 0.001
    oversized = ColdGasSystem(ColdGasConfig.model_validate(base))
    forces = oversized.thrust_and_torque((True, True, True), 0.0, oversized.initial_state())

    assert forces.regulator.sag_factor < 1.0
    assert forces.regulator.output_pressure_pa < oversized.config.data.regulator.setpoint_pa


def test_closed_valves_emit_zero_force_and_flow() -> None:
    coldgas = system()
    forces = coldgas.thrust_and_torque((False, False, False), 0.0, coldgas.initial_state())

    assert forces.total_mass_flow_kg_s == pytest.approx(0.0)
    assert forces.total_thrust_n == pytest.approx(0.0)
    np.testing.assert_array_equal(forces.force_body_n, np.zeros(3))
    np.testing.assert_array_equal(forces.torque_body_n, np.zeros(3))


def test_coldgas_mass_depletion_couples_to_vehicle_mass_properties() -> None:
    coldgas = system()
    initial = coldgas.initial_state()
    result = coldgas.step(initial, (True, True, True), 0.1)
    depletion = DepletionProfile.model_validate(
        {
            "points": [
                {"time_s": initial.time_s, "remaining_fraction": 1.0},
                {
                    "time_s": result.state.time_s,
                    "remaining_fraction": result.state.total_mass_kg / initial.total_mass_kg,
                },
            ]
        }
    )
    vehicle = VehicleModel(
        VehicleDefinition(
            schema_version=1,
            name="coldgas_vehicle",
            description="CO2 depletion coupling.",
            placeholder=False,
            parts=(
                PartDefinition(
                    id="structure",
                    material="test",
                    mass_kg=1.0,
                    position_m=(0.0, 0.0, 0.0),
                    state_tag="fixed",
                ),
                PartDefinition(
                    id="co2",
                    material="carbon_dioxide",
                    mass_kg=initial.total_mass_kg,
                    position_m=(0.0, 0.0, 0.1),
                    state_tag="CO2",
                    depletion=depletion,
                ),
            ),
        )
    )

    assert vehicle.mass_properties(result.state.time_s).mass_kg == pytest.approx(
        1.0 + result.state.total_mass_kg
    )


@given(dt_s=st.floats(min_value=0.001, max_value=0.2, allow_nan=False, allow_infinity=False))
def test_property_step_mass_and_energy_balance(dt_s: float) -> None:
    coldgas = system()
    result = coldgas.step(coldgas.initial_state(), (True, False, True), dt_s)

    assert abs(result.mass_balance_residual_kg) <= 1.0e-12
    assert abs(result.energy_balance_residual_j) <= 1.0e-5
    assert result.state.total_mass_kg <= coldgas.initial_state().total_mass_kg


def test_valve_count_must_match_nozzles() -> None:
    coldgas = system()

    with pytest.raises(ValueError, match="valve state count must match nozzle count"):
        coldgas.thrust_and_torque((True,), 0.0, coldgas.initial_state())


def test_invalid_coldgas_yaml_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(TypeError, match="must contain a YAML mapping"):
        load_coldgas_config(invalid)
