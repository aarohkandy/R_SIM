"""Deterministic local active rocket simulation for pre-flight design work.

This is not a CFD solver and it is not flight certification. It is a local
dynamic model intended to make active pneumatic configuration, controller
wiring, noise, and result inspection real enough to iterate on before heavier
CFD/table calibration is added.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import asdict, is_dataclass
from typing import Callable, Dict, List, Optional

import numpy as np


ControllerCallback = Callable[[Dict[str, float]], Dict[str, float]]


class ActiveSimulationManager:
    """Runs deterministic local active pneumatic rocket simulations."""

    model_version = "active_pneumatic_local_dynamics_v1"

    def __init__(self):
        self.simulations: Dict[str, Dict] = {}
        self.latest_simulation_id: Optional[str] = None

    @staticmethod
    def _as_float(value, default: float) -> float:
        try:
            if value is None or value == "":
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _as_bool(value, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "enabled", "on"}
        if value is None:
            return default
        return bool(value)

    @staticmethod
    def _first_value(component: Dict, keys: List[str], default):
        for key in keys:
            if key in component and component[key] not in (None, ""):
                return component[key]
        return default

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def submit_cfd_simulation(
        self,
        rocket_data: Dict,
        simulation_config: Dict,
        controller_callback: Optional[ControllerCallback] = None,
    ) -> Dict:
        simulation_id = f"active_{uuid.uuid4().hex[:12]}"
        started_at = time.time()
        config = self._normalize_config(simulation_config)
        results = self._run_local_active_physics(rocket_data, config, controller_callback)
        entry = {
            "success": True,
            "simulation_id": simulation_id,
            "status": "completed",
            "progress": 100,
            "message": "Active pneumatic local simulation completed.",
            "elapsed_time": time.time() - started_at,
            "rocket_components": len(rocket_data.get("components", [])),
            "rocket_weight": rocket_data.get("weight", 0),
            "rocket_cg": rocket_data.get("cg", 0),
            "totalHeight": rocket_data.get("totalHeight"),
            "results": results,
        }
        self.simulations[simulation_id] = entry
        self.latest_simulation_id = simulation_id
        return entry

    def _normalize_config(self, simulation_config):
        if is_dataclass(simulation_config):
            return asdict(simulation_config)
        return simulation_config or {}

    def _run_local_active_physics(
        self,
        rocket_data: Dict,
        config: Dict,
        controller_callback: Optional[ControllerCallback],
    ) -> Dict:
        components = rocket_data.get("components", [])
        active = self._build_active_config(config)
        controller = self._build_controller_config(config, active)
        noise = self._build_noise_config(config)
        rng = np.random.default_rng(noise["seed"])
        warnings: List[str] = []

        mass_input = self._as_float(rocket_data.get("weight"), 250.0)
        mass_kg = mass_input / 1000.0 if mass_input > 20 else mass_input
        mass_kg = max(mass_kg, 0.05)

        total_length_m = self._rocket_length_m(rocket_data, components)
        diameter_m = self._rocket_diameter_m(components)
        frontal_area_m2 = math.pi * (diameter_m / 2.0) ** 2
        fin_count = self._fin_count(components)
        base_cd = 0.48 + 0.025 * max(fin_count, 3)

        motor = next((c for c in components if str(c.get("type", "")).lower() == "motor"), {})
        thrust_n = self._as_float(
            self._first_value(motor, ["motorThrust", "average_thrust", "averageThrust"], 6.0),
            6.0,
        )
        burn_time_s = self._as_float(
            self._first_value(motor, ["motorBurnTime", "burn_time", "burnTime"], 1.6),
            1.6,
        )
        total_impulse_ns = self._as_float(
            self._first_value(motor, ["motorTotalImpulse", "total_impulse", "totalImpulse"], thrust_n * burn_time_s),
            thrust_n * burn_time_s,
        )
        if total_impulse_ns > 0 and burn_time_s > 0:
            thrust_n = max(thrust_n, total_impulse_ns / burn_time_s)

        pressure_pa = self._as_float(config.get("pressure"), 101325.0)
        temp_c = self._as_float(config.get("temperature"), 15.0)
        launch_altitude_m = self._as_float(config.get("launchAltitude") or config.get("launch_altitude"), 0.0)
        density = max(0.45, pressure_pa / (287.05 * (temp_c + 273.15)))
        wind_speed = self._as_float(config.get("windSpeed") or config.get("wind_speed"), 0.0)
        wind_direction_rad = math.radians(self._as_float(config.get("windDirection") or config.get("wind_direction"), 0.0))
        wind_x = wind_speed * math.cos(wind_direction_rad)
        wind_y = wind_speed * math.sin(wind_direction_rad)

        dt = self._clamp(self._as_float(config.get("timeStep") or config.get("time_step"), 0.02), 0.005, 0.1)
        max_time = self._clamp(self._as_float(config.get("maxTime") or config.get("max_time"), 45.0), 3.0, 180.0)
        gravity = 9.80665

        altitude = max(0.0, launch_altitude_m)
        velocity_z = 0.0
        x = 0.0
        y = 0.0
        vx = 0.0
        vy = 0.0
        pitch = math.radians(noise["initial_attitude_deg"] * rng.normal())
        yaw = math.radians(noise["initial_attitude_deg"] * rng.normal())
        roll = 0.0
        pitch_rate = 0.0
        yaw_rate = 0.0
        roll_rate = 0.0

        tank_pressure = active["tank_pressure_pa"]
        actuator_pressure = pressure_pa
        stroke = 0.0
        last_valve = 0.0
        valve_cycles = 0
        controller_failures = 0

        max_altitude = altitude
        max_velocity = 0.0
        max_drag_force = 0.0
        max_dynamic_pressure = 0.0
        max_deployment = 0.0
        max_surface_angle = 0.0
        min_tank_pressure = tank_pressure
        apogee_time = 0.0
        landing_velocity = 0.0
        trajectory = []
        active_history = []
        controller_history = []

        prev_accel_z = 0.0
        t = 0.0
        while t <= max_time:
            speed_air_x = vx - wind_x
            speed_air_y = vy - wind_y
            speed_air_z = velocity_z
            speed_air = math.sqrt(speed_air_x**2 + speed_air_y**2 + speed_air_z**2)
            dynamic_pressure = 0.5 * density * speed_air**2
            deployment_fraction = self._clamp((stroke / active["cylinder_stroke_m"]) * active["linkage_ratio"], 0.0, 1.0)

            sensor = {
                "timestamp": t,
                "altitude": altitude + rng.normal(0.0, noise["altitude_std_m"]),
                "velocity_x": vx + rng.normal(0.0, noise["velocity_std_mps"]),
                "velocity_y": vy + rng.normal(0.0, noise["velocity_std_mps"]),
                "velocity_z": velocity_z + rng.normal(0.0, noise["velocity_std_mps"]),
                "acceleration_x": 0.0,
                "acceleration_y": 0.0,
                "acceleration_z": prev_accel_z + rng.normal(0.0, noise["accel_std_mps2"]),
                "angular_velocity_x": roll_rate,
                "angular_velocity_y": pitch_rate,
                "angular_velocity_z": yaw_rate,
                "pressure": pressure_pa + rng.normal(0.0, noise["ambient_pressure_std_pa"]),
                "temperature": temp_c + rng.normal(0.0, noise["temperature_std_c"]),
                "tank_pressure": tank_pressure + rng.normal(0.0, noise["pneumatic_pressure_std_pa"]),
                "actuator_pressure": actuator_pressure + rng.normal(0.0, noise["pneumatic_pressure_std_pa"]),
                "surface_deployment": deployment_fraction,
                "predicted_apogee": altitude + max(velocity_z, 0.0) ** 2 / (2.0 * gravity),
                "dynamic_pressure": dynamic_pressure,
            }

            valve_command, surface_target, controller_note = self._controller_command(
                sensor,
                controller,
                active,
                pressure_pa,
                controller_callback,
            )
            if controller_note:
                controller_failures += 1
                if controller_failures <= 3:
                    warnings.append(controller_note)

            valve_command = self._clamp(valve_command, 0.0, 1.0 if active["enabled"] else 0.0)
            surface_target = self._clamp(surface_target, 0.0, 1.0 if active["enabled"] else 0.0)
            if abs(valve_command - last_valve) > 0.25:
                valve_cycles += 1
            last_valve = valve_command

            tank_pressure, actuator_pressure, stroke = self._step_pneumatics(
                tank_pressure,
                actuator_pressure,
                stroke,
                valve_command,
                surface_target,
                active,
                pressure_pa,
                dt,
            )
            min_tank_pressure = min(min_tank_pressure, tank_pressure)
            deployment_fraction = self._clamp((stroke / active["cylinder_stroke_m"]) * active["linkage_ratio"], 0.0, 1.0)
            surface_angle_deg = deployment_fraction * active["surface_max_angle_deg"]

            airbrake_area = active["surface_area_m2"] * active["surface_count"] * deployment_fraction
            airbrake_cd = active["surface_cd"] * airbrake_area / max(frontal_area_m2, 1e-6)
            cd = base_cd + airbrake_cd
            drag_force = dynamic_pressure * cd * frontal_area_m2
            drag_z = drag_force * (velocity_z / max(speed_air, 0.1))
            drag_x = drag_force * (speed_air_x / max(speed_air, 0.1))
            drag_y = drag_force * (speed_air_y / max(speed_air, 0.1))
            thrust = thrust_n if t <= burn_time_s else 0.0
            accel_z = (thrust - mass_kg * gravity - drag_z) / mass_kg
            accel_x = -drag_x / mass_kg
            accel_y = -drag_y / mass_kg

            pitch_moment = -0.45 * pitch - 0.16 * pitch_rate + deployment_fraction * 0.015 * math.sin(wind_direction_rad)
            yaw_moment = -0.45 * yaw - 0.16 * yaw_rate + deployment_fraction * 0.015 * math.cos(wind_direction_rad)
            pitch_rate += pitch_moment * dt
            yaw_rate += yaw_moment * dt
            pitch += pitch_rate * dt
            yaw += yaw_rate * dt
            roll_rate *= 0.995
            roll += roll_rate * dt

            velocity_z += accel_z * dt
            vx += accel_x * dt + 0.02 * wind_x * dt
            vy += accel_y * dt + 0.02 * wind_y * dt
            altitude = max(0.0, altitude + velocity_z * dt)
            x += vx * dt
            y += vy * dt
            prev_accel_z = accel_z

            if altitude >= max_altitude:
                max_altitude = altitude
                apogee_time = t
            max_velocity = max(max_velocity, math.sqrt(vx**2 + vy**2 + velocity_z**2))
            max_drag_force = max(max_drag_force, abs(drag_force))
            max_dynamic_pressure = max(max_dynamic_pressure, dynamic_pressure)
            max_deployment = max(max_deployment, deployment_fraction)
            max_surface_angle = max(max_surface_angle, surface_angle_deg)

            if len(trajectory) == 0 or t - trajectory[-1]["time"] >= 0.1:
                sample = {
                    "time": round(t, 3),
                    "altitude": round(altitude, 4),
                    "downrange_x": round(x, 4),
                    "crossrange_y": round(y, 4),
                    "velocity_z": round(velocity_z, 4),
                    "speed": round(math.sqrt(vx**2 + vy**2 + velocity_z**2), 4),
                    "acceleration_z": round(accel_z, 4),
                    "pitch_deg": round(math.degrees(pitch), 4),
                    "yaw_deg": round(math.degrees(yaw), 4),
                    "roll_deg": round(math.degrees(roll), 4),
                    "dynamic_pressure": round(dynamic_pressure, 4),
                    "drag_force": round(drag_force, 4),
                    "valve_command": round(valve_command, 4),
                    "surface_deployment": round(deployment_fraction, 4),
                    "surface_angle_deg": round(surface_angle_deg, 4),
                    "tank_pressure": round(tank_pressure, 2),
                    "actuator_pressure": round(actuator_pressure, 2),
                }
                trajectory.append(sample)
                active_history.append({
                    "time": sample["time"],
                    "tank_pressure": sample["tank_pressure"],
                    "actuator_pressure": sample["actuator_pressure"],
                    "stroke_m": round(stroke, 5),
                    "surface_deployment": sample["surface_deployment"],
                    "surface_angle_deg": sample["surface_angle_deg"],
                    "valve_command": sample["valve_command"],
                })
                controller_history.append({
                    "time": sample["time"],
                    "mode": controller["mode"],
                    "predicted_apogee": round(sensor["predicted_apogee"], 4),
                    "command": sample["valve_command"],
                    "surface_target": round(surface_target, 4),
                })

            t += dt
            if t > burn_time_s and altitude <= 0.0 and velocity_z < 0.0:
                landing_velocity = abs(velocity_z)
                break

        if active["enabled"] and max_deployment < 0.01:
            warnings.append("Active system was enabled but never deployed; check controller threshold and pressure settings.")
        if active["enabled"] and min_tank_pressure < active["min_operating_pressure_pa"]:
            warnings.append("Tank pressure fell below minimum operating pressure during flight.")
        if max_dynamic_pressure > active["max_dynamic_pressure_pa"]:
            warnings.append("Dynamic pressure exceeded configured active-system structural limit.")

        total_time = max(t, burn_time_s)
        downrange = math.sqrt(x**2 + y**2)
        cg_m = self._as_float(rocket_data.get("cg"), total_length_m * 470.0)
        cg_m = cg_m / 1000.0 if cg_m > 5 else cg_m
        cp_m = total_length_m * (0.61 + min(0.08, 0.01 * fin_count))
        stability_margin = max(0.05, (cp_m - cg_m) / diameter_m)

        return {
            "source": "active_pneumatic_local_dynamics",
            "model_version": self.model_version,
            "is_placeholder": False,
            "max_altitude": max_altitude,
            "max_velocity": max_velocity,
            "total_flight_time": total_time,
            "apogee_time": apogee_time,
            "landing_velocity": landing_velocity,
            "downrange_distance": downrange,
            "motor_thrust": thrust_n,
            "motor_burn_time": burn_time_s,
            "total_impulse": total_impulse_ns,
            "stability_margin": stability_margin,
            "drag_coefficient": base_cd,
            "lift_coefficient": 0.0,
            "max_drag_force": max_drag_force,
            "max_dynamic_pressure": max_dynamic_pressure,
            "pressure_distribution": "local_dynamic_pressure_estimate",
            "velocity_field": "local_trajectory_air_relative_profile",
            "trajectory_data": "time_history_included",
            "trajectory": trajectory,
            "active_system": {
                "enabled": active["enabled"],
                "type": "pneumatic_airbrake",
                "tank_pressure_start": active["tank_pressure_pa"],
                "tank_pressure_final": tank_pressure,
                "tank_pressure_min": min_tank_pressure,
                "actuator_pressure_final": actuator_pressure,
                "max_surface_deployment": max_deployment,
                "max_surface_angle_deg": max_surface_angle,
                "max_surface_area_m2": active["surface_area_m2"] * active["surface_count"],
                "valve_cycles": valve_cycles,
                "history": active_history,
            },
            "controller": {
                "mode": controller["mode"],
                "target_apogee": controller["target_apogee_m"],
                "compiled_cpp": bool(controller_callback),
                "failures": controller_failures,
                "history": controller_history,
            },
            "noise": {
                "seed": noise["seed"],
                "altitude_std_m": noise["altitude_std_m"],
                "velocity_std_mps": noise["velocity_std_mps"],
                "pressure_std_pa": noise["pneumatic_pressure_std_pa"],
            },
            "warnings": warnings,
            "notes": "Local dynamic model with pneumatic actuator coupling; optional CFD/table calibration remains future work.",
        }

    def _build_active_config(self, config: Dict) -> Dict:
        active = config.get("activeSystem") or {}
        enabled = self._as_bool(active.get("enabled"), self._as_bool(config.get("activePneumaticEnabled"), False))
        surface_count = int(self._clamp(self._as_float(active.get("surfaceCount"), 3), 1, 8))
        return {
            "enabled": enabled,
            "tank_pressure_pa": self._as_float(active.get("tankPressure"), 650000.0),
            "tank_volume_l": self._as_float(active.get("tankVolume"), 0.18),
            "regulator_pressure_pa": self._as_float(active.get("regulatorPressure"), 450000.0),
            "min_operating_pressure_pa": self._as_float(active.get("minOperatingPressure"), 180000.0),
            "valve_flow_rate": self._as_float(active.get("valveFlowRate"), 14.0),
            "vent_rate": self._as_float(active.get("ventRate"), 2.5),
            "line_volume_l": self._as_float(active.get("lineVolume"), 0.035),
            "cylinder_bore_m": self._as_float(active.get("cylinderBore"), 0.012),
            "cylinder_stroke_m": max(0.002, self._as_float(active.get("cylinderStroke"), 0.035)),
            "cylinder_friction_n": self._as_float(active.get("cylinderFriction"), 5.0),
            "return_spring_n": self._as_float(active.get("returnSpring"), 18.0),
            "linkage_ratio": self._as_float(active.get("linkageRatio"), 1.0),
            "surface_max_angle_deg": self._as_float(active.get("surfaceMaxAngle"), 65.0),
            "surface_area_m2": self._as_float(active.get("surfaceArea"), 0.0024),
            "surface_count": surface_count,
            "surface_cd": self._as_float(active.get("surfaceCd"), 1.35),
            "location_from_nose_m": self._as_float(active.get("locationFromNose"), 0.42),
            "max_dynamic_pressure_pa": self._as_float(active.get("maxDynamicPressure"), 85000.0),
        }

    def _build_controller_config(self, config: Dict, active: Dict) -> Dict:
        controller = config.get("controller") or {}
        mode = controller.get("mode") or config.get("activeFinControl") or "target_apogee"
        if mode == "enabled":
            mode = "target_apogee"
        if not active["enabled"]:
            mode = "disabled"
        return {
            "mode": mode,
            "target_apogee_m": self._as_float(controller.get("targetApogee"), 240.0),
            "deploy_altitude_m": self._as_float(controller.get("deployAltitude"), 60.0),
            "descent_deploy_altitude_m": self._as_float(controller.get("descentDeployAltitude"), 160.0),
            "kp": self._as_float(controller.get("kp"), 0.012),
            "kd": self._as_float(controller.get("kd"), 0.018),
            "minimum_command": self._as_float(controller.get("minimumCommand"), 0.03),
        }

    def _build_noise_config(self, config: Dict) -> Dict:
        noise = config.get("noise") or {}
        return {
            "seed": int(self._as_float(noise.get("seed"), 20260625)),
            "altitude_std_m": self._as_float(noise.get("altitudeStd"), 0.15),
            "velocity_std_mps": self._as_float(noise.get("velocityStd"), 0.05),
            "accel_std_mps2": self._as_float(noise.get("accelStd"), 0.12),
            "ambient_pressure_std_pa": self._as_float(noise.get("ambientPressureStd"), 8.0),
            "pneumatic_pressure_std_pa": self._as_float(noise.get("pneumaticPressureStd"), 120.0),
            "temperature_std_c": self._as_float(noise.get("temperatureStd"), 0.05),
            "initial_attitude_deg": self._as_float(noise.get("initialAttitudeStd"), 0.35),
        }

    def _controller_command(
        self,
        sensor: Dict[str, float],
        controller: Dict,
        active: Dict,
        ambient_pressure: float,
        controller_callback: Optional[ControllerCallback],
    ):
        if controller["mode"] == "disabled" or not active["enabled"]:
            return 0.0, 0.0, ""

        if controller_callback is not None:
            try:
                output = controller_callback(sensor)
                valve = self._as_float(output.get("valve_command"), self._as_float(output.get("fin_deflection_1"), 0.0) / 15.0)
                surface = self._as_float(output.get("surface_target"), valve)
                return valve, surface, ""
            except Exception as exc:
                return 0.0, 0.0, f"Controller execution failed and built-in fallback was used: {exc}"

        if controller["mode"] == "descent_brake":
            descending = sensor["velocity_z"] < -0.5
            low_enough = sensor["altitude"] < controller["descent_deploy_altitude_m"]
            command = 1.0 if descending and low_enough else 0.0
            return command, command, ""

        predicted_error = sensor["predicted_apogee"] - controller["target_apogee_m"]
        damping = max(sensor["velocity_z"], 0.0) * controller["kd"]
        command = controller["kp"] * predicted_error + damping
        if sensor["altitude"] < controller["deploy_altitude_m"] and sensor["velocity_z"] > 0:
            command = 0.0
        if command > controller["minimum_command"]:
            return self._clamp(command, 0.0, 1.0), self._clamp(command, 0.0, 1.0), ""
        return 0.0, 0.0, ""

    def _step_pneumatics(
        self,
        tank_pressure: float,
        actuator_pressure: float,
        stroke: float,
        valve_command: float,
        surface_target: float,
        active: Dict,
        ambient_pressure: float,
        dt: float,
    ):
        regulated_pressure = min(tank_pressure, active["regulator_pressure_pa"])
        fill_rate = active["valve_flow_rate"] * valve_command
        vent_rate = active["vent_rate"] * max(0.0, 1.0 - valve_command)
        actuator_pressure += (regulated_pressure - actuator_pressure) * (1.0 - math.exp(-fill_rate * dt))
        actuator_pressure += (ambient_pressure - actuator_pressure) * (1.0 - math.exp(-vent_rate * dt))
        actuator_pressure = max(ambient_pressure, actuator_pressure)

        cylinder_area = math.pi * (active["cylinder_bore_m"] / 2.0) ** 2
        pressure_force = max(0.0, actuator_pressure - ambient_pressure) * cylinder_area
        spring_force = active["return_spring_n"] * (stroke / active["cylinder_stroke_m"])
        net_force = pressure_force - spring_force - active["cylinder_friction_n"]
        pressure_target = self._clamp(net_force / max(pressure_force + active["return_spring_n"], 1.0), 0.0, 1.0)
        target_fraction = max(pressure_target, surface_target * valve_command)
        stroke_target = target_fraction * active["cylinder_stroke_m"]
        actuator_rate = 18.0 if stroke_target >= stroke else 7.5
        stroke += (stroke_target - stroke) * (1.0 - math.exp(-actuator_rate * dt))
        stroke = self._clamp(stroke, 0.0, active["cylinder_stroke_m"])

        tank_volume_scale = max(active["tank_volume_l"], 0.01)
        pressure_drop = valve_command * max(tank_pressure - actuator_pressure, 0.0) * dt * 0.012 / tank_volume_scale
        tank_pressure = max(ambient_pressure, tank_pressure - pressure_drop)
        return tank_pressure, actuator_pressure, stroke

    def _rocket_length_m(self, rocket_data: Dict, components: List[Dict]) -> float:
        total = 0.0
        for component in components:
            if str(component.get("type", "")).lower() in {"fins", "motor"}:
                continue
            total += self._as_float(self._first_value(component, ["length", "totalHeight"], 0.0), 0.0)
        if total <= 0:
            total = self._as_float(rocket_data.get("totalHeight"), 680.0)
        return max(0.2, total / 1000.0 if total > 5 else total)

    def _rocket_diameter_m(self, components: List[Dict]) -> float:
        diameters = []
        for component in components:
            diameter = self._as_float(
                self._first_value(component, ["diameter", "bottomDiameter", "topDiameter"], 0.0),
                0.0,
            )
            if diameter > 0:
                diameters.append(diameter)
        diameter = max(diameters) if diameters else 40.0
        return max(0.01, diameter / 1000.0 if diameter > 1 else diameter)

    def _fin_count(self, components: List[Dict]) -> int:
        total = 0
        for component in components:
            if str(component.get("type", "")).lower() == "fins":
                total += int(self._as_float(self._first_value(component, ["finCount", "fin_count"], 3), 3))
        return total or 3

    def get_status(self, simulation_id: Optional[str] = None) -> Dict:
        target_id = simulation_id or self.latest_simulation_id
        if not target_id:
            return {
                "status": "idle",
                "progress": 0,
                "message": "No active simulation has run.",
            }
        return self.simulations.get(target_id, {
            "status": "error",
            "progress": 0,
            "message": f"Simulation {target_id} not found.",
        })

    def stop_simulation(self, simulation_id: Optional[str] = None) -> Dict:
        target_id = simulation_id or self.latest_simulation_id
        if target_id and target_id in self.simulations:
            self.simulations[target_id]["status"] = "stopped"
            self.simulations[target_id]["message"] = "Active local simulation stopped."
            return {"success": True, "status": "stopped", "simulation_id": target_id}
        return {"success": False, "error": "Simulation not found"}

