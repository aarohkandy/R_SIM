"""Deterministic IMU and barometer sensor models."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from rocketsim.dynamics import DynamicsForces, RigidBodyState, rotate_inertial_to_body
from rocketsim.environment import EnvironmentModel, ISAParameters
from rocketsim.randomness import make_rng
from rocketsim.sensors.schema import BarometerConfig, IMUConfig, SensorsConfig, load_sensors_config

Vector3Array = NDArray[np.float64]


@dataclass(frozen=True)
class SensorTruth:
    """Noise-free plant truth at one sample instant."""

    time_s: float
    position_m: Vector3Array
    velocity_m_s: Vector3Array
    attitude_quat: Vector3Array
    angular_velocity_rad_s: Vector3Array
    acceleration_inertial_m_s2: Vector3Array
    specific_force_body_m_s2: Vector3Array
    pressure_pa: float
    altitude_m: float

    @classmethod
    def from_dynamics(
        cls,
        state: RigidBodyState,
        forces: DynamicsForces,
        gravity_m_s2: float,
    ) -> SensorTruth:
        """Build sensor truth from a dynamics state and force model output."""

        acceleration = forces.force_inertial_n / forces.mass_kg
        gravity = np.asarray([0.0, 0.0, -gravity_m_s2], dtype=np.float64)
        specific_force_body = rotate_inertial_to_body(state.attitude_quat, acceleration - gravity)
        return cls(
            time_s=state.time_s,
            position_m=np.asarray(state.position_m, dtype=np.float64),
            velocity_m_s=np.asarray(state.velocity_m_s, dtype=np.float64),
            attitude_quat=np.asarray(state.attitude_quat, dtype=np.float64),
            angular_velocity_rad_s=np.asarray(state.angular_velocity_rad_s, dtype=np.float64),
            acceleration_inertial_m_s2=np.asarray(acceleration, dtype=np.float64),
            specific_force_body_m_s2=np.asarray(specific_force_body, dtype=np.float64),
            pressure_pa=forces.atmosphere.pressure_pa,
            altitude_m=float(state.position_m[2]),
        )


@dataclass(frozen=True)
class IMUReading:
    """One IMU sample with truth and internal bias for telemetry."""

    time_s: float
    accel_m_s2: Vector3Array
    gyro_rad_s: Vector3Array
    truth_specific_force_body_m_s2: Vector3Array
    truth_angular_velocity_rad_s: Vector3Array
    accel_bias_m_s2: Vector3Array
    gyro_bias_rad_s: Vector3Array


@dataclass(frozen=True)
class BarometerReading:
    """One barometer sample with truth and lagged/noisy measurement."""

    time_s: float
    pressure_pa: float
    altitude_m: float
    truth_pressure_pa: float
    truth_altitude_m: float
    pressure_bias_pa: float


@dataclass(frozen=True)
class SensorPacket:
    """Sensor packet emitted at a plant time boundary."""

    time_s: float
    imu: IMUReading | None
    barometer: BarometerReading | None
    tof_range_m: float | None
    pressure_transducer_pa: float | None

    def numeric_vector(self) -> Vector3Array:
        """Return deterministic numeric payload values for hashing/regression."""

        values: list[float] = [self.time_s]
        if self.imu is None:
            values.extend([math.nan] * 12)
        else:
            values.extend(self.imu.accel_m_s2.tolist())
            values.extend(self.imu.gyro_rad_s.tolist())
            values.extend(self.imu.accel_bias_m_s2.tolist())
            values.extend(self.imu.gyro_bias_rad_s.tolist())
        if self.barometer is None:
            values.extend([math.nan] * 4)
        else:
            values.extend(
                [
                    self.barometer.pressure_pa,
                    self.barometer.altitude_m,
                    self.barometer.truth_pressure_pa,
                    self.barometer.pressure_bias_pa,
                ]
            )
        return np.asarray(values, dtype=np.float64)


class IMUModel:
    """Seed-driven IMU with noise, bias drift, scale, misalignment, and saturation."""

    def __init__(self, config: IMUConfig, master_seed: int, noise_enabled: bool) -> None:
        self.config = config
        self.noise_enabled = noise_enabled
        self._rng = make_rng(master_seed, "sensors.imu")
        self._accel_bias = np.asarray(config.accel_bias_initial_m_s2, dtype=np.float64)
        self._gyro_bias = np.asarray(config.gyro_bias_initial_rad_s, dtype=np.float64)
        self._scale_accel = np.asarray(config.accel_scale_factor, dtype=np.float64)
        self._scale_gyro = np.asarray(config.gyro_scale_factor, dtype=np.float64)
        self._misalignment = np.asarray(config.misalignment_matrix, dtype=np.float64)

    @property
    def sample_period_s(self) -> float:
        return 1.0 / self.config.sample_rate_hz

    @property
    def accel_noise_std_m_s2(self) -> float:
        return noise_density_to_discrete_std(
            self.config.accel_noise_density_m_s2_per_sqrt_hz,
            self.config.sample_rate_hz,
        )

    @property
    def gyro_noise_std_rad_s(self) -> float:
        return noise_density_to_discrete_std(
            self.config.gyro_noise_density_rad_s_per_sqrt_hz,
            self.config.sample_rate_hz,
        )

    @property
    def accel_bias_m_s2(self) -> Vector3Array:
        return np.asarray(self._accel_bias, dtype=np.float64)

    @property
    def gyro_bias_rad_s(self) -> Vector3Array:
        return np.asarray(self._gyro_bias, dtype=np.float64)

    def sample(self, truth: SensorTruth, dt_s: float | None = None) -> IMUReading:
        """Sample the IMU at the configured sample rate."""

        dt = self.sample_period_s if dt_s is None else dt_s
        if dt <= 0.0:
            msg = "dt_s must be positive"
            raise ValueError(msg)
        if self.noise_enabled:
            self._accel_bias = self._accel_bias + self._rng.normal(
                0.0,
                self.config.accel_bias_random_walk_m_s2_per_sqrt_s * math.sqrt(dt),
                size=3,
            )
            self._gyro_bias = self._gyro_bias + self._rng.normal(
                0.0,
                self.config.gyro_bias_random_walk_rad_s_per_sqrt_s * math.sqrt(dt),
                size=3,
            )
            accel_noise = self._rng.normal(0.0, self.accel_noise_std_m_s2, size=3)
            gyro_noise = self._rng.normal(0.0, self.gyro_noise_std_rad_s, size=3)
        else:
            accel_noise = np.zeros(3, dtype=np.float64)
            gyro_noise = np.zeros(3, dtype=np.float64)

        accel = self._misalignment @ (
            self._scale_accel * truth.specific_force_body_m_s2 + self._accel_bias
        )
        gyro = self._misalignment @ (
            self._scale_gyro * truth.angular_velocity_rad_s + self._gyro_bias
        )
        accel = np.clip(
            accel + accel_noise,
            -self.config.accel_saturation_m_s2,
            self.config.accel_saturation_m_s2,
        )
        gyro = np.clip(
            gyro + gyro_noise,
            -self.config.gyro_saturation_rad_s,
            self.config.gyro_saturation_rad_s,
        )
        return IMUReading(
            time_s=truth.time_s,
            accel_m_s2=np.asarray(accel, dtype=np.float64),
            gyro_rad_s=np.asarray(gyro, dtype=np.float64),
            truth_specific_force_body_m_s2=np.asarray(
                truth.specific_force_body_m_s2,
                dtype=np.float64,
            ),
            truth_angular_velocity_rad_s=np.asarray(truth.angular_velocity_rad_s, dtype=np.float64),
            accel_bias_m_s2=self.accel_bias_m_s2,
            gyro_bias_rad_s=self.gyro_bias_rad_s,
        )


class BarometerModel:
    """Seed-driven barometer with pressure noise, bias drift, and first-order lag."""

    def __init__(
        self,
        config: BarometerConfig,
        atmosphere: ISAParameters,
        master_seed: int,
        noise_enabled: bool,
    ) -> None:
        self.config = config
        self.atmosphere = atmosphere
        self.noise_enabled = noise_enabled
        self._rng = make_rng(master_seed, "sensors.barometer")
        self._pressure_bias_pa = config.pressure_bias_initial_pa
        self._filtered_pressure_pa: float | None = None

    @property
    def sample_period_s(self) -> float:
        return 1.0 / self.config.sample_rate_hz

    @property
    def pressure_noise_std_pa(self) -> float:
        return noise_density_to_discrete_std(
            self.config.pressure_noise_density_pa_per_sqrt_hz,
            self.config.sample_rate_hz,
        )

    @property
    def pressure_bias_pa(self) -> float:
        return self._pressure_bias_pa

    def sample(self, truth: SensorTruth, dt_s: float | None = None) -> BarometerReading:
        """Sample the barometer at the configured sample rate."""

        dt = self.sample_period_s if dt_s is None else dt_s
        if dt <= 0.0:
            msg = "dt_s must be positive"
            raise ValueError(msg)
        if self.noise_enabled:
            self._pressure_bias_pa = self._pressure_bias_pa + float(
                self._rng.normal(
                    0.0,
                    self.config.pressure_bias_random_walk_pa_per_sqrt_s * math.sqrt(dt),
                )
            )
            noise = float(self._rng.normal(0.0, self.pressure_noise_std_pa))
        else:
            noise = 0.0

        measured_pressure = float(
            np.clip(
                truth.pressure_pa + self._pressure_bias_pa + noise,
                self.config.pressure_min_pa,
                self.config.pressure_max_pa,
            )
        )
        if self._filtered_pressure_pa is None:
            filtered_pressure = measured_pressure
        else:
            alpha = 1.0 - math.exp(-dt / self.config.lag_time_constant_s)
            filtered_pressure = self._filtered_pressure_pa + alpha * (
                measured_pressure - self._filtered_pressure_pa
            )
        self._filtered_pressure_pa = filtered_pressure
        return BarometerReading(
            time_s=truth.time_s,
            pressure_pa=filtered_pressure,
            altitude_m=pressure_to_altitude_m(filtered_pressure, self.atmosphere),
            truth_pressure_pa=truth.pressure_pa,
            truth_altitude_m=truth.altitude_m,
            pressure_bias_pa=self._pressure_bias_pa,
        )


class SensorSuite:
    """IMU/barometer sampler with explicit disabled stubs for deferred sensors."""

    def __init__(
        self,
        config: SensorsConfig,
        atmosphere: ISAParameters,
        master_seed: int,
    ) -> None:
        self.config = config
        self.imu = IMUModel(config.data.imu, master_seed, config.data.noise_enabled)
        self.barometer = BarometerModel(
            config.data.barometer,
            atmosphere,
            master_seed,
            config.data.noise_enabled,
        )
        self._last_imu_time_s: float | None = None
        self._last_baro_time_s: float | None = None
        self._next_imu_time_s = 0.0
        self._next_baro_time_s = 0.0

    @classmethod
    def from_config_paths(
        cls,
        sensors_config_path: Path | str,
        environment_config_path: Path | str,
        master_seed: int,
    ) -> SensorSuite:
        environment = EnvironmentModel.from_config_path(environment_config_path)
        return cls(
            load_sensors_config(sensors_config_path),
            environment.definition.data.atmosphere,
            master_seed,
        )

    def sample_due(self, truth: SensorTruth) -> SensorPacket | None:
        """Emit any sensor samples due at this truth time."""

        eps = 1.0e-12
        imu_reading: IMUReading | None = None
        baro_reading: BarometerReading | None = None
        if truth.time_s + eps >= self._next_imu_time_s:
            dt = (
                self.imu.sample_period_s
                if self._last_imu_time_s is None
                else truth.time_s - self._last_imu_time_s
            )
            imu_reading = self.imu.sample(truth, dt_s=dt)
            self._last_imu_time_s = truth.time_s
            self._next_imu_time_s += self.imu.sample_period_s
        if truth.time_s + eps >= self._next_baro_time_s:
            dt = (
                self.barometer.sample_period_s
                if self._last_baro_time_s is None
                else truth.time_s - self._last_baro_time_s
            )
            baro_reading = self.barometer.sample(truth, dt_s=dt)
            self._last_baro_time_s = truth.time_s
            self._next_baro_time_s += self.barometer.sample_period_s
        if imu_reading is None and baro_reading is None:
            return None
        return SensorPacket(
            time_s=truth.time_s,
            imu=imu_reading,
            barometer=baro_reading,
            tof_range_m=None,
            pressure_transducer_pa=None,
        )


def noise_density_to_discrete_std(noise_density: float, sample_rate_hz: float) -> float:
    """Convert one-sided white-noise density to per-sample standard deviation."""

    if noise_density < 0.0:
        msg = "noise_density must be non-negative"
        raise ValueError(msg)
    if sample_rate_hz <= 0.0:
        msg = "sample_rate_hz must be positive"
        raise ValueError(msg)
    return noise_density * math.sqrt(sample_rate_hz / 2.0)


def pressure_to_altitude_m(pressure_pa: float, atmosphere: ISAParameters) -> float:
    """Invert the configured ISA troposphere pressure-altitude relation."""

    if pressure_pa <= 0.0:
        msg = "pressure_pa must be positive"
        raise ValueError(msg)
    p = atmosphere
    exponent = -(p.lapse_rate_k_per_m * p.gas_constant_air_j_kg_k) / p.gravity_m_s2
    return float((p.sea_level_temperature_k / p.lapse_rate_k_per_m) * (
        (pressure_pa / p.sea_level_pressure_pa) ** exponent - 1.0
    ))


def sensor_packet_hash(packets: list[SensorPacket] | tuple[SensorPacket, ...]) -> str:
    """Return a stable hash of emitted sensor packets."""

    matrix = np.asarray([packet.numeric_vector() for packet in packets], dtype=np.float64)
    rounded = np.round(np.nan_to_num(matrix, nan=-999999.0), decimals=12)
    return hashlib.sha256(np.ascontiguousarray(rounded).tobytes()).hexdigest()
