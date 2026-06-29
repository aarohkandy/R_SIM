"""Quaternion rigid-body dynamics and force assembly."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from rocketsim.aero import AeroModel, AeroResult
from rocketsim.environment import AtmosphereState, EnvironmentModel
from rocketsim.propulsion import CO2TankState, ColdGasForces, ColdGasSystem, SolidMotor
from rocketsim.sim import DynamicsSettings
from rocketsim.vehicle import MassProperties, VehicleDefinition, VehicleModel

Vector3Array = NDArray[np.float64]
ForceProvider = Callable[["RigidBodyState"], "ForceMoment"]


@dataclass(frozen=True)
class RigidBodyState:
    """Full 6-DOF rigid-body state.

    The attitude quaternion is stored as ``[w, x, y, z]`` and rotates body-frame vectors
    into the inertial frame. Body +z is the rocket axial direction.
    """

    time_s: float
    position_m: Vector3Array
    velocity_m_s: Vector3Array
    attitude_quat: Vector3Array
    angular_velocity_rad_s: Vector3Array

    def __post_init__(self) -> None:
        if self.time_s < 0.0:
            msg = "state time must be non-negative"
            raise ValueError(msg)
        _require_shape(self.position_m, (3,), "position_m")
        _require_shape(self.velocity_m_s, (3,), "velocity_m_s")
        _require_shape(self.attitude_quat, (4,), "attitude_quat")
        _require_shape(self.angular_velocity_rad_s, (3,), "angular_velocity_rad_s")
        if not np.all(np.isfinite(self.state_vector())):
            msg = "rigid-body state must be finite"
            raise ValueError(msg)

    def normalized(self) -> RigidBodyState:
        """Return this state with a unit-norm attitude quaternion."""

        return RigidBodyState(
            time_s=self.time_s,
            position_m=np.asarray(self.position_m, dtype=np.float64),
            velocity_m_s=np.asarray(self.velocity_m_s, dtype=np.float64),
            attitude_quat=normalize_quaternion(self.attitude_quat),
            angular_velocity_rad_s=np.asarray(self.angular_velocity_rad_s, dtype=np.float64),
        )

    def state_vector(self) -> Vector3Array:
        """Return a deterministic numeric vector for hashing and goldens."""

        return np.concatenate(
            (
                np.asarray([self.time_s], dtype=np.float64),
                np.asarray(self.position_m, dtype=np.float64),
                np.asarray(self.velocity_m_s, dtype=np.float64),
                np.asarray(self.attitude_quat, dtype=np.float64),
                np.asarray(self.angular_velocity_rad_s, dtype=np.float64),
            )
        )


@dataclass(frozen=True)
class StateDerivative:
    """Derivative of a rigid-body state."""

    position_dot_m_s: Vector3Array
    velocity_dot_m_s2: Vector3Array
    attitude_dot_quat_s: Vector3Array
    angular_velocity_dot_rad_s2: Vector3Array


@dataclass(frozen=True)
class ForceMoment:
    """Net force/moment and instantaneous mass properties."""

    force_inertial_n: Vector3Array
    moment_body_n_m: Vector3Array
    mass_kg: float
    inertia_tensor_kg_m2: Vector3Array


@dataclass(frozen=True)
class DynamicsForces(ForceMoment):
    """Detailed force model output for logging and tests."""

    mass_properties: MassProperties
    atmosphere: AtmosphereState
    aero: AeroResult
    solid_thrust_body_n: Vector3Array
    coldgas: ColdGasForces | None
    aerodynamic_force_body_n: Vector3Array
    aerodynamic_moment_body_n_m: Vector3Array
    dynamic_pressure_pa: float
    mach: float
    mechanical_energy_j: float


class DynamicsPlant:
    """Assemble gravity, aero, solid-motor, and cold-gas loads for the rigid-body core."""

    def __init__(
        self,
        vehicle: VehicleModel,
        environment: EnvironmentModel,
        aero: AeroModel,
        settings: DynamicsSettings,
        motor: SolidMotor | None = None,
        coldgas: ColdGasSystem | None = None,
    ) -> None:
        self.vehicle = vehicle
        self.environment = environment
        self.aero = aero
        self.settings = settings
        self.motor = motor
        self.coldgas = coldgas
        self._motor_axis = _unit(np.asarray(settings.motor_thrust_axis_unit, dtype=np.float64))
        self._motor_position = np.asarray(settings.motor_thrust_position_m, dtype=np.float64)

    def force_moment(
        self,
        state: RigidBodyState,
        valve_states: Sequence[bool] = (),
        tank_state: CO2TankState | None = None,
    ) -> DynamicsForces:
        """Compute the force/moment at one state."""

        state = state.normalized()
        mass_properties = self.vehicle.mass_properties(state.time_s)
        mass = mass_properties.mass_kg
        inertia = mass_properties.inertia_tensor_kg_m2
        cg_body = mass_properties.center_of_mass_m

        altitude = float(state.position_m[2])
        atmosphere = self.environment.atmosphere.state_at(altitude)
        wind_inertial = self.environment.wind.velocity_at(altitude, state.time_s)
        relative_velocity_inertial = state.velocity_m_s - wind_inertial
        speed = float(np.linalg.norm(relative_velocity_inertial))
        mach = speed / atmosphere.speed_of_sound_m_s if atmosphere.speed_of_sound_m_s > 0.0 else 0.0
        leg_angle = average_leg_deploy_angle_deg(self.vehicle.definition, state.time_s)
        aero_state = self.aero.state_from_mass_properties(
            mass_properties=mass_properties,
            mach=mach,
            leg_deploy_angle_deg=leg_angle,
        )
        aero_result = self.aero.evaluate(aero_state)
        dynamic_pressure = 0.5 * atmosphere.density_kg_m3 * speed * speed
        aero_force_body, aero_moment_body = self._aero_loads(
            state=state,
            relative_velocity_inertial=relative_velocity_inertial,
            speed_m_s=speed,
            dynamic_pressure_pa=dynamic_pressure,
            aero_result=aero_result,
            cg_body_m=cg_body,
        )

        gravity_force_inertial = np.asarray(
            [0.0, 0.0, -mass * self.environment.definition.data.atmosphere.gravity_m_s2],
            dtype=np.float64,
        )

        solid_force_body = np.zeros(3, dtype=np.float64)
        solid_moment_body = np.zeros(3, dtype=np.float64)
        if self.motor is not None:
            solid_force_body = self.motor.thrust_force_body_n(
                state.time_s,
                axis=_tuple3(self._motor_axis),
            )
            solid_moment_body = np.cross(self._motor_position - cg_body, solid_force_body)

        coldgas_forces: ColdGasForces | None = None
        coldgas_force_body = np.zeros(3, dtype=np.float64)
        coldgas_moment_body = np.zeros(3, dtype=np.float64)
        if self.coldgas is not None and tank_state is not None:
            coldgas_forces = self.coldgas.thrust_and_torque(
                valve_states,
                state.time_s,
                tank_state,
            )
            coldgas_force_body = coldgas_forces.force_body_n
            coldgas_moment_body = self._coldgas_moment_about_cg(coldgas_forces, cg_body)

        body_force = aero_force_body + solid_force_body + coldgas_force_body
        force_inertial = gravity_force_inertial + rotate_body_to_inertial(
            state.attitude_quat,
            body_force,
        )
        moment_body = aero_moment_body + solid_moment_body + coldgas_moment_body
        energy = mechanical_energy_j(
            state=state,
            mass_kg=mass,
            inertia_tensor_kg_m2=inertia,
            gravity_m_s2=self.environment.definition.data.atmosphere.gravity_m_s2,
        )
        return DynamicsForces(
            force_inertial_n=force_inertial,
            moment_body_n_m=moment_body,
            mass_kg=mass,
            inertia_tensor_kg_m2=inertia,
            mass_properties=mass_properties,
            atmosphere=atmosphere,
            aero=aero_result,
            solid_thrust_body_n=solid_force_body,
            coldgas=coldgas_forces,
            aerodynamic_force_body_n=aero_force_body,
            aerodynamic_moment_body_n_m=aero_moment_body,
            dynamic_pressure_pa=dynamic_pressure,
            mach=mach,
            mechanical_energy_j=energy,
        )

    def step(
        self,
        state: RigidBodyState,
        dt_s: float,
        valve_states: Sequence[bool] = (),
        tank_state: CO2TankState | None = None,
    ) -> RigidBodyState:
        """Advance one fixed RK4 step with zero-order-held valve/tank inputs."""

        held_valves = tuple(valve_states)

        def held_provider(substate: RigidBodyState) -> ForceMoment:
            return self.force_moment(substate, held_valves, tank_state)

        return rk4_step(state, dt_s, held_provider)

    def _aero_loads(
        self,
        state: RigidBodyState,
        relative_velocity_inertial: Vector3Array,
        speed_m_s: float,
        dynamic_pressure_pa: float,
        aero_result: AeroResult,
        cg_body_m: Vector3Array,
    ) -> tuple[Vector3Array, Vector3Array]:
        if speed_m_s < self.settings.minimum_aero_speed_m_s:
            return np.zeros(3, dtype=np.float64), np.zeros(3, dtype=np.float64)

        velocity_body = rotate_inertial_to_body(state.attitude_quat, relative_velocity_inertial)
        drag_inertial = (
            -dynamic_pressure_pa
            * aero_result.reference_area_m2
            * aero_result.cd
            * relative_velocity_inertial
            / speed_m_s
        )
        drag_body = rotate_inertial_to_body(state.attitude_quat, drag_inertial)
        transverse_velocity_body = np.asarray(
            [velocity_body[0], velocity_body[1], 0.0],
            dtype=np.float64,
        )
        normal_body = (
            -dynamic_pressure_pa
            * aero_result.reference_area_m2
            * aero_result.normal_force_slope_per_rad
            * transverse_velocity_body
            / speed_m_s
        )
        force_body = drag_body + normal_body
        cp_body = np.asarray([0.0, 0.0, aero_result.cp_axial_m], dtype=np.float64)
        moment_body = np.cross(cp_body - cg_body_m, force_body)
        moment_body = (
            moment_body - self.settings.angular_damping_n_m_s * state.angular_velocity_rad_s
        )
        return np.asarray(force_body, dtype=np.float64), np.asarray(moment_body, dtype=np.float64)

    def _coldgas_moment_about_cg(
        self,
        coldgas_forces: ColdGasForces,
        cg_body_m: Vector3Array,
    ) -> Vector3Array:
        if self.coldgas is None:
            return np.zeros(3, dtype=np.float64)
        moment = np.zeros(3, dtype=np.float64)
        for nozzle, flow in zip(
            self.coldgas.config.data.nozzles.items,
            coldgas_forces.flows,
            strict=True,
        ):
            nozzle_position = np.asarray(nozzle.position_m, dtype=np.float64)
            moment = moment + np.cross(nozzle_position - cg_body_m, flow.force_body_n)
        return np.asarray(moment, dtype=np.float64)


def normalize_quaternion(quaternion: ArrayLike) -> Vector3Array:
    """Return a unit quaternion."""

    q = np.asarray(quaternion, dtype=np.float64)
    _require_shape(q, (4,), "quaternion")
    norm = float(np.linalg.norm(q))
    if norm <= 0.0:
        msg = "quaternion norm must be positive"
        raise ValueError(msg)
    return q / norm


def quat_conjugate(quaternion: ArrayLike) -> Vector3Array:
    """Return the quaternion conjugate."""

    q = normalize_quaternion(quaternion)
    return np.asarray([q[0], -q[1], -q[2], -q[3]], dtype=np.float64)


def quat_multiply(left: ArrayLike, right: ArrayLike) -> Vector3Array:
    """Hamilton product of two quaternions."""

    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    _require_shape(a, (4,), "left quaternion")
    _require_shape(b, (4,), "right quaternion")
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.asarray(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ],
        dtype=np.float64,
    )


def rotate_body_to_inertial(
    quaternion: ArrayLike,
    vector_body: ArrayLike,
) -> Vector3Array:
    """Rotate a body-frame vector into the inertial frame."""

    q = normalize_quaternion(quaternion)
    v = np.asarray(vector_body, dtype=np.float64)
    _require_shape(v, (3,), "vector_body")
    rotated = quat_multiply(quat_multiply(q, np.concatenate(([0.0], v))), quat_conjugate(q))
    return np.asarray(rotated[1:], dtype=np.float64)


def rotate_inertial_to_body(
    quaternion: ArrayLike,
    vector_inertial: ArrayLike,
) -> Vector3Array:
    """Rotate an inertial-frame vector into the body frame."""

    q = normalize_quaternion(quaternion)
    v = np.asarray(vector_inertial, dtype=np.float64)
    _require_shape(v, (3,), "vector_inertial")
    rotated = quat_multiply(quat_multiply(quat_conjugate(q), np.concatenate(([0.0], v))), q)
    return np.asarray(rotated[1:], dtype=np.float64)


def compute_derivative(state: RigidBodyState, forces: ForceMoment) -> StateDerivative:
    """Compute rigid-body translational and rotational derivatives."""

    state = state.normalized()
    if forces.mass_kg <= 0.0:
        msg = "mass must be positive"
        raise ValueError(msg)
    inertia = np.asarray(forces.inertia_tensor_kg_m2, dtype=np.float64)
    _require_shape(inertia, (3, 3), "inertia_tensor_kg_m2")
    inertia = 0.5 * (inertia + inertia.T)
    if np.any(np.linalg.eigvalsh(inertia) <= 0.0):
        msg = "inertia tensor must be positive definite for dynamics"
        raise ValueError(msg)

    omega = np.asarray(state.angular_velocity_rad_s, dtype=np.float64)
    angular_momentum_body = inertia @ omega
    omega_dot = np.linalg.solve(
        inertia,
        np.asarray(forces.moment_body_n_m, dtype=np.float64)
        - np.cross(omega, angular_momentum_body),
    )
    omega_quat = np.asarray([0.0, omega[0], omega[1], omega[2]], dtype=np.float64)
    q_dot = 0.5 * quat_multiply(state.attitude_quat, omega_quat)
    return StateDerivative(
        position_dot_m_s=np.asarray(state.velocity_m_s, dtype=np.float64),
        velocity_dot_m_s2=np.asarray(forces.force_inertial_n, dtype=np.float64) / forces.mass_kg,
        attitude_dot_quat_s=q_dot,
        angular_velocity_dot_rad_s2=np.asarray(omega_dot, dtype=np.float64),
    )


def rk4_step(state: RigidBodyState, dt_s: float, provider: ForceProvider) -> RigidBodyState:
    """Advance one fixed RK4 step."""

    if dt_s <= 0.0:
        msg = "dt_s must be positive"
        raise ValueError(msg)
    normalized_state = state.normalized()
    k1 = compute_derivative(normalized_state, provider(normalized_state))
    k2_state = _apply_derivative(normalized_state, k1, 0.5 * dt_s)
    k2 = compute_derivative(k2_state, provider(k2_state))
    k3_state = _apply_derivative(normalized_state, k2, 0.5 * dt_s)
    k3 = compute_derivative(k3_state, provider(k3_state))
    k4_state = _apply_derivative(normalized_state, k3, dt_s)
    k4 = compute_derivative(k4_state, provider(k4_state))

    return RigidBodyState(
        time_s=normalized_state.time_s + dt_s,
        position_m=normalized_state.position_m
        + dt_s
        / 6.0
        * (
            k1.position_dot_m_s
            + 2.0 * k2.position_dot_m_s
            + 2.0 * k3.position_dot_m_s
            + k4.position_dot_m_s
        ),
        velocity_m_s=normalized_state.velocity_m_s
        + dt_s
        / 6.0
        * (
            k1.velocity_dot_m_s2
            + 2.0 * k2.velocity_dot_m_s2
            + 2.0 * k3.velocity_dot_m_s2
            + k4.velocity_dot_m_s2
        ),
        attitude_quat=normalize_quaternion(
            normalized_state.attitude_quat
            + dt_s
            / 6.0
            * (
                k1.attitude_dot_quat_s
                + 2.0 * k2.attitude_dot_quat_s
                + 2.0 * k3.attitude_dot_quat_s
                + k4.attitude_dot_quat_s
            )
        ),
        angular_velocity_rad_s=normalized_state.angular_velocity_rad_s
        + dt_s
        / 6.0
        * (
            k1.angular_velocity_dot_rad_s2
            + 2.0 * k2.angular_velocity_dot_rad_s2
            + 2.0 * k3.angular_velocity_dot_rad_s2
            + k4.angular_velocity_dot_rad_s2
        ),
    )


def integrate_fixed_step(
    initial_state: RigidBodyState,
    duration_s: float,
    dt_s: float,
    provider: ForceProvider,
) -> tuple[RigidBodyState, ...]:
    """Integrate from the initial state for a duration using fixed-step RK4."""

    if duration_s < 0.0:
        msg = "duration_s must be non-negative"
        raise ValueError(msg)
    steps_float = duration_s / dt_s
    steps = int(round(steps_float))
    if not math.isclose(steps * dt_s, duration_s, rel_tol=0.0, abs_tol=1.0e-12):
        msg = "duration_s must be an integer multiple of dt_s"
        raise ValueError(msg)
    states = [initial_state.normalized()]
    state = states[0]
    for _ in range(steps):
        state = rk4_step(state, dt_s, provider)
        states.append(state)
    return tuple(states)


def mechanical_energy_j(
    state: RigidBodyState,
    mass_kg: float,
    inertia_tensor_kg_m2: Vector3Array,
    gravity_m_s2: float,
) -> float:
    """Return translational + rotational + gravitational potential energy."""

    translational = 0.5 * mass_kg * float(state.velocity_m_s @ state.velocity_m_s)
    rotational = 0.5 * float(
        state.angular_velocity_rad_s
        @ (np.asarray(inertia_tensor_kg_m2, dtype=np.float64) @ state.angular_velocity_rad_s)
    )
    potential = mass_kg * gravity_m_s2 * float(state.position_m[2])
    return translational + rotational + potential


def inertial_angular_momentum(
    state: RigidBodyState,
    inertia_tensor_kg_m2: Vector3Array,
) -> Vector3Array:
    """Return angular momentum expressed in the inertial frame."""

    body_h = np.asarray(inertia_tensor_kg_m2, dtype=np.float64) @ state.angular_velocity_rad_s
    return rotate_body_to_inertial(state.attitude_quat, body_h)


def analytic_ballistic_position(
    initial_position_m: ArrayLike,
    initial_velocity_m_s: ArrayLike,
    t_s: float,
    gravity_m_s2: float,
) -> Vector3Array:
    """Closed-form no-thrust ballistic position under constant gravity."""

    if t_s < 0.0:
        msg = "t_s must be non-negative"
        raise ValueError(msg)
    position = np.asarray(initial_position_m, dtype=np.float64)
    velocity = np.asarray(initial_velocity_m_s, dtype=np.float64)
    _require_shape(position, (3,), "initial_position_m")
    _require_shape(velocity, (3,), "initial_velocity_m_s")
    acceleration = np.asarray([0.0, 0.0, -gravity_m_s2], dtype=np.float64)
    return position + velocity * t_s + 0.5 * acceleration * t_s * t_s


def trajectory_hash(states: Sequence[RigidBodyState]) -> str:
    """Return a stable hash of a state sequence."""

    matrix = np.asarray([state.state_vector() for state in states], dtype=np.float64)
    rounded = np.round(matrix, decimals=12)
    return hashlib.sha256(np.ascontiguousarray(rounded).tobytes()).hexdigest()


def average_leg_deploy_angle_deg(definition: VehicleDefinition, t_s: float) -> float:
    """Return the mean deployable-leg angle for live aero coupling."""

    angles = [
        part.deployable_leg.angle_deg_at(t_s)
        for part in definition.parts
        if part.deployable_leg is not None
    ]
    if not angles:
        return 0.0
    return float(np.mean(np.asarray(angles, dtype=np.float64)))


def _apply_derivative(
    state: RigidBodyState,
    derivative: StateDerivative,
    dt_s: float,
) -> RigidBodyState:
    return RigidBodyState(
        time_s=state.time_s + dt_s,
        position_m=state.position_m + derivative.position_dot_m_s * dt_s,
        velocity_m_s=state.velocity_m_s + derivative.velocity_dot_m_s2 * dt_s,
        attitude_quat=normalize_quaternion(
            state.attitude_quat + derivative.attitude_dot_quat_s * dt_s
        ),
        angular_velocity_rad_s=state.angular_velocity_rad_s
        + derivative.angular_velocity_dot_rad_s2 * dt_s,
    )


def _unit(vector: Vector3Array) -> Vector3Array:
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        msg = "unit vector must be non-zero"
        raise ValueError(msg)
    return vector / norm


def _tuple3(vector: Vector3Array) -> tuple[float, float, float]:
    _require_shape(vector, (3,), "vector")
    return (float(vector[0]), float(vector[1]), float(vector[2]))


def _require_shape(array: ArrayLike, shape: tuple[int, ...], name: str) -> None:
    if np.asarray(array).shape != shape:
        msg = f"{name} must have shape {shape}"
        raise ValueError(msg)
