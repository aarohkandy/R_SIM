from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rocketsim.aero import AeroModel
from rocketsim.dynamics import (
    DynamicsPlant,
    ForceMoment,
    RigidBodyState,
    analytic_ballistic_position,
    inertial_angular_momentum,
    integrate_fixed_step,
    mechanical_energy_j,
    normalize_quaternion,
    rk4_step,
    rotate_body_to_inertial,
    rotate_inertial_to_body,
    trajectory_hash,
)
from rocketsim.environment import EnvironmentModel
from rocketsim.propulsion import ColdGasSystem, load_configured_motor
from rocketsim.sim import load_sim_config
from rocketsim.vehicle import VehicleModel

ROOT = Path(__file__).resolve().parents[1]
SIM_CONFIG = ROOT / "config" / "sim.yaml"
ENV_CONFIG = ROOT / "config" / "environment.yaml"
AERO_CONFIG = ROOT / "config" / "aero.yaml"
BOM = ROOT / "inputs" / "bom_placeholder.yaml"
MOTOR_CONFIG = ROOT / "config" / "motor.yaml"
COLDGAS_CONFIG = ROOT / "config" / "coldgas.yaml"
GOLDEN = ROOT / "tests" / "golden" / "phase6_dynamics.json"


def state(
    *,
    time_s: float = 0.0,
    position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0),
    attitude: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0),
    omega: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> RigidBodyState:
    return RigidBodyState(
        time_s=time_s,
        position_m=np.asarray(position, dtype=np.float64),
        velocity_m_s=np.asarray(velocity, dtype=np.float64),
        attitude_quat=np.asarray(attitude, dtype=np.float64),
        angular_velocity_rad_s=np.asarray(omega, dtype=np.float64),
    )


def constant_provider(
    *,
    mass_kg: float,
    inertia: np.ndarray,
    force: tuple[float, float, float] = (0.0, 0.0, 0.0),
    moment: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Callable[[RigidBodyState], ForceMoment]:
    def provider(_state: RigidBodyState) -> ForceMoment:
        return ForceMoment(
            force_inertial_n=np.asarray(force, dtype=np.float64),
            moment_body_n_m=np.asarray(moment, dtype=np.float64),
            mass_kg=mass_kg,
            inertia_tensor_kg_m2=inertia,
        )

    return provider


def test_sim_config_loads_phase6_dynamics_settings() -> None:
    config = load_sim_config(SIM_CONFIG)

    assert config.data.integrator_dt_s == pytest.approx(0.001)
    assert config.data.dynamics.minimum_aero_speed_m_s == pytest.approx(0.05)
    assert config.data.dynamics.motor_thrust_axis_unit == (0.0, 0.0, 1.0)


def test_quaternion_rotation_round_trip_and_normalization() -> None:
    q = normalize_quaternion((2.0, 0.0, 0.0, 0.0))
    vector = np.asarray((0.2, -0.4, 1.3), dtype=np.float64)

    inertial = rotate_body_to_inertial(q, vector)
    body = rotate_inertial_to_body(q, inertial)

    assert np.linalg.norm(q) == pytest.approx(1.0)
    np.testing.assert_allclose(body, vector, atol=1.0e-12)


def test_no_thrust_ballistic_matches_analytic_and_golden() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))["ballistic_1s"]
    mass = 2.0
    gravity = 9.80665
    inertia = np.diag([0.04, 0.05, 0.06])
    initial = state(position=(10.0, 0.0, 100.0), velocity=(3.0, -2.0, 40.0))
    provider = constant_provider(
        mass_kg=mass,
        inertia=inertia,
        force=(0.0, 0.0, -mass * gravity),
    )

    states = integrate_fixed_step(initial, duration_s=1.0, dt_s=0.01, provider=provider)
    final = states[-1]

    np.testing.assert_allclose(
        final.position_m,
        analytic_ballistic_position(initial.position_m, initial.velocity_m_s, 1.0, gravity),
        atol=1.0e-12,
    )
    np.testing.assert_allclose(final.position_m, golden["position_m"], atol=1.0e-12)
    np.testing.assert_allclose(final.velocity_m_s, golden["velocity_m_s"], atol=1.0e-12)
    assert mechanical_energy_j(final, mass, inertia, gravity) == pytest.approx(
        golden["mechanical_energy_j"],
        abs=1.0e-10,
    )


def test_torque_free_rotation_conserves_inertial_angular_momentum_and_energy() -> None:
    inertia = np.diag([0.06, 0.04, 0.03])
    initial = state(omega=(2.0, 3.0, 4.0))
    provider = constant_provider(mass_kg=1.5, inertia=inertia)

    states = integrate_fixed_step(initial, duration_s=0.5, dt_s=0.001, provider=provider)
    final = states[-1]

    np.testing.assert_allclose(
        inertial_angular_momentum(final, inertia),
        inertial_angular_momentum(initial, inertia),
        atol=2.0e-8,
    )
    assert mechanical_energy_j(final, 1.5, inertia, 0.0) == pytest.approx(
        mechanical_energy_j(initial, 1.5, inertia, 0.0),
        rel=1.0e-9,
    )
    assert not np.allclose(final.angular_velocity_rad_s, initial.angular_velocity_rad_s)


@settings(max_examples=40)
@given(
    wx=st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    wy=st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    wz=st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    dt_s=st.floats(min_value=0.0001, max_value=0.05, allow_nan=False, allow_infinity=False),
)
def test_property_rk4_step_preserves_unit_quaternion(
    wx: float,
    wy: float,
    wz: float,
    dt_s: float,
) -> None:
    inertia = np.eye(3)
    initial = state(omega=(wx, wy, wz))
    stepped = rk4_step(initial, dt_s, constant_provider(mass_kg=1.0, inertia=inertia))

    assert np.linalg.norm(stepped.attitude_quat) == pytest.approx(1.0, abs=1.0e-12)


def test_trajectory_hash_is_deterministic_and_state_sensitive() -> None:
    inertia = np.eye(3)
    initial = state(velocity=(1.0, 0.0, 0.0))
    provider = constant_provider(mass_kg=1.0, inertia=inertia)

    first = integrate_fixed_step(initial, duration_s=0.1, dt_s=0.01, provider=provider)
    second = integrate_fixed_step(initial, duration_s=0.1, dt_s=0.01, provider=provider)
    changed = integrate_fixed_step(
        state(velocity=(1.1, 0.0, 0.0)),
        duration_s=0.1,
        dt_s=0.01,
        provider=provider,
    )

    assert trajectory_hash(first) == trajectory_hash(second)
    assert trajectory_hash(first) != trajectory_hash(changed)


def test_dynamics_plant_assembles_live_forces_from_existing_modules() -> None:
    sim = load_sim_config(SIM_CONFIG)
    vehicle = VehicleModel.from_bom_path(BOM)
    environment = EnvironmentModel.from_config_path(ENV_CONFIG)
    aero = AeroModel.from_config_path(AERO_CONFIG)
    motor = load_configured_motor(MOTOR_CONFIG)
    coldgas = ColdGasSystem.from_config_path(COLDGAS_CONFIG)
    plant = DynamicsPlant(
        vehicle=vehicle,
        environment=environment,
        aero=aero,
        settings=sim.data.dynamics,
        motor=motor,
        coldgas=coldgas,
    )
    current = state(
        time_s=0.2,
        position=(0.0, 0.0, 1.0),
        velocity=(0.5, 0.0, 20.0),
        omega=(0.1, -0.2, 0.05),
    )

    forces = plant.force_moment(
        current,
        valve_states=(True, False, True),
        tank_state=coldgas.initial_state(),
    )
    advanced = plant.step(
        current,
        dt_s=sim.data.integrator_dt_s,
        valve_states=(True, False, True),
        tank_state=coldgas.initial_state(),
    )

    assert forces.mass_kg == pytest.approx(vehicle.mass_properties(current.time_s).mass_kg)
    assert forces.solid_thrust_body_n[2] > 0.0
    assert forces.coldgas is not None
    assert forces.coldgas.total_thrust_n > 0.0
    assert forces.dynamic_pressure_pa > 0.0
    assert forces.aero.cd > 0.0
    assert np.all(np.isfinite(forces.force_inertial_n))
    assert np.all(np.isfinite(forces.moment_body_n_m))
    assert np.all(np.isfinite(advanced.state_vector()))


def test_invalid_inputs_are_rejected() -> None:
    inertia = np.eye(3)

    with pytest.raises(ValueError, match="quaternion norm must be positive"):
        normalize_quaternion((0.0, 0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="dt_s must be positive"):
        rk4_step(state(), 0.0, constant_provider(mass_kg=1.0, inertia=inertia))
    with pytest.raises(ValueError, match="mass must be positive"):
        rk4_step(state(), 0.01, constant_provider(mass_kg=0.0, inertia=inertia))
