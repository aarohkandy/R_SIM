"""CoolProp-backed CO2 cold-gas propulsion model."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from CoolProp.CoolProp import PropsSI
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator

Vector3 = tuple[float, float, float]
CO2 = "CO2"
MIN_CO2_TEMPERATURE_K = 217.0


def _props(output: str, input1: str, value1: float, input2: str, value2: float) -> float:
    return float(PropsSI(output, input1, value1, input2, value2, CO2))


def _co2_constant(output: str) -> float:
    return float(PropsSI(output, CO2))


class TankConfig(BaseModel):
    """CO2 cartridge and thermal parameters."""

    model_config = ConfigDict(extra="forbid")

    initial_co2_mass_kg: float = Field(gt=0.0)
    volume_m3: float = Field(gt=0.0)
    initial_temperature_k: float = Field(gt=MIN_CO2_TEMPERATURE_K)
    shell_mass_kg: float = Field(gt=0.0)
    shell_specific_heat_j_kg_k: float = Field(gt=0.0)
    ambient_temperature_k: float = Field(gt=0.0)
    heat_transfer_w_per_k: float = Field(ge=0.0)
    evaporation_time_constant_s: float = Field(gt=0.0)


class RegulatorConfig(BaseModel):
    """Regulator setpoints."""

    model_config = ConfigDict(extra="forbid")

    setpoint_pa: float = Field(gt=0.0)
    second_stage_enabled: bool
    second_stage_setpoint_pa: float = Field(gt=0.0)


class NozzleConfig(BaseModel):
    """One fixed bang-bang cold-gas nozzle."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    throat_area_m2: float = Field(gt=0.0)
    position_m: Vector3
    axis_unit: Vector3

    @field_validator("axis_unit")
    @classmethod
    def axis_must_be_nonzero(cls, value: Vector3) -> Vector3:
        if np.linalg.norm(np.asarray(value, dtype=np.float64)) <= 0.0:
            msg = "nozzle axis must be non-zero"
            raise ValueError(msg)
        return value

    @property
    def unit_axis_array(self) -> NDArray[np.float64]:
        axis = np.asarray(self.axis_unit, dtype=np.float64)
        return axis / float(np.linalg.norm(axis))


class NozzleBankConfig(BaseModel):
    """Nozzle bank and ambient pressure."""

    model_config = ConfigDict(extra="forbid")

    discharge_coefficient: float = Field(gt=0.0, le=1.0)
    ambient_pressure_pa: float = Field(gt=0.0)
    items: tuple[NozzleConfig, ...] = Field(min_length=1)


class ColdGasData(BaseModel):
    """Validated payload under config/coldgas.yaml:data."""

    model_config = ConfigDict(extra="forbid")

    tank: TankConfig
    regulator: RegulatorConfig
    nozzles: NozzleBankConfig


class ColdGasConfig(BaseModel):
    """Versioned cold-gas config document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: PositiveInt
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    placeholder: bool
    units: dict[str, str] = Field(default_factory=dict)
    data: ColdGasData


@dataclass(frozen=True)
class CO2TankState:
    """CO2 tank/cartridge state."""

    time_s: float
    total_mass_kg: float
    liquid_mass_kg: float
    vapor_mass_kg: float
    temperature_k: float
    pressure_pa: float
    co2_internal_energy_j: float
    shell_energy_j: float

    @property
    def total_energy_j(self) -> float:
        return self.co2_internal_energy_j + self.shell_energy_j


@dataclass(frozen=True)
class RegulatorState:
    """Regulator output after setpoint and pressure-sag logic."""

    inlet_pressure_pa: float
    output_pressure_pa: float
    sag_factor: float


@dataclass(frozen=True)
class NozzleFlow:
    """Flow and thrust for one nozzle."""

    id: str
    is_open: bool
    mass_flow_kg_s: float
    thrust_n: float
    force_body_n: NDArray[np.float64]
    torque_body_n: NDArray[np.float64]
    choked: bool


@dataclass(frozen=True)
class ColdGasForces:
    """Aggregate cold-gas thrust and torque."""

    regulator: RegulatorState
    flows: tuple[NozzleFlow, ...]
    total_mass_flow_kg_s: float
    total_thrust_n: float
    force_body_n: NDArray[np.float64]
    torque_body_n: NDArray[np.float64]


@dataclass(frozen=True)
class ColdGasStepResult:
    """Tank update and conservation residuals for one step."""

    state: CO2TankState
    forces: ColdGasForces
    mass_out_kg: float
    heat_in_j: float
    outflow_enthalpy_j: float
    mass_balance_residual_kg: float
    energy_balance_residual_j: float


class ColdGasSystem:
    """Real-gas CO2 blowdown, regulator, and fixed-nozzle thrust model."""

    def __init__(self, config: ColdGasConfig) -> None:
        self.config = config

    @classmethod
    def from_config_path(cls, path: Path | str) -> ColdGasSystem:
        return cls(load_coldgas_config(path))

    def initial_state(self) -> CO2TankState:
        tank = self.config.data.tank
        return self.state_from_mass_temperature(
            time_s=0.0,
            total_mass_kg=tank.initial_co2_mass_kg,
            temperature_k=tank.initial_temperature_k,
        )

    def state_from_mass_temperature(
        self,
        time_s: float,
        total_mass_kg: float,
        temperature_k: float,
    ) -> CO2TankState:
        if total_mass_kg < 0.0:
            msg = "CO2 mass must be non-negative"
            raise ValueError(msg)
        tank = self.config.data.tank
        liquid_mass, vapor_mass, pressure, internal_energy = co2_phase_state(
            total_mass_kg=total_mass_kg,
            temperature_k=max(temperature_k, MIN_CO2_TEMPERATURE_K),
            volume_m3=tank.volume_m3,
        )
        shell_energy = tank.shell_mass_kg * tank.shell_specific_heat_j_kg_k * temperature_k
        return CO2TankState(
            time_s=time_s,
            total_mass_kg=total_mass_kg,
            liquid_mass_kg=liquid_mass,
            vapor_mass_kg=vapor_mass,
            temperature_k=temperature_k,
            pressure_pa=pressure,
            co2_internal_energy_j=internal_energy,
            shell_energy_j=shell_energy,
        )

    def regulate_pressure(
        self,
        tank_state: CO2TankState,
        requested_mass_flow_kg_s: float,
    ) -> RegulatorState:
        regulator = self.config.data.regulator
        output_pressure = min(tank_state.pressure_pa, regulator.setpoint_pa)
        if regulator.second_stage_enabled:
            output_pressure = min(output_pressure, regulator.second_stage_setpoint_pa)

        supply_capacity = vapor_supply_capacity_kg_s(
            tank_state,
            evaporation_time_constant_s=self.config.data.tank.evaporation_time_constant_s,
        )
        sag_factor = 1.0
        if requested_mass_flow_kg_s > supply_capacity > 0.0:
            sag_factor = supply_capacity / requested_mass_flow_kg_s
            ambient = self.config.data.nozzles.ambient_pressure_pa
            output_pressure = ambient + (output_pressure - ambient) * sag_factor
        elif supply_capacity <= 0.0 and requested_mass_flow_kg_s > 0.0:
            sag_factor = 0.0
            output_pressure = self.config.data.nozzles.ambient_pressure_pa

        return RegulatorState(
            inlet_pressure_pa=tank_state.pressure_pa,
            output_pressure_pa=max(output_pressure, self.config.data.nozzles.ambient_pressure_pa),
            sag_factor=sag_factor,
        )

    def thrust_and_torque(
        self,
        valve_states: Sequence[bool],
        _t_s: float,
        tank_state: CO2TankState,
    ) -> ColdGasForces:
        if len(valve_states) != len(self.config.data.nozzles.items):
            msg = "valve state count must match nozzle count"
            raise ValueError(msg)
        preliminary_pressure = min(tank_state.pressure_pa, self.config.data.regulator.setpoint_pa)
        preliminary = [
            nozzle_flow_rate(
                nozzle=nozzle,
                is_open=is_open,
                pressure_pa=preliminary_pressure,
                temperature_k=tank_state.temperature_k,
                discharge_coefficient=self.config.data.nozzles.discharge_coefficient,
                ambient_pressure_pa=self.config.data.nozzles.ambient_pressure_pa,
            )
            for nozzle, is_open in zip(self.config.data.nozzles.items, valve_states, strict=True)
        ]
        regulator = self.regulate_pressure(
            tank_state,
            requested_mass_flow_kg_s=sum(flow.mass_flow_kg_s for flow in preliminary),
        )
        flows = tuple(
            nozzle_flow_rate(
                nozzle=nozzle,
                is_open=is_open,
                pressure_pa=regulator.output_pressure_pa,
                temperature_k=tank_state.temperature_k,
                discharge_coefficient=self.config.data.nozzles.discharge_coefficient,
                ambient_pressure_pa=self.config.data.nozzles.ambient_pressure_pa,
            )
            for nozzle, is_open in zip(self.config.data.nozzles.items, valve_states, strict=True)
        )
        force = np.sum([flow.force_body_n for flow in flows], axis=0)
        torque = np.sum([flow.torque_body_n for flow in flows], axis=0)
        total_mass_flow = sum(flow.mass_flow_kg_s for flow in flows)
        total_thrust = sum(flow.thrust_n for flow in flows)
        return ColdGasForces(
            regulator=regulator,
            flows=flows,
            total_mass_flow_kg_s=total_mass_flow,
            total_thrust_n=total_thrust,
            force_body_n=np.asarray(force, dtype=np.float64),
            torque_body_n=np.asarray(torque, dtype=np.float64),
        )

    def step(
        self,
        tank_state: CO2TankState,
        valve_states: Sequence[bool],
        dt_s: float,
    ) -> ColdGasStepResult:
        if dt_s <= 0.0:
            msg = "dt_s must be positive"
            raise ValueError(msg)
        forces = self.thrust_and_torque(valve_states, tank_state.time_s, tank_state)
        requested_mass_out = forces.total_mass_flow_kg_s * dt_s
        mass_out = min(requested_mass_out, tank_state.total_mass_kg)
        heat_in = (
            self.config.data.tank.heat_transfer_w_per_k
            * (self.config.data.tank.ambient_temperature_k - tank_state.temperature_k)
            * dt_s
        )
        outflow_h = co2_gas_enthalpy_j_kg(
            temperature_k=tank_state.temperature_k,
            pressure_pa=forces.regulator.output_pressure_pa,
        )
        outflow_enthalpy = mass_out * outflow_h
        target_energy = tank_state.total_energy_j - outflow_enthalpy + heat_in
        next_mass = max(0.0, tank_state.total_mass_kg - mass_out)
        next_temperature = self._solve_temperature_for_energy(next_mass, target_energy)
        next_state = self.state_from_mass_temperature(
            time_s=tank_state.time_s + dt_s,
            total_mass_kg=next_mass,
            temperature_k=next_temperature,
        )
        mass_residual = tank_state.total_mass_kg - mass_out - next_state.total_mass_kg
        energy_residual = target_energy - next_state.total_energy_j
        return ColdGasStepResult(
            state=next_state,
            forces=forces,
            mass_out_kg=mass_out,
            heat_in_j=heat_in,
            outflow_enthalpy_j=outflow_enthalpy,
            mass_balance_residual_kg=mass_residual,
            energy_balance_residual_j=energy_residual,
        )

    def _solve_temperature_for_energy(self, total_mass_kg: float, target_energy_j: float) -> float:
        tank = self.config.data.tank
        if total_mass_kg <= 0.0:
            return tank.ambient_temperature_k
        low = MIN_CO2_TEMPERATURE_K
        high = max(tank.ambient_temperature_k + 80.0, tank.initial_temperature_k + 80.0)
        for _ in range(120):
            mid = 0.5 * (low + high)
            energy = self.state_from_mass_temperature(
                time_s=0.0,
                total_mass_kg=total_mass_kg,
                temperature_k=mid,
            ).total_energy_j
            if energy < target_energy_j:
                low = mid
            else:
                high = mid
        return 0.5 * (low + high)


def load_coldgas_config(path: Path | str) -> ColdGasConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{config_path} must contain a YAML mapping"
        raise TypeError(msg)
    return ColdGasConfig.model_validate(raw)


def co2_saturation_pressure_pa(temperature_k: float) -> float:
    return _props("P", "T", temperature_k, "Q", 0.0)


def co2_phase_state(
    total_mass_kg: float,
    temperature_k: float,
    volume_m3: float,
) -> tuple[float, float, float, float]:
    """Return liquid mass, vapor mass, pressure, and CO2 internal energy."""

    if total_mass_kg <= 0.0:
        return (0.0, 0.0, 0.0, 0.0)
    rho_liquid = _props("Dmass", "T", temperature_k, "Q", 0.0)
    rho_vapor = _props("Dmass", "T", temperature_k, "Q", 1.0)
    vapor_capacity = rho_vapor * volume_m3
    liquid_capacity = rho_liquid * volume_m3
    if total_mass_kg <= vapor_capacity:
        density = total_mass_kg / volume_m3
        pressure = _props("P", "T", temperature_k, "Dmass", density)
        internal_energy = total_mass_kg * _props("Umass", "T", temperature_k, "Dmass", density)
        return (0.0, total_mass_kg, pressure, internal_energy)
    if total_mass_kg >= liquid_capacity:
        density = total_mass_kg / volume_m3
        pressure = _props("P", "T", temperature_k, "Dmass", density)
        internal_energy = total_mass_kg * _props("Umass", "T", temperature_k, "Dmass", density)
        return (total_mass_kg, 0.0, pressure, internal_energy)
    vapor_mass = (volume_m3 - total_mass_kg / rho_liquid) / (1.0 / rho_vapor - 1.0 / rho_liquid)
    liquid_mass = total_mass_kg - vapor_mass
    u_liquid = _props("Umass", "T", temperature_k, "Q", 0.0)
    u_vapor = _props("Umass", "T", temperature_k, "Q", 1.0)
    pressure = co2_saturation_pressure_pa(temperature_k)
    internal_energy = liquid_mass * u_liquid + vapor_mass * u_vapor
    return (liquid_mass, vapor_mass, pressure, internal_energy)


def co2_gas_enthalpy_j_kg(temperature_k: float, pressure_pa: float) -> float:
    return _props("Hmass", "T", temperature_k, "P", pressure_pa)


def co2_gamma_and_specific_gas_constant(
    temperature_k: float,
    pressure_pa: float,
) -> tuple[float, float]:
    cp = _props("Cpmass", "T", temperature_k, "P", pressure_pa)
    cv = _props("Cvmass", "T", temperature_k, "P", pressure_pa)
    molar_mass = _co2_constant("M")
    gas_constant = _co2_constant("GAS_CONSTANT") / molar_mass
    return (cp / cv, gas_constant)


def vapor_supply_capacity_kg_s(
    state: CO2TankState,
    evaporation_time_constant_s: float,
) -> float:
    return state.vapor_mass_kg + state.liquid_mass_kg / evaporation_time_constant_s


def nozzle_flow_rate(
    nozzle: NozzleConfig,
    is_open: bool,
    pressure_pa: float,
    temperature_k: float,
    discharge_coefficient: float,
    ambient_pressure_pa: float,
) -> NozzleFlow:
    if not is_open or pressure_pa <= ambient_pressure_pa:
        zero = np.zeros(3, dtype=np.float64)
        return NozzleFlow(
            id=nozzle.id,
            is_open=is_open,
            mass_flow_kg_s=0.0,
            thrust_n=0.0,
            force_body_n=zero,
            torque_body_n=zero,
            choked=False,
        )
    gamma, specific_r = co2_gamma_and_specific_gas_constant(temperature_k, pressure_pa)
    pressure_ratio = ambient_pressure_pa / pressure_pa
    critical_ratio = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))
    choked = pressure_ratio <= critical_ratio
    if choked:
        mass_flux = pressure_pa * math.sqrt(gamma / (specific_r * temperature_k)) * (
            2.0 / (gamma + 1.0)
        ) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
        exit_temperature = temperature_k * 2.0 / (gamma + 1.0)
        exit_pressure = pressure_pa * critical_ratio
        exit_velocity = math.sqrt(gamma * specific_r * exit_temperature)
    else:
        ratio = pressure_ratio
        mass_flux = pressure_pa * math.sqrt(
            (2.0 * gamma / (specific_r * temperature_k * (gamma - 1.0)))
            * (ratio ** (2.0 / gamma) - ratio ** ((gamma + 1.0) / gamma))
        )
        exit_pressure = ambient_pressure_pa
        cp = gamma * specific_r / (gamma - 1.0)
        exit_velocity = math.sqrt(
            max(0.0, 2.0 * cp * temperature_k * (1.0 - pressure_ratio ** ((gamma - 1.0) / gamma)))
        )
    mass_flow = discharge_coefficient * nozzle.throat_area_m2 * mass_flux
    pressure_thrust = max(0.0, exit_pressure - ambient_pressure_pa) * nozzle.throat_area_m2
    thrust = mass_flow * exit_velocity + pressure_thrust
    force = nozzle.unit_axis_array * thrust
    torque = np.cross(np.asarray(nozzle.position_m, dtype=np.float64), force)
    return NozzleFlow(
        id=nozzle.id,
        is_open=True,
        mass_flow_kg_s=mass_flow,
        thrust_n=thrust,
        force_body_n=force,
        torque_body_n=torque,
        choked=choked,
    )
