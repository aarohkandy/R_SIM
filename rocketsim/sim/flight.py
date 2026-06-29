"""End-to-end native SIL flight runner."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from rocketsim.actuation import ValveCommands
from rocketsim.aero import AeroModel
from rocketsim.control import NativeSILBackend
from rocketsim.dynamics import (
    DynamicsPlant,
    RigidBodyState,
    rotate_inertial_to_body,
    trajectory_hash,
)
from rocketsim.environment import EnvironmentModel
from rocketsim.io import write_full_data_bundle
from rocketsim.propulsion import ColdGasSystem, load_configured_motor
from rocketsim.sensors import SensorPacket, SensorSuite, SensorTruth, sensor_packet_hash
from rocketsim.sim.schema import SimConfig, load_sim_config
from rocketsim.thermal import (
    ThermalArtifacts,
    run_configured_thermal_analysis,
    write_thermal_artifacts,
)
from rocketsim.vehicle import VehicleModel


@dataclass(frozen=True)
class SILRunResult:
    """End-to-end SIL run paths and summary data."""

    output_dir: Path
    telemetry_csv: Path
    telemetry_parquet: Path
    landing_summary_json: Path
    landing_summary_csv: Path
    run_manifest_json: Path
    plot_paths: tuple[Path, ...]
    animation_gif: Path
    animation_html: Path
    animation_mp4: Path | None
    thermal_artifacts: ThermalArtifacts
    telemetry_hash: str
    sensor_hash: str
    state_hash: str
    summary: dict[str, Any]


def run_native_sil_e2e(
    repo_root: Path | str = Path("."),
    output_root: Path | str | None = None,
) -> SILRunResult:
    """Run the Phase-8 native-SIL rail-to-touchdown simulation."""

    root = Path(repo_root).resolve()
    sim_config = load_sim_config(root / "config" / "sim.yaml")
    output_base = (
        Path(output_root) if output_root is not None else root / sim_config.data.e2e.output_root
    )
    if not output_base.is_absolute():
        output_base = root / output_base
    run_id = f"{sim_config.data.e2e.run_id_prefix}_seed{sim_config.data.master_seed}"
    output_dir = output_base / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    environment = EnvironmentModel.from_config_path(root / "config" / "environment.yaml")
    coldgas = ColdGasSystem.from_config_path(root / "config" / "coldgas.yaml")
    plant = DynamicsPlant(
        vehicle=VehicleModel.from_bom_path(root / "inputs" / "bom_placeholder.yaml"),
        environment=environment,
        aero=AeroModel.from_config_path(root / "config" / "aero.yaml"),
        settings=sim_config.data.dynamics,
        motor=load_configured_motor(root / "config" / "motor.yaml"),
        coldgas=coldgas,
    )
    backend = NativeSILBackend.from_config_paths(
        root / "config" / "control.yaml",
        root / "config" / "actuation.yaml",
        root / "config" / "coldgas.yaml",
    )
    backend.reset(sim_config.data.master_seed)
    sensors = SensorSuite.from_config_paths(
        root / "config" / "sensors.yaml",
        root / "config" / "environment.yaml",
        sim_config.data.master_seed,
    )

    state = _initial_state(sim_config)
    tank_state = coldgas.initial_state()
    valve_commands = ValveCommands(tuple(False for _ in coldgas.config.data.nozzles.items))
    latest_packet: SensorPacket | None = None
    telemetry_rows: list[dict[str, Any]] = []
    sensor_packets: list[SensorPacket] = []
    states: list[RigidBodyState] = [state]
    rail_exit_time_s: float | None = None
    rail_exit_speed_m_s: float | None = None
    max_altitude_m = float(state.position_m[2])
    max_dynamic_pressure_pa = 0.0
    next_control_time_s = 0.0
    dt_s = sim_config.data.integrator_dt_s

    while state.time_s < sim_config.data.e2e.max_time_s:
        forces = plant.force_moment(state, valve_commands.states, tank_state)
        max_altitude_m = max(max_altitude_m, float(state.position_m[2]))
        max_dynamic_pressure_pa = max(max_dynamic_pressure_pa, forces.dynamic_pressure_pa)
        truth = SensorTruth.from_dynamics(
            state,
            forces,
            environment.definition.data.atmosphere.gravity_m_s2,
        )
        packet = sensors.sample_due(truth)
        if packet is not None:
            latest_packet = packet
            sensor_packets.append(packet)
        if latest_packet is not None and state.time_s + 1.0e-12 >= next_control_time_s:
            valve_commands = backend.step(latest_packet, state.time_s)
            next_control_time_s += backend.loop_period_s

        telemetry_rows.append(
            _telemetry_row(
                state=state,
                forces=forces,
                tank_state=tank_state,
                valves=valve_commands,
                packet=latest_packet,
                controller=backend.telemetry(),
                rail_exit_time_s=rail_exit_time_s,
            )
        )

        next_state = plant.step(state, dt_s, valve_commands.states, tank_state)
        next_state, rail_exit_time_s, rail_exit_speed_m_s = _apply_rail_constraint(
            previous=state,
            candidate=next_state,
            environment=environment,
            rail_exit_time_s=rail_exit_time_s,
            rail_exit_speed_m_s=rail_exit_speed_m_s,
            margin_m=sim_config.data.e2e.rail_exit_latch_margin_m,
        )
        if any(valve_commands.states) and tank_state.total_mass_kg > 0.0:
            tank_state = coldgas.step(tank_state, valve_commands.states, dt_s).state
        else:
            tank_state = replace(tank_state, time_s=tank_state.time_s + dt_s)
        state = next_state
        states.append(state)

        if (
            rail_exit_time_s is not None
            and state.position_m[2] <= sim_config.data.e2e.touchdown_altitude_m
            and state.velocity_m_s[2] <= 0.0
        ):
            break

    touchdown = state.position_m[2] <= sim_config.data.e2e.touchdown_altitude_m
    telemetry_hash = _rows_hash(telemetry_rows)
    summary: dict[str, Any] = {
        "touchdown": bool(touchdown),
        "touchdown_time_s": state.time_s,
        "touchdown_speed_m_s": float(np.linalg.norm(state.velocity_m_s)),
        "touchdown_vertical_speed_m_s": float(state.velocity_m_s[2]),
        "touchdown_altitude_m": float(state.position_m[2]),
        "max_altitude_m": max_altitude_m,
        "max_dynamic_pressure_pa": max_dynamic_pressure_pa,
        "rail_exit_time_s": rail_exit_time_s,
        "rail_exit_speed_m_s": rail_exit_speed_m_s,
        "co2_remaining_kg": tank_state.total_mass_kg,
        "tank_pressure_pa": tank_state.pressure_pa,
        "controller_backend": "sil",
        "telemetry_rows": len(telemetry_rows),
    }
    thermal_result = run_configured_thermal_analysis(
        root / "config" / "thermal.yaml",
        telemetry_rows,
        root,
    )
    summary["thermal"] = thermal_result.summary
    summary["peak_thermal_temperature_deg_c"] = thermal_result.summary["peak_temperature_deg_c"]
    summary["minimum_thermal_margin_deg_c"] = thermal_result.summary["minimum_margin_deg_c"]
    thermal_artifacts = write_thermal_artifacts(thermal_result, output_dir)
    sensor_hash = sensor_packet_hash(sensor_packets)
    state_hash = trajectory_hash(states)
    manifest = {
        "run_id": run_id,
        "seed": sim_config.data.master_seed,
        "backend": "sil",
        "telemetry_hash": telemetry_hash,
        "sensor_hash": sensor_hash,
        "state_hash": state_hash,
        "input_hashes": _input_hashes(root),
    }
    artifacts = write_full_data_bundle(
        output_dir=output_dir,
        telemetry_rows=telemetry_rows,
        landing_summary=summary,
        manifest=manifest,
        extra_artifacts={"thermal": thermal_artifacts.manifest_payload(output_dir)},
    )
    return SILRunResult(
        output_dir=output_dir,
        telemetry_csv=artifacts.telemetry_csv,
        telemetry_parquet=artifacts.telemetry_parquet,
        landing_summary_json=artifacts.landing_summary_json,
        landing_summary_csv=artifacts.landing_summary_csv,
        run_manifest_json=artifacts.run_manifest_json,
        plot_paths=artifacts.plot_paths,
        animation_gif=artifacts.animation_gif,
        animation_html=artifacts.animation_html,
        animation_mp4=artifacts.animation_mp4,
        thermal_artifacts=thermal_artifacts,
        telemetry_hash=telemetry_hash,
        sensor_hash=sensor_hash,
        state_hash=state_hash,
        summary=summary,
    )


def _initial_state(sim_config: SimConfig) -> RigidBodyState:
    e2e = sim_config.data.e2e
    return RigidBodyState(
        time_s=0.0,
        position_m=np.asarray(e2e.initial_position_m, dtype=np.float64),
        velocity_m_s=np.asarray(e2e.initial_velocity_m_s, dtype=np.float64),
        attitude_quat=np.asarray(e2e.initial_attitude_quat, dtype=np.float64),
        angular_velocity_rad_s=np.asarray(e2e.initial_angular_velocity_rad_s, dtype=np.float64),
    ).normalized()


def _apply_rail_constraint(
    previous: RigidBodyState,
    candidate: RigidBodyState,
    environment: EnvironmentModel,
    rail_exit_time_s: float | None,
    rail_exit_speed_m_s: float | None,
    margin_m: float,
) -> tuple[RigidBodyState, float | None, float | None]:
    if rail_exit_time_s is not None:
        return candidate, rail_exit_time_s, rail_exit_speed_m_s
    rail = environment.launch_rail
    direction = rail.direction_m
    distance = float(candidate.position_m @ direction)
    if distance < rail.definition.length_m + margin_m:
        constrained_distance = max(0.0, distance)
        along_velocity = max(0.0, float(candidate.velocity_m_s @ direction))
        return (
            RigidBodyState(
                time_s=candidate.time_s,
                position_m=rail.position_at_distance(constrained_distance),
                velocity_m_s=direction * along_velocity,
                attitude_quat=previous.attitude_quat,
                angular_velocity_rad_s=np.zeros(3, dtype=np.float64),
            ),
            None,
            None,
        )
    return candidate, candidate.time_s, float(np.linalg.norm(candidate.velocity_m_s))


def _telemetry_row(
    state: RigidBodyState,
    forces: Any,
    tank_state: Any,
    valves: ValveCommands,
    packet: SensorPacket | None,
    controller: dict[str, Any],
    rail_exit_time_s: float | None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "time_s": state.time_s,
        "position_x_m": float(state.position_m[0]),
        "position_y_m": float(state.position_m[1]),
        "position_z_m": float(state.position_m[2]),
        "velocity_x_m_s": float(state.velocity_m_s[0]),
        "velocity_y_m_s": float(state.velocity_m_s[1]),
        "velocity_z_m_s": float(state.velocity_m_s[2]),
        "accel_x_m_s2": float(forces.force_inertial_n[0] / forces.mass_kg),
        "accel_y_m_s2": float(forces.force_inertial_n[1] / forces.mass_kg),
        "accel_z_m_s2": float(forces.force_inertial_n[2] / forces.mass_kg),
        "quat_w": float(state.attitude_quat[0]),
        "quat_x": float(state.attitude_quat[1]),
        "quat_y": float(state.attitude_quat[2]),
        "quat_z": float(state.attitude_quat[3]),
        **_euler_degrees(state.attitude_quat),
        "body_rate_x_rad_s": float(state.angular_velocity_rad_s[0]),
        "body_rate_y_rad_s": float(state.angular_velocity_rad_s[1]),
        "body_rate_z_rad_s": float(state.angular_velocity_rad_s[2]),
        "mass_kg": forces.mass_kg,
        "cg_x_m": float(forces.mass_properties.center_of_mass_m[0]),
        "cg_y_m": float(forces.mass_properties.center_of_mass_m[1]),
        "cg_z_m": float(forces.mass_properties.center_of_mass_m[2]),
        "inertia_xx_kg_m2": float(forces.inertia_tensor_kg_m2[0, 0]),
        "inertia_yy_kg_m2": float(forces.inertia_tensor_kg_m2[1, 1]),
        "inertia_zz_kg_m2": float(forces.inertia_tensor_kg_m2[2, 2]),
        "aoa_rad": _angle_of_attack_rad(state),
        "mach": forces.mach,
        "dynamic_pressure_pa": forces.dynamic_pressure_pa,
        "static_margin_calibers": forces.aero.static_margin_calibers,
        "solid_thrust_n": float(np.linalg.norm(forces.solid_thrust_body_n)),
        "coldgas_thrust_n": 0.0 if forces.coldgas is None else forces.coldgas.total_thrust_n,
        "total_thrust_n": float(np.linalg.norm(forces.solid_thrust_body_n))
        + (0.0 if forces.coldgas is None else forces.coldgas.total_thrust_n),
        "co2_mass_kg": tank_state.total_mass_kg,
        "co2_liquid_mass_kg": tank_state.liquid_mass_kg,
        "co2_vapor_mass_kg": tank_state.vapor_mass_kg,
        "tank_pressure_pa": tank_state.pressure_pa,
        "cartridge_temperature_k": tank_state.temperature_k,
        "controller_collective_duty": controller.get("collective_duty", 0.0),
        "controller_torque_x_duty": controller.get("torque_x_duty", 0.0),
        "controller_torque_y_duty": controller.get("torque_y_duty", 0.0),
        "controller_vertical_rate_m_s": controller.get("estimated_vertical_rate_m_s", 0.0),
        "rail_exited": rail_exit_time_s is not None,
    }
    for index, is_open in enumerate(valves.states):
        row[f"valve_{index}_open"] = is_open
        thrust = 0.0
        mass_flow = 0.0
        if forces.coldgas is not None and index < len(forces.coldgas.flows):
            thrust = forces.coldgas.flows[index].thrust_n
            mass_flow = forces.coldgas.flows[index].mass_flow_kg_s
        row[f"nozzle_{index}_thrust_n"] = thrust
        row[f"nozzle_{index}_mass_flow_kg_s"] = mass_flow
    if packet is not None and packet.imu is not None:
        row["imu_accel_x_m_s2"] = float(packet.imu.accel_m_s2[0])
        row["imu_accel_y_m_s2"] = float(packet.imu.accel_m_s2[1])
        row["imu_accel_z_m_s2"] = float(packet.imu.accel_m_s2[2])
        row["imu_gyro_x_rad_s"] = float(packet.imu.gyro_rad_s[0])
        row["imu_gyro_y_rad_s"] = float(packet.imu.gyro_rad_s[1])
        row["imu_gyro_z_rad_s"] = float(packet.imu.gyro_rad_s[2])
        row["sensor_truth_accel_x_m_s2"] = float(packet.imu.truth_specific_force_body_m_s2[0])
        row["sensor_truth_accel_y_m_s2"] = float(packet.imu.truth_specific_force_body_m_s2[1])
        row["sensor_truth_accel_z_m_s2"] = float(packet.imu.truth_specific_force_body_m_s2[2])
        row["sensor_truth_gyro_x_rad_s"] = float(packet.imu.truth_angular_velocity_rad_s[0])
        row["sensor_truth_gyro_y_rad_s"] = float(packet.imu.truth_angular_velocity_rad_s[1])
        row["sensor_truth_gyro_z_rad_s"] = float(packet.imu.truth_angular_velocity_rad_s[2])
    if packet is not None and packet.barometer is not None:
        row["baro_altitude_m"] = packet.barometer.altitude_m
        row["baro_pressure_pa"] = packet.barometer.pressure_pa
        row["sensor_truth_baro_altitude_m"] = packet.barometer.truth_altitude_m
        row["sensor_truth_baro_pressure_pa"] = packet.barometer.truth_pressure_pa
    return row


def _rows_hash(rows: list[dict[str, Any]]) -> str:
    text = json.dumps(rows, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def _euler_degrees(quaternion: np.ndarray) -> dict[str, float]:
    w, x, y, z = quaternion / max(1.0e-12, float(np.linalg.norm(quaternion)))
    roll = np.degrees(np.arctan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y)))
    pitch = np.degrees(np.arcsin(np.clip(2.0 * (w * y - z * x), -1.0, 1.0)))
    yaw = np.degrees(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))
    return {
        "euler_roll_deg": float(roll),
        "euler_pitch_deg": float(pitch),
        "euler_yaw_deg": float(yaw),
    }


def _angle_of_attack_rad(state: RigidBodyState) -> float:
    speed = float(np.linalg.norm(state.velocity_m_s))
    if speed <= 1.0e-12:
        return 0.0
    velocity_body = rotate_inertial_to_body(state.attitude_quat, state.velocity_m_s)
    transverse = float(np.linalg.norm(velocity_body[:2]))
    axial = abs(float(velocity_body[2]))
    return float(np.arctan2(transverse, max(axial, 1.0e-12)))


def _input_hashes(root: Path) -> dict[str, str]:
    paths = [
        root / "config" / "sim.yaml",
        root / "config" / "control.yaml",
        root / "config" / "actuation.yaml",
        root / "config" / "sensors.yaml",
        root / "config" / "coldgas.yaml",
        root / "config" / "environment.yaml",
        root / "config" / "aero.yaml",
        root / "config" / "motor.yaml",
        root / "inputs" / "bom_placeholder.yaml",
        root / "inputs" / "motor_D21_placeholder.eng",
    ]
    return {str(path.relative_to(root)): _file_sha256(path) for path in paths}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
