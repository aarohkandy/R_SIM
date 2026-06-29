from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from rocketsim.aero import AeroModel
from rocketsim.dynamics import DynamicsPlant, RigidBodyState
from rocketsim.environment import EnvironmentModel
from rocketsim.propulsion import ColdGasSystem, load_configured_motor
from rocketsim.sensors import (
    BarometerModel,
    IMUModel,
    SensorPacket,
    SensorsConfig,
    SensorSuite,
    SensorTruth,
    load_sensors_config,
    noise_density_to_discrete_std,
    pressure_to_altitude_m,
    sensor_packet_hash,
)
from rocketsim.sim import load_sim_config
from rocketsim.vehicle import VehicleModel

ROOT = Path(__file__).resolve().parents[1]
SENSORS_CONFIG = ROOT / "config" / "sensors.yaml"
ENV_CONFIG = ROOT / "config" / "environment.yaml"
SIM_CONFIG = ROOT / "config" / "sim.yaml"
AERO_CONFIG = ROOT / "config" / "aero.yaml"
BOM = ROOT / "inputs" / "bom_placeholder.yaml"
MOTOR_CONFIG = ROOT / "config" / "motor.yaml"
COLDGAS_CONFIG = ROOT / "config" / "coldgas.yaml"
GOLDEN = ROOT / "tests" / "golden" / "phase7_sensors.json"


def base_truth(
    *,
    time_s: float = 0.0,
    pressure_pa: float = 101325.0,
    altitude_m: float = 0.0,
    specific_force: tuple[float, float, float] = (0.3, -0.2, 12.0),
    gyro: tuple[float, float, float] = (0.01, -0.02, 0.03),
) -> SensorTruth:
    return SensorTruth(
        time_s=time_s,
        position_m=np.asarray((0.0, 0.0, altitude_m), dtype=np.float64),
        velocity_m_s=np.asarray((0.0, 0.0, 0.0), dtype=np.float64),
        attitude_quat=np.asarray((1.0, 0.0, 0.0, 0.0), dtype=np.float64),
        angular_velocity_rad_s=np.asarray(gyro, dtype=np.float64),
        acceleration_inertial_m_s2=np.asarray((0.0, 0.0, 0.0), dtype=np.float64),
        specific_force_body_m_s2=np.asarray(specific_force, dtype=np.float64),
        pressure_pa=pressure_pa,
        altitude_m=altitude_m,
    )


def no_noise_config() -> SensorsConfig:
    payload = load_sensors_config(SENSORS_CONFIG).model_dump(mode="python")
    payload["data"]["noise_enabled"] = False
    payload["data"]["imu"]["accel_bias_initial_m_s2"] = (0.0, 0.0, 0.0)
    payload["data"]["imu"]["gyro_bias_initial_rad_s"] = (0.0, 0.0, 0.0)
    payload["data"]["imu"]["accel_bias_random_walk_m_s2_per_sqrt_s"] = 0.0
    payload["data"]["imu"]["gyro_bias_random_walk_rad_s_per_sqrt_s"] = 0.0
    payload["data"]["imu"]["accel_scale_factor"] = (1.0, 1.0, 1.0)
    payload["data"]["imu"]["gyro_scale_factor"] = (1.0, 1.0, 1.0)
    payload["data"]["imu"]["misalignment_matrix"] = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    payload["data"]["barometer"]["pressure_bias_initial_pa"] = 0.0
    payload["data"]["barometer"]["pressure_bias_random_walk_pa_per_sqrt_s"] = 0.0
    return SensorsConfig.model_validate(payload)


def noise_stats_config() -> SensorsConfig:
    payload = no_noise_config().model_dump(mode="python")
    payload["data"]["noise_enabled"] = True
    payload["data"]["imu"]["accel_noise_density_m_s2_per_sqrt_hz"] = 0.01
    payload["data"]["imu"]["gyro_noise_density_rad_s_per_sqrt_hz"] = 0.001
    payload["data"]["barometer"]["pressure_noise_density_pa_per_sqrt_hz"] = 0.2
    payload["data"]["barometer"]["lag_time_constant_s"] = 1.0e-9
    return SensorsConfig.model_validate(payload)


def test_sensors_config_loads() -> None:
    config = load_sensors_config(SENSORS_CONFIG)

    assert config.data.noise_enabled
    assert config.data.imu.sample_rate_hz == pytest.approx(500.0)
    assert config.data.barometer.sample_rate_hz == pytest.approx(100.0)
    assert not config.data.tof_rangefinder.enabled
    assert not config.data.pressure_transducer.enabled


def test_noise_density_conversion_uses_sample_rate() -> None:
    assert noise_density_to_discrete_std(0.004, 500.0) == pytest.approx(
        0.004 * np.sqrt(250.0)
    )


def test_imu_no_noise_identity_calibration_reports_truth() -> None:
    config = no_noise_config()
    imu = IMUModel(config.data.imu, master_seed=123, noise_enabled=config.data.noise_enabled)
    truth = base_truth()

    reading = imu.sample(truth)

    np.testing.assert_allclose(reading.accel_m_s2, truth.specific_force_body_m_s2)
    np.testing.assert_allclose(reading.gyro_rad_s, truth.angular_velocity_rad_s)


def test_imu_noise_statistics_match_configured_density() -> None:
    config = noise_stats_config()
    imu = IMUModel(config.data.imu, master_seed=123, noise_enabled=True)
    truth = base_truth(specific_force=(0.0, 0.0, 0.0), gyro=(0.0, 0.0, 0.0))

    samples = np.asarray([imu.sample(truth).accel_m_s2 for _ in range(5000)])
    observed = samples.std(axis=0, ddof=1)

    assert np.mean(observed) == pytest.approx(imu.accel_noise_std_m_s2, rel=0.06)


def test_barometer_noise_statistics_match_configured_density() -> None:
    config = noise_stats_config()
    environment = EnvironmentModel.from_config_path(ENV_CONFIG)
    baro = BarometerModel(
        config.data.barometer,
        environment.definition.data.atmosphere,
        master_seed=321,
        noise_enabled=True,
    )
    truth = base_truth(pressure_pa=100000.0)
    readings = np.asarray([baro.sample(truth).pressure_pa for _ in range(4000)])
    first_difference_std = np.diff(readings).std(ddof=1) / np.sqrt(2.0)

    assert first_difference_std == pytest.approx(baro.pressure_noise_std_pa, rel=0.12)


def test_barometer_pressure_to_altitude_matches_environment_inverse() -> None:
    environment = EnvironmentModel.from_config_path(ENV_CONFIG)
    atmosphere = environment.definition.data.atmosphere
    state = environment.atmosphere.state_at(250.0)

    assert pressure_to_altitude_m(state.pressure_pa, atmosphere) == pytest.approx(250.0)


def test_barometer_lag_filters_pressure_steps() -> None:
    config = no_noise_config()
    environment = EnvironmentModel.from_config_path(ENV_CONFIG)
    baro = BarometerModel(
        config.data.barometer,
        environment.definition.data.atmosphere,
        master_seed=1,
        noise_enabled=False,
    )
    first = baro.sample(base_truth(pressure_pa=101325.0), dt_s=0.01)
    second = baro.sample(base_truth(time_s=0.01, pressure_pa=90000.0), dt_s=0.01)

    assert 90000.0 < second.pressure_pa < first.pressure_pa


def test_sensor_suite_sample_schedule_and_disabled_stubs() -> None:
    suite = SensorSuite.from_config_paths(SENSORS_CONFIG, ENV_CONFIG, master_seed=20260629)
    packets: list[SensorPacket] = []
    for index in range(11):
        packet = suite.sample_due(base_truth(time_s=index * 0.001))
        if packet is not None:
            packets.append(packet)

    imu_count = sum(packet.imu is not None for packet in packets)
    baro_count = sum(packet.barometer is not None for packet in packets)
    assert imu_count == 6
    assert baro_count == 2
    assert all(packet.tof_range_m is None for packet in packets)
    assert all(packet.pressure_transducer_pa is None for packet in packets)


def test_sensor_packets_are_seed_deterministic_and_seed_sensitive() -> None:
    def run(seed: int) -> list[SensorPacket]:
        suite = SensorSuite.from_config_paths(SENSORS_CONFIG, ENV_CONFIG, master_seed=seed)
        packets: list[SensorPacket] = []
        for index in range(11):
            packet = suite.sample_due(base_truth(time_s=index * 0.001))
            if packet is not None:
                packets.append(packet)
        return packets

    assert sensor_packet_hash(run(123)) == sensor_packet_hash(run(123))
    assert sensor_packet_hash(run(123)) != sensor_packet_hash(run(124))


def test_sensor_packet_matches_golden_reference() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    suite = SensorSuite.from_config_paths(SENSORS_CONFIG, ENV_CONFIG, master_seed=20260629)
    packet = suite.sample_due(base_truth())

    assert packet is not None
    assert packet.imu is not None
    assert packet.barometer is not None
    np.testing.assert_allclose(packet.imu.accel_m_s2, golden["packet_0"]["imu_accel_m_s2"])
    np.testing.assert_allclose(packet.imu.gyro_rad_s, golden["packet_0"]["imu_gyro_rad_s"])
    assert packet.barometer.pressure_pa == pytest.approx(golden["packet_0"]["baro_pressure_pa"])
    assert packet.barometer.altitude_m == pytest.approx(golden["packet_0"]["baro_altitude_m"])
    assert sensor_packet_hash([packet]) == golden["packet_0"]["packet_hash"]


def test_truth_from_dynamics_integrates_with_phase6_plant() -> None:
    sim = load_sim_config(SIM_CONFIG)
    environment = EnvironmentModel.from_config_path(ENV_CONFIG)
    plant = DynamicsPlant(
        vehicle=VehicleModel.from_bom_path(BOM),
        environment=environment,
        aero=AeroModel.from_config_path(AERO_CONFIG),
        settings=sim.data.dynamics,
        motor=load_configured_motor(MOTOR_CONFIG),
        coldgas=ColdGasSystem.from_config_path(COLDGAS_CONFIG),
    )
    current = RigidBodyState(
        time_s=0.2,
        position_m=np.asarray((0.0, 0.0, 1.0), dtype=np.float64),
        velocity_m_s=np.asarray((0.5, 0.0, 20.0), dtype=np.float64),
        attitude_quat=np.asarray((1.0, 0.0, 0.0, 0.0), dtype=np.float64),
        angular_velocity_rad_s=np.asarray((0.1, -0.2, 0.05), dtype=np.float64),
    )
    coldgas = ColdGasSystem.from_config_path(COLDGAS_CONFIG)
    forces = plant.force_moment(current, (True, False, True), coldgas.initial_state())
    truth = SensorTruth.from_dynamics(
        current,
        forces,
        environment.definition.data.atmosphere.gravity_m_s2,
    )
    packet = SensorSuite.from_config_paths(
        SENSORS_CONFIG,
        ENV_CONFIG,
        master_seed=20260629,
    ).sample_due(truth)

    assert packet is not None
    assert packet.imu is not None
    assert packet.barometer is not None
    np.testing.assert_allclose(truth.angular_velocity_rad_s, current.angular_velocity_rad_s)
    assert np.all(np.isfinite(packet.numeric_vector()))


@settings(max_examples=40)
@given(
    ax=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    ay=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    az=st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
)
def test_property_imu_acceleration_is_saturated(ax: float, ay: float, az: float) -> None:
    config = no_noise_config()
    imu = IMUModel(config.data.imu, master_seed=1, noise_enabled=False)
    reading = imu.sample(base_truth(specific_force=(ax, ay, az)))

    assert np.all(np.abs(reading.accel_m_s2) <= config.data.imu.accel_saturation_m_s2)


def test_invalid_sensor_yaml_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(TypeError, match="must contain a YAML mapping"):
        load_sensors_config(invalid)


def test_invalid_sensor_config_rejected() -> None:
    payload = load_sensors_config(SENSORS_CONFIG).model_dump(mode="python")
    payload["data"]["barometer"]["pressure_min_pa"] = 120000.0

    with pytest.raises(ValidationError, match="pressure_min_pa must be less"):
        SensorsConfig.model_validate(payload)
