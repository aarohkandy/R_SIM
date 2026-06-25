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

    def _distance_m(self, value, default: float) -> float:
        distance = self._as_float(value, default)
        return distance / 1000.0 if abs(distance) > 5 else distance

    @staticmethod
    def _first_value(component: Dict, keys: List[str], default):
        for key in keys:
            if key in component and component[key] not in (None, ""):
                return component[key]
        return default

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _distance_xy(x: Optional[float], y: Optional[float]) -> Optional[float]:
        if x is None or y is None:
            return None
        return math.sqrt(x * x + y * y)

    @staticmethod
    def _bearing_deg(x: Optional[float], y: Optional[float]) -> Optional[float]:
        if x is None or y is None or (abs(x) < 1e-9 and abs(y) < 1e-9):
            return None
        return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

    @staticmethod
    def _normalize_deploy_event(value, default: str) -> str:
        raw = str(value or default).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "altitude_on_descent": "altitude",
            "descent": "altitude",
            "main_altitude": "altitude",
            "motor": "motor_ejection",
            "ejection": "motor_ejection",
            "motor_delay": "motor_ejection",
            "motor_ejection_charge": "motor_ejection",
        }
        return aliases.get(raw, raw)

    def submit_cfd_simulation(
        self,
        rocket_data: Dict,
        simulation_config: Dict,
        controller_callback: Optional[ControllerCallback] = None,
    ) -> Dict:
        simulation_id = f"active_{uuid.uuid4().hex[:12]}"
        started_at = time.time()
        config = self._normalize_config(simulation_config)
        validation = self.validate_inputs(rocket_data, config)
        if validation["errors"]:
            return {
                "success": False,
                "error": "Input validation failed.",
                "validation_errors": validation["errors"],
                "validation_warnings": validation["warnings"],
            }
        results = self._run_local_active_physics(rocket_data, config, controller_callback)
        results["input_validation"] = validation
        results["warnings"] = validation["warnings"] + results.get("warnings", [])
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

    def validate_inputs(self, rocket_data: Dict, config: Dict) -> Dict[str, List[str]]:
        errors: List[str] = []
        warnings: List[str] = []
        components = rocket_data.get("components", [])
        if not isinstance(components, list) or not components:
            errors.append("Rocket must include at least one component.")

        mass_input = self._as_float(rocket_data.get("weight"), 0.0)
        if mass_input <= 0:
            errors.append("Rocket weight must be positive.")

        motor_delay = 0.0
        motor = next((c for c in components if str(c.get("type", "")).lower() == "motor"), None)
        if motor is None:
            errors.append("Rocket must include a motor.")
        else:
            burn_time = self._as_float(self._first_value(motor, ["motorBurnTime", "burn_time", "burnTime"], 0.0), 0.0)
            thrust = self._as_float(self._first_value(motor, ["motorThrust", "average_thrust", "averageThrust"], 0.0), 0.0)
            impulse = self._as_float(self._first_value(motor, ["motorTotalImpulse", "total_impulse", "totalImpulse"], 0.0), 0.0)
            motor_delay = self._as_float(self._first_value(motor, ["motorDelay", "delay_time", "delay"], 0.0), 0.0)
            if burn_time <= 0:
                errors.append("Motor burn time must be positive.")
            if thrust <= 0 and impulse <= 0:
                errors.append("Motor thrust or total impulse must be positive.")
            if motor_delay < 0:
                errors.append("Motor delay must not be negative.")
            raw_curve = (
                motor.get("thrustCurve")
                or motor.get("thrust_curve")
                or motor.get("thrustCurvePoints")
            )
            if raw_curve:
                thrust_curve = self._parse_thrust_curve(motor)
                if not thrust_curve:
                    errors.append("Motor thrust curve must include at least two valid time/thrust points.")
                else:
                    curve_impulse = self._integrate_curve(thrust_curve)
                    if curve_impulse <= 0:
                        errors.append("Motor thrust curve impulse must be positive.")
                    if thrust_curve[0][1] > max(thrust_curve[-1][1], 0.5):
                        warnings.append("Motor thrust curve starts above zero thrust; check ignition timing.")
                    if thrust_curve[-1][1] > 0.5:
                        warnings.append("Motor thrust curve ends above zero thrust; check burnout timing.")

        if self._rocket_diameter_m(components) <= 0.01 and components:
            warnings.append("Rocket diameter is very small; check units.")

        dt_raw = self._as_float(config.get("timeStep") or config.get("time_step"), 0.02)
        max_time_raw = self._as_float(config.get("maxTime") or config.get("max_time"), 45.0)
        if dt_raw <= 0:
            errors.append("Simulation time step must be positive.")
        if max_time_raw <= 0:
            errors.append("Simulation max time must be positive.")
        if dt_raw > 0.1:
            warnings.append("Time step is large and will be clamped to 0.1 s.")

        pressure_pa = self._as_float(config.get("pressure"), 101325.0)
        active = config.get("activeSystem") or {}
        active_enabled = self._as_bool(active.get("enabled"), self._as_bool(config.get("activePneumaticEnabled"), False))
        if active_enabled:
            tank_pressure = self._as_float(active.get("tankPressure"), 650000.0)
            tank_volume = self._as_float(active.get("tankVolume"), 0.18)
            regulator_pressure = self._as_float(active.get("regulatorPressure"), 450000.0)
            min_operating_pressure = self._as_float(active.get("minOperatingPressure"), 180000.0)
            cylinder_bore = self._as_float(active.get("cylinderBore"), 0.012)
            cylinder_stroke = self._as_float(active.get("cylinderStroke"), 0.035)
            surface_area = self._as_float(active.get("surfaceArea"), 0.0024)
            surface_count = self._as_float(active.get("surfaceCount"), 3.0)
            valve_flow = self._as_float(active.get("valveFlowRate"), 14.0)

            if tank_pressure <= pressure_pa:
                errors.append("Active tank pressure must be above ambient pressure.")
            if tank_pressure < min_operating_pressure:
                warnings.append("Tank pressure starts below minimum operating pressure.")
            if tank_volume <= 0:
                errors.append("Active tank volume must be positive.")
            if regulator_pressure <= pressure_pa:
                errors.append("Regulator pressure must be above ambient pressure.")
            if cylinder_bore <= 0:
                errors.append("Cylinder bore must be positive.")
            if cylinder_stroke <= 0:
                errors.append("Cylinder stroke must be positive.")
            if surface_area <= 0:
                errors.append("Active surface area must be positive.")
            if surface_count < 1:
                errors.append("Active surface count must be at least 1.")
            if valve_flow <= 0:
                errors.append("Valve flow rate must be positive.")
            active_location = self._distance_m(active.get("locationFromNose"), 0.42)
            total_length_m = self._rocket_length_m(rocket_data, components)
            if active_location < 0 or active_location > total_length_m:
                errors.append("Active airbrake location must be inside the rocket length.")

        controller = config.get("controller") or {}
        if controller.get("mode", "target_apogee") == "target_apogee":
            target_apogee = self._as_float(controller.get("targetApogee"), 240.0)
            if target_apogee <= 0:
                errors.append("Target apogee must be positive.")

        guide_length = self._as_float(
            self._first_value(config, ["launchGuideLength", "launchRodLength", "railLength"], 1.5),
            1.5,
        )
        guide_angle = self._as_float(
            self._first_value(config, ["launchGuideAngle", "launchAngle", "railAngle"], 0.0),
            0.0,
        )
        min_exit_velocity = self._as_float(
            self._first_value(config, ["minRailExitVelocity", "minGuideExitVelocity"], 12.0),
            12.0,
        )
        if guide_length <= 0:
            errors.append("Launch guide length must be positive.")
        if guide_angle < 0 or guide_angle > 30:
            errors.append("Launch guide angle must be between 0 and 30 degrees.")
        if min_exit_velocity <= 0:
            errors.append("Minimum launch guide exit velocity must be positive.")

        landing = config.get("landingSystem") or config.get("recoverySystem") or {}
        landing_enabled = self._as_bool(landing.get("enabled"), True)
        if landing_enabled:
            system_type = landing.get("type") or landing.get("systemType") or "main_parachute"
            deploy_altitude = self._as_float(landing.get("deployAltitude"), 120.0)
            drogue_deploy_altitude = self._as_float(landing.get("drogueDeployAltitude"), deploy_altitude)
            drag_area = self._as_float(landing.get("dragArea"), 0.18)
            drag_coefficient = self._as_float(landing.get("dragCoefficient"), 1.55)
            max_safe_velocity = self._as_float(landing.get("maxSafeVelocity"), 7.5)
            max_opening_load_g = self._as_float(landing.get("maxOpeningLoadG"), 15.0)
            drogue_drag_area = self._as_float(landing.get("drogueDragArea"), 0.04)
            drogue_drag_coefficient = self._as_float(landing.get("drogueDragCoefficient"), 1.25)
            valid_events = {"apogee", "altitude", "motor_ejection"}
            main_event = self._normalize_deploy_event(
                self._first_value(landing, ["mainDeployEvent", "deployEvent", "deploymentEvent"], "altitude"),
                "altitude",
            )
            drogue_event = self._normalize_deploy_event(
                self._first_value(landing, ["drogueDeployEvent", "drogueDeploymentEvent"], "apogee"),
                "apogee",
            )
            if deploy_altitude <= 0:
                errors.append("Landing deploy altitude must be positive.")
            if drag_area <= 0:
                errors.append("Landing drag area must be positive.")
            if drag_coefficient <= 0:
                errors.append("Landing drag coefficient must be positive.")
            if max_safe_velocity <= 0:
                errors.append("Landing safe touchdown velocity must be positive.")
            if max_opening_load_g <= 0:
                errors.append("Landing maximum opening load must be positive.")
            if main_event not in valid_events:
                errors.append("Main recovery deploy event must be apogee, altitude, or motor_ejection.")
            if main_event == "motor_ejection" and motor_delay <= 0:
                warnings.append("Main recovery uses motor ejection but motor delay is not set.")
            if system_type == "drogue_main":
                if drogue_event not in valid_events:
                    errors.append("Drogue recovery deploy event must be apogee, altitude, or motor_ejection.")
                if drogue_event == "altitude" and drogue_deploy_altitude <= 0:
                    errors.append("Drogue deploy altitude must be positive.")
                if drogue_event == "motor_ejection" and motor_delay <= 0:
                    warnings.append("Drogue recovery uses motor ejection but motor delay is not set.")
                if drogue_drag_area <= 0:
                    errors.append("Drogue drag area must be positive.")
                if drogue_drag_coefficient <= 0:
                    errors.append("Drogue drag coefficient must be positive.")

        return {"errors": errors, "warnings": warnings}

    def _run_local_active_physics(
        self,
        rocket_data: Dict,
        config: Dict,
        controller_callback: Optional[ControllerCallback],
    ) -> Dict:
        components = rocket_data.get("components", [])
        active = self._build_active_config(config)
        controller = self._build_controller_config(config, active)
        landing = self._build_landing_config(config)
        noise = self._build_noise_config(config)
        rng = np.random.default_rng(noise["seed"])
        warnings: List[str] = []

        mass_input = self._as_float(rocket_data.get("weight"), 250.0)
        mass_kg = mass_input / 1000.0 if mass_input > 20 else mass_input
        mass_kg = max(mass_kg, 0.05)

        total_length_m = self._rocket_length_m(rocket_data, components)
        diameter_m = self._rocket_diameter_m(components)
        frontal_area_m2 = math.pi * (diameter_m / 2.0) ** 2
        cg_m = self._distance_m(rocket_data.get("cg"), total_length_m * 0.47)
        active["location_from_nose_m"] = self._clamp(active["location_from_nose_m"], 0.0, total_length_m)
        active["moment_arm_m"] = active["location_from_nose_m"] - cg_m
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
        motor_delay_s = self._as_float(
            self._first_value(motor, ["motorDelay", "delay_time", "delay"], 0.0),
            0.0,
        )
        total_impulse_ns = self._as_float(
            self._first_value(motor, ["motorTotalImpulse", "total_impulse", "totalImpulse"], thrust_n * burn_time_s),
            thrust_n * burn_time_s,
        )
        if total_impulse_ns > 0 and burn_time_s > 0:
            thrust_n = max(thrust_n, total_impulse_ns / burn_time_s)
        thrust_curve = self._parse_thrust_curve(motor)
        curve_total_impulse_ns = None
        if thrust_curve:
            burn_time_s = max(burn_time_s, thrust_curve[-1][0])
            curve_total_impulse_ns = self._integrate_curve(thrust_curve)
            total_impulse_ns = curve_total_impulse_ns
            thrust_n = max(thrust_n, curve_total_impulse_ns / max(burn_time_s, 0.001))

        pressure_pa = self._as_float(config.get("pressure"), 101325.0)
        temp_c = self._as_float(config.get("temperature"), 15.0)
        launch_altitude_m = self._as_float(config.get("launchAltitude") or config.get("launch_altitude"), 0.0)
        density = max(0.45, pressure_pa / (287.05 * (temp_c + 273.15)))
        wind_speed = self._as_float(config.get("windSpeed") or config.get("wind_speed"), 0.0)
        wind_direction_rad = math.radians(self._as_float(config.get("windDirection") or config.get("wind_direction"), 0.0))
        wind_x = wind_speed * math.cos(wind_direction_rad)
        wind_y = wind_speed * math.sin(wind_direction_rad)
        launch_guide = self._build_launch_guide_config(config, mass_kg, thrust_n, burn_time_s)
        launch_angle_rad = math.radians(launch_guide["angle_deg"])
        launch_direction_rad = math.radians(launch_guide["direction_deg"])
        launch_axis_x = math.sin(launch_angle_rad) * math.cos(launch_direction_rad)
        launch_axis_y = math.sin(launch_angle_rad) * math.sin(launch_direction_rad)
        launch_axis_z = math.cos(launch_angle_rad)

        dt = self._clamp(self._as_float(config.get("timeStep") or config.get("time_step"), 0.02), 0.005, 0.1)
        max_time = self._clamp(self._as_float(config.get("maxTime") or config.get("max_time"), 45.0), 3.0, 180.0)
        gravity = 9.80665
        aero = self._build_aero_config(config, base_cd)
        inertia_pitch = max(mass_kg * total_length_m**2 / 12.0, 1e-5)
        inertia_roll = max(0.5 * mass_kg * (diameter_m / 2.0) ** 2, 1e-6)

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
        landing_deployed = False
        landing_deploy_time = None
        landing_deploy_altitude = None
        landing_deploy_x = None
        landing_deploy_y = None
        landing_deploy_velocity_z = None
        landing_deploy_speed_air = None
        drogue_deployed = False
        drogue_deploy_time = None
        drogue_deploy_altitude = None
        drogue_deploy_x = None
        drogue_deploy_y = None
        drogue_deploy_velocity_z = None
        drogue_deploy_speed_air = None

        max_altitude = altitude
        apogee_x = x
        apogee_y = y
        max_velocity = 0.0
        max_drag_force = 0.0
        max_net_force = 0.0
        max_dynamic_pressure = 0.0
        max_deployment = 0.0
        max_deployment_time = 0.0
        max_surface_angle = 0.0
        max_drag_coefficient = base_cd
        max_active_drag_force = 0.0
        max_attitude_deg = 0.0
        max_angular_rate_deg_s = 0.0
        min_tank_pressure = tank_pressure
        apogee_time = 0.0
        landing_velocity = 0.0
        touchdown_time = None
        guide_clear_time = None
        guide_exit_velocity = None
        guide_clear_altitude = None
        trajectory = []
        active_history = []
        landing_history = []
        controller_history = []
        force_history = []
        moment_history = []

        prev_accel_z = 0.0
        t = 0.0
        motor_ejection_time_s = burn_time_s + motor_delay_s if motor_delay_s > 0 else None
        while t <= max_time:
            speed_air_x = vx - wind_x
            speed_air_y = vy - wind_y
            speed_air_z = velocity_z
            speed_air = math.sqrt(speed_air_x**2 + speed_air_y**2 + speed_air_z**2)
            dynamic_pressure = 0.5 * density * speed_air**2
            deployment_fraction = self._clamp((stroke / active["cylinder_stroke_m"]) * active["linkage_ratio"], 0.0, 1.0)
            apogee_detected = velocity_z < -0.5
            if landing["enabled"]:
                if (
                    landing["system_type"] == "drogue_main"
                    and not drogue_deployed
                    and self._should_deploy_recovery(
                        landing["drogue_deploy_event"],
                        t=t,
                        altitude=altitude,
                        velocity_z=velocity_z,
                        deploy_altitude_m=landing["drogue_deploy_altitude_m"],
                        apogee_detected=apogee_detected,
                        motor_ejection_time_s=motor_ejection_time_s,
                    )
                ):
                    drogue_deployed = True
                    drogue_deploy_time = t
                    drogue_deploy_altitude = altitude
                    drogue_deploy_x = x
                    drogue_deploy_y = y
                    drogue_deploy_velocity_z = velocity_z
                    drogue_deploy_speed_air = speed_air

                if (
                    not landing_deployed
                    and self._should_deploy_recovery(
                        landing["main_deploy_event"],
                        t=t,
                        altitude=altitude,
                        velocity_z=velocity_z,
                        deploy_altitude_m=landing["deploy_altitude_m"],
                        apogee_detected=apogee_detected,
                        motor_ejection_time_s=motor_ejection_time_s,
                    )
                ):
                    landing_deployed = True
                    landing_deploy_time = t
                    landing_deploy_altitude = altitude
                    landing_deploy_x = x
                    landing_deploy_y = y
                    landing_deploy_velocity_z = velocity_z
                    landing_deploy_speed_air = speed_air

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

            cd = self._effective_drag_coefficient(
                deployment_fraction,
                active,
                aero,
                frontal_area_m2,
            )
            active_cd_increment = max(0.0, cd - aero["base_cd"])
            active_drag_force = dynamic_pressure * active_cd_increment * frontal_area_m2
            drogue_deployment = 1.0 if drogue_deployed else 0.0
            main_deployment = 1.0 if landing_deployed else 0.0
            landing_deployment = 1.0 if landing_deployed else (0.35 if drogue_deployed else 0.0)
            landing_cd = self._landing_drag_coefficient(landing, drogue_deployment, main_deployment, frontal_area_m2)
            cd += landing_cd
            drag_force = dynamic_pressure * cd * frontal_area_m2
            drag_z = drag_force * (velocity_z / max(speed_air, 0.1))
            drag_x = drag_force * (speed_air_x / max(speed_air, 0.1))
            drag_y = drag_force * (speed_air_y / max(speed_air, 0.1))
            thrust = self._thrust_at_time(t, thrust_curve, thrust_n, burn_time_s)
            thrust_x = thrust * launch_axis_x
            thrust_y = thrust * launch_axis_y
            thrust_z = thrust * launch_axis_z
            weight_force = mass_kg * gravity
            accel_z = (thrust_z - mass_kg * gravity - drag_z) / mass_kg
            accel_x = (thrust_x - drag_x) / mass_kg
            accel_y = (thrust_y - drag_y) / mass_kg
            net_force_x = accel_x * mass_kg
            net_force_y = accel_y * mass_kg
            net_force_z = accel_z * mass_kg

            active_pitch_moment_nm = active_drag_force * active["moment_arm_m"] * 0.006 * math.sin(wind_direction_rad)
            active_yaw_moment_nm = active_drag_force * active["moment_arm_m"] * 0.006 * math.cos(wind_direction_rad)
            pitch_angular_accel = (
                -0.45 * pitch
                - 0.16 * pitch_rate
                + deployment_fraction * 0.015 * math.sin(wind_direction_rad)
                + active_pitch_moment_nm / inertia_pitch
            )
            yaw_angular_accel = (
                -0.45 * yaw
                - 0.16 * yaw_rate
                + deployment_fraction * 0.015 * math.cos(wind_direction_rad)
                + active_yaw_moment_nm / inertia_pitch
            )
            roll_angular_accel = -0.08 * roll_rate
            pitch_moment_nm = pitch_angular_accel * inertia_pitch
            yaw_moment_nm = yaw_angular_accel * inertia_pitch
            roll_moment_nm = roll_angular_accel * inertia_roll
            pitch_rate += pitch_angular_accel * dt
            yaw_rate += yaw_angular_accel * dt
            roll_rate += roll_angular_accel * dt
            pitch += pitch_rate * dt
            yaw += yaw_rate * dt
            roll += roll_rate * dt

            velocity_z += accel_z * dt
            vx += accel_x * dt + 0.02 * wind_x * dt
            vy += accel_y * dt + 0.02 * wind_y * dt
            altitude = max(0.0, altitude + velocity_z * dt)
            x += vx * dt
            y += vy * dt
            prev_accel_z = accel_z
            if guide_clear_time is None:
                guide_distance = (
                    x * launch_axis_x
                    + y * launch_axis_y
                    + max(0.0, altitude - launch_altitude_m) * launch_axis_z
                )
                if guide_distance >= launch_guide["length_m"]:
                    guide_clear_time = t
                    guide_exit_velocity = max(0.0, vx * launch_axis_x + vy * launch_axis_y + velocity_z * launch_axis_z)
                    guide_clear_altitude = altitude

            if altitude >= max_altitude:
                max_altitude = altitude
                apogee_time = t
                apogee_x = x
                apogee_y = y
            max_velocity = max(max_velocity, math.sqrt(vx**2 + vy**2 + velocity_z**2))
            max_drag_force = max(max_drag_force, abs(drag_force))
            max_net_force = max(max_net_force, math.sqrt(net_force_x**2 + net_force_y**2 + net_force_z**2))
            max_dynamic_pressure = max(max_dynamic_pressure, dynamic_pressure)
            if deployment_fraction >= max_deployment:
                max_deployment = deployment_fraction
                max_deployment_time = t
            max_surface_angle = max(max_surface_angle, surface_angle_deg)
            max_drag_coefficient = max(max_drag_coefficient, cd)
            max_active_drag_force = max(max_active_drag_force, active_drag_force)
            max_attitude_deg = max(max_attitude_deg, abs(math.degrees(pitch)), abs(math.degrees(yaw)), abs(math.degrees(roll)))
            max_angular_rate_deg_s = max(
                max_angular_rate_deg_s,
                abs(math.degrees(pitch_rate)),
                abs(math.degrees(yaw_rate)),
                abs(math.degrees(roll_rate)),
            )

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
                    "angular_velocity_x_deg_s": round(math.degrees(roll_rate), 4),
                    "angular_velocity_y_deg_s": round(math.degrees(pitch_rate), 4),
                    "angular_velocity_z_deg_s": round(math.degrees(yaw_rate), 4),
                    "dynamic_pressure": round(dynamic_pressure, 4),
                    "drag_coefficient": round(cd, 5),
                    "landing_deployment": round(landing_deployment, 4),
                    "drogue_deployment": round(drogue_deployment, 4),
                    "main_deployment": round(main_deployment, 4),
                    "drag_force": round(drag_force, 4),
                    "active_drag_force": round(active_drag_force, 4),
                    "drag_force_x": round(-drag_x, 4),
                    "drag_force_y": round(-drag_y, 4),
                    "drag_force_z": round(-drag_z, 4),
                    "thrust_force": round(thrust, 4),
                    "thrust_force_x": round(thrust_x, 4),
                    "thrust_force_y": round(thrust_y, 4),
                    "thrust_force_z": round(thrust_z, 4),
                    "weight_force": round(weight_force, 4),
                    "net_force_x": round(net_force_x, 4),
                    "net_force_y": round(net_force_y, 4),
                    "net_force_z": round(net_force_z, 4),
                    "pitch_moment": round(pitch_moment_nm, 6),
                    "yaw_moment": round(yaw_moment_nm, 6),
                    "roll_moment": round(roll_moment_nm, 6),
                    "active_pitch_moment": round(active_pitch_moment_nm, 6),
                    "active_yaw_moment": round(active_yaw_moment_nm, 6),
                    "valve_command": round(valve_command, 4),
                    "surface_deployment": round(deployment_fraction, 4),
                    "surface_angle_deg": round(surface_angle_deg, 4),
                    "tank_pressure": round(tank_pressure, 2),
                    "actuator_pressure": round(actuator_pressure, 2),
                }
                trajectory.append(sample)
                sample_bearing = self._bearing_deg(x, y)
                active_history.append({
                    "time": sample["time"],
                    "tank_pressure": sample["tank_pressure"],
                    "actuator_pressure": sample["actuator_pressure"],
                    "stroke_m": round(stroke, 5),
                    "surface_deployment": sample["surface_deployment"],
                    "surface_angle_deg": sample["surface_angle_deg"],
                    "valve_command": sample["valve_command"],
                })
                landing_history.append({
                    "time": sample["time"],
                    "deployed": landing_deployed,
                    "deployment": sample["landing_deployment"],
                    "drogue_deployed": drogue_deployed,
                    "drogue_deployment": sample["drogue_deployment"],
                    "main_deployed": landing_deployed,
                    "main_deployment": sample["main_deployment"],
                    "phase": "main" if landing_deployed else "drogue" if drogue_deployed else "stowed",
                    "altitude": sample["altitude"],
                    "downrange_x": sample["downrange_x"],
                    "crossrange_y": sample["crossrange_y"],
                    "range_m": round(self._distance_xy(x, y), 4),
                    "bearing_deg": round(sample_bearing, 4) if sample_bearing is not None else None,
                    "velocity_z": sample["velocity_z"],
                })
                controller_history.append({
                    "time": sample["time"],
                    "mode": controller["mode"],
                    "predicted_apogee": round(sensor["predicted_apogee"], 4),
                    "command": sample["valve_command"],
                    "surface_target": round(surface_target, 4),
                })
                force_history.append({
                    "time": sample["time"],
                    "thrust_force": sample["thrust_force"],
                    "drag_force": sample["drag_force"],
                    "active_drag_force": sample["active_drag_force"],
                    "weight_force": sample["weight_force"],
                    "net_force_x": sample["net_force_x"],
                    "net_force_y": sample["net_force_y"],
                    "net_force_z": sample["net_force_z"],
                    "dynamic_pressure": sample["dynamic_pressure"],
                    "drag_coefficient": sample["drag_coefficient"],
                })
                moment_history.append({
                    "time": sample["time"],
                    "pitch_moment": sample["pitch_moment"],
                    "yaw_moment": sample["yaw_moment"],
                    "roll_moment": sample["roll_moment"],
                    "active_pitch_moment": sample["active_pitch_moment"],
                    "active_yaw_moment": sample["active_yaw_moment"],
                    "pitch_rate_deg_s": sample["angular_velocity_y_deg_s"],
                    "yaw_rate_deg_s": sample["angular_velocity_z_deg_s"],
                    "roll_rate_deg_s": sample["angular_velocity_x_deg_s"],
                })

            t += dt
            if t > burn_time_s and altitude <= 0.0 and velocity_z < 0.0:
                landing_velocity = abs(velocity_z)
                touchdown_time = t
                break

        if active["enabled"] and max_deployment < 0.01:
            warnings.append("Active system was enabled but never deployed; check controller threshold and pressure settings.")
        if active["enabled"] and min_tank_pressure < active["min_operating_pressure_pa"]:
            warnings.append("Tank pressure fell below minimum operating pressure during flight.")
        if max_dynamic_pressure > active["max_dynamic_pressure_pa"]:
            warnings.append("Dynamic pressure exceeded configured active-system structural limit.")
        if landing["enabled"] and not landing_deployed:
            warnings.append("Landing system did not deploy before touchdown; raise max time or deploy altitude.")
        if launch_guide["estimated_exit_velocity_mps"] < launch_guide["min_exit_velocity_mps"]:
            warnings.append("Estimated launch guide exit velocity is below configured minimum.")

        total_time = max(t, burn_time_s)
        if touchdown_time is None and altitude <= 0.0:
            touchdown_time = total_time
        downrange = math.sqrt(x**2 + y**2)
        touchdown_bearing = self._bearing_deg(x, y)
        main_drift = (
            self._distance_xy(x - landing_deploy_x, y - landing_deploy_y)
            if landing_deploy_x is not None and landing_deploy_y is not None
            else None
        )
        drogue_drift = (
            self._distance_xy(x - drogue_deploy_x, y - drogue_deploy_y)
            if drogue_deploy_x is not None and drogue_deploy_y is not None
            else None
        )
        descent_time = touchdown_time - apogee_time if touchdown_time is not None else None
        landing_footprint = {
            "launch_x_m": 0.0,
            "launch_y_m": 0.0,
            "apogee_x_m": apogee_x,
            "apogee_y_m": apogee_y,
            "apogee_range_m": self._distance_xy(apogee_x, apogee_y),
            "apogee_bearing_deg": self._bearing_deg(apogee_x, apogee_y),
            "drogue_deploy_x_m": drogue_deploy_x,
            "drogue_deploy_y_m": drogue_deploy_y,
            "drogue_deploy_range_m": self._distance_xy(drogue_deploy_x, drogue_deploy_y),
            "drogue_deploy_bearing_deg": self._bearing_deg(drogue_deploy_x, drogue_deploy_y),
            "main_deploy_x_m": landing_deploy_x,
            "main_deploy_y_m": landing_deploy_y,
            "main_deploy_range_m": self._distance_xy(landing_deploy_x, landing_deploy_y),
            "main_deploy_bearing_deg": self._bearing_deg(landing_deploy_x, landing_deploy_y),
            "touchdown_x_m": x,
            "touchdown_y_m": y,
            "touchdown_range_m": downrange,
            "touchdown_bearing_deg": touchdown_bearing,
            "drift_after_main_deploy_m": main_drift,
            "drift_after_drogue_deploy_m": drogue_drift,
            "descent_time_s": descent_time,
        }
        recovery_analysis = self._build_recovery_analysis(
            max_altitude=max_altitude,
            apogee_time=apogee_time,
            apogee_x=apogee_x,
            apogee_y=apogee_y,
            drogue_deploy_time=drogue_deploy_time,
            drogue_deploy_altitude=drogue_deploy_altitude,
            drogue_deploy_velocity_z=drogue_deploy_velocity_z,
            drogue_deploy_x=drogue_deploy_x,
            drogue_deploy_y=drogue_deploy_y,
            landing_deploy_time=landing_deploy_time,
            landing_deploy_altitude=landing_deploy_altitude,
            landing_deploy_velocity_z=landing_deploy_velocity_z,
            landing_deploy_x=landing_deploy_x,
            landing_deploy_y=landing_deploy_y,
            touchdown_time=touchdown_time,
            touchdown_velocity=landing_velocity,
            touchdown_x=x,
            touchdown_y=y,
            footprint=landing_footprint,
        )
        recovery_safety = self._build_recovery_safety(
            landing=landing,
            density=density,
            mass_kg=mass_kg,
            gravity=gravity,
            main_deploy_speed_air=landing_deploy_speed_air,
            drogue_deploy_speed_air=drogue_deploy_speed_air,
            touchdown_velocity=landing_velocity,
        )
        aero_center = self._aerodynamic_center_m(components, total_length_m, diameter_m)
        cp_m = aero_center["cp_m"]
        stability_margin = (cp_m - cg_m) / diameter_m
        recovery_timing = self._build_recovery_timing(
            burn_time_s=burn_time_s,
            motor_delay_s=motor_delay_s,
            apogee_time=apogee_time,
            touchdown_time=touchdown_time,
        )
        if motor_delay_s > 0 and abs(recovery_timing["timing_error_s"]) > 2.5:
            warnings.append("Motor ejection delay is far from apogee; use avionics or adjust delay.")
        if recovery_safety["main_area_margin_m2"] is not None and recovery_safety["main_area_margin_m2"] < 0:
            warnings.append("Landing drag area is below the configured safe touchdown target.")
        if recovery_safety["main_opening_load_status"] == "hard" or recovery_safety["drogue_opening_load_status"] == "hard":
            warnings.append("Recovery opening load exceeds configured limit.")
        flight_events = self._build_flight_events(
            burn_time_s=burn_time_s,
            max_altitude=max_altitude,
            apogee_time=apogee_time,
            recovery_timing=recovery_timing,
            max_deployment=max_deployment,
            max_deployment_time=max_deployment_time,
            landing=landing,
            landing_deployed=landing_deployed,
            landing_deploy_time=landing_deploy_time,
            landing_deploy_altitude=landing_deploy_altitude,
            drogue_deployed=drogue_deployed,
            drogue_deploy_time=drogue_deploy_time,
            drogue_deploy_altitude=drogue_deploy_altitude,
            touchdown_time=touchdown_time,
            landing_velocity=landing_velocity,
        )
        stage_splits = self._build_stage_splits(
            rocket_data.get("splitPoints") or rocket_data.get("stageSplits") or [],
            components,
        )

        return {
            "source": "active_pneumatic_local_dynamics",
            "model_version": self.model_version,
            "is_placeholder": False,
            "stage_splits": stage_splits,
            "max_altitude": max_altitude,
            "max_velocity": max_velocity,
            "total_flight_time": total_time,
            "apogee_time": apogee_time,
            "landing_velocity": landing_velocity,
            "downrange_distance": downrange,
            "landing_footprint": landing_footprint,
            "motor_thrust": thrust_n,
            "motor_burn_time": burn_time_s,
            "motor_delay": motor_delay_s,
            "total_impulse": total_impulse_ns,
            "recovery_timing": recovery_timing,
            "recovery_analysis": recovery_analysis,
            "recovery_safety": recovery_safety,
            "stability_margin": stability_margin,
            "center_of_pressure_m": cp_m,
            "cp_contributions": aero_center["contributions"],
            "drag_coefficient": aero["base_cd"],
            "max_drag_coefficient": max_drag_coefficient,
            "lift_coefficient": 0.0,
            "max_drag_force": max_drag_force,
            "max_active_drag_force": max_active_drag_force,
            "max_net_force": max_net_force,
            "max_dynamic_pressure": max_dynamic_pressure,
            "max_attitude_deg": max_attitude_deg,
            "max_angular_rate_deg_s": max_angular_rate_deg_s,
            "pressure_distribution": "local_dynamic_pressure_estimate",
            "velocity_field": "local_trajectory_air_relative_profile",
            "trajectory_data": "time_history_included",
            "trajectory": trajectory,
            "flight_events": flight_events,
            "launch_guide": {
                **launch_guide,
                "simulated_exit_velocity_mps": guide_exit_velocity,
                "clear_time_s": guide_clear_time,
                "clear_altitude_m": guide_clear_altitude,
                "status": "safe" if launch_guide["estimated_exit_velocity_mps"] >= launch_guide["min_exit_velocity_mps"] else "slow",
            },
            "force_history": force_history,
            "moment_history": moment_history,
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
                "location_from_nose_m": active["location_from_nose_m"],
                "moment_arm_m": active["moment_arm_m"],
                "max_active_drag_force": max_active_drag_force,
                "valve_cycles": valve_cycles,
                "history": active_history,
            },
            "landing_system": {
                "enabled": landing["enabled"],
                "type": landing["system_type"],
                "deployed": landing_deployed,
                "main_deployed": landing_deployed,
                "drogue_deployed": drogue_deployed,
                "deploy_altitude_m": landing["deploy_altitude_m"],
                "main_deploy_event": landing["main_deploy_event"],
                "deploy_time": landing_deploy_time,
                "deploy_actual_altitude_m": landing_deploy_altitude,
                "deploy_x_m": landing_deploy_x,
                "deploy_y_m": landing_deploy_y,
                "deploy_range_m": landing_footprint["main_deploy_range_m"],
                "deploy_bearing_deg": landing_footprint["main_deploy_bearing_deg"],
                "drogue_deploy_event": landing["drogue_deploy_event"],
                "drogue_deploy_altitude_target_m": landing["drogue_deploy_altitude_m"],
                "drogue_deploy_time": drogue_deploy_time,
                "drogue_deploy_altitude_m": drogue_deploy_altitude,
                "drogue_deploy_x_m": drogue_deploy_x,
                "drogue_deploy_y_m": drogue_deploy_y,
                "drogue_deploy_range_m": landing_footprint["drogue_deploy_range_m"],
                "drogue_deploy_bearing_deg": landing_footprint["drogue_deploy_bearing_deg"],
                "drag_area_m2": landing["drag_area_m2"],
                "drag_coefficient": landing["drag_coefficient"],
                "drogue_drag_area_m2": landing["drogue_drag_area_m2"],
                "drogue_drag_coefficient": landing["drogue_drag_coefficient"],
                "max_safe_velocity_mps": landing["max_safe_velocity_mps"],
                "max_opening_load_g": landing["max_opening_load_g"],
                "required_drag_area_m2": recovery_safety["required_main_drag_area_m2"],
                "area_margin_m2": recovery_safety["main_area_margin_m2"],
                "estimated_terminal_velocity_mps": recovery_safety["main_terminal_velocity_mps"],
                "drogue_terminal_velocity_mps": recovery_safety["drogue_terminal_velocity_mps"],
                "main_opening_load_n": recovery_safety["main_opening_load_n"],
                "main_opening_load_g": recovery_safety["main_opening_load_g"],
                "main_opening_load_status": recovery_safety["main_opening_load_status"],
                "drogue_opening_load_n": recovery_safety["drogue_opening_load_n"],
                "drogue_opening_load_g": recovery_safety["drogue_opening_load_g"],
                "drogue_opening_load_status": recovery_safety["drogue_opening_load_status"],
                "touchdown_velocity_mps": landing_velocity,
                "touchdown_time": touchdown_time,
                "touchdown_x_m": x,
                "touchdown_y_m": y,
                "touchdown_range_m": downrange,
                "touchdown_bearing_deg": touchdown_bearing,
                "drift_after_main_deploy_m": main_drift,
                "drift_after_drogue_deploy_m": drogue_drift,
                "descent_time_s": descent_time,
                "touchdown_status": "safe" if landing_velocity <= landing["max_safe_velocity_mps"] else "hard",
                "history": landing_history,
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
            "aerodynamics": {
                "base_drag_coefficient": aero["base_cd"],
                "active_drag_model": aero["active_drag_model"],
                "active_drag_table": aero["active_drag_table"],
                "max_drag_coefficient": max_drag_coefficient,
            },
            "thrust_profile": {
                "source": "curve" if thrust_curve else "average",
                "points": [{"time": t_point, "thrust": thrust_point} for t_point, thrust_point in thrust_curve],
                "integrated_impulse": curve_total_impulse_ns,
            },
            "warnings": warnings,
            "notes": "Local dynamic model with pneumatic actuator coupling; optional CFD/table calibration remains future work.",
        }

    def _parse_thrust_curve(self, motor: Dict) -> List[tuple]:
        raw_curve = (
            motor.get("thrustCurve")
            or motor.get("thrust_curve")
            or motor.get("thrustCurvePoints")
            or []
        )
        points = []
        if not isinstance(raw_curve, list):
            return points

        for point in raw_curve:
            if isinstance(point, dict):
                time_s = self._as_float(
                    self._first_value(point, ["time", "time_s", "t"], None),
                    math.nan,
                )
                thrust_n = self._as_float(
                    self._first_value(point, ["thrust", "thrust_n", "force", "force_n"], None),
                    math.nan,
                )
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                time_s = self._as_float(point[0], math.nan)
                thrust_n = self._as_float(point[1], math.nan)
            else:
                continue
            if math.isfinite(time_s) and math.isfinite(thrust_n) and time_s >= 0 and thrust_n >= 0:
                points.append((time_s, thrust_n))

        points = sorted(points, key=lambda item: item[0])
        deduped = []
        for time_s, thrust_n in points:
            if deduped and abs(deduped[-1][0] - time_s) < 1e-9:
                deduped[-1] = (time_s, thrust_n)
            else:
                deduped.append((time_s, thrust_n))
        return deduped if len(deduped) >= 2 and deduped[-1][0] > deduped[0][0] else []

    @staticmethod
    def _integrate_curve(points: List[tuple]) -> float:
        impulse = 0.0
        for (t0, f0), (t1, f1) in zip(points, points[1:]):
            impulse += max(t1 - t0, 0.0) * (f0 + f1) * 0.5
        return impulse

    def _thrust_at_time(
        self,
        time_s: float,
        thrust_curve: List[tuple],
        average_thrust: float,
        burn_time_s: float,
    ) -> float:
        if not thrust_curve:
            return average_thrust if time_s <= burn_time_s else 0.0
        if time_s < thrust_curve[0][0] or time_s > thrust_curve[-1][0]:
            return 0.0
        for (t0, f0), (t1, f1) in zip(thrust_curve, thrust_curve[1:]):
            if t0 <= time_s <= t1:
                if abs(t1 - t0) < 1e-9:
                    return f1
                fraction = (time_s - t0) / (t1 - t0)
                return f0 + (f1 - f0) * fraction
        return 0.0

    def _build_aero_config(self, config: Dict, base_cd: float) -> Dict:
        aero = config.get("aerodynamics") or config.get("aero") or {}
        table = self._parse_active_drag_table(
            aero.get("activeDragCoefficientTable")
            or aero.get("dragCoefficientTable")
            or []
        )
        return {
            "base_cd": self._as_float(aero.get("baseDragCoefficient"), base_cd),
            "active_drag_table": table,
            "active_drag_model": "table" if table else "surface_area",
        }

    def _build_launch_guide_config(self, config: Dict, mass_kg: float, thrust_n: float, burn_time_s: float) -> Dict:
        length_m = self._as_float(
            self._first_value(config, ["launchGuideLength", "launchRodLength", "railLength"], 1.5),
            1.5,
        )
        angle_deg = self._clamp(
            self._as_float(self._first_value(config, ["launchGuideAngle", "launchAngle", "railAngle"], 0.0), 0.0),
            0.0,
            30.0,
        )
        direction_deg = self._as_float(
            self._first_value(config, ["launchGuideDirection", "launchDirection", "railDirection"], 0.0),
            0.0,
        ) % 360
        min_exit_velocity = self._as_float(
            self._first_value(config, ["minRailExitVelocity", "minGuideExitVelocity"], 12.0),
            12.0,
        )
        gravity_component = 9.80665 * math.cos(math.radians(angle_deg))
        average_accel = max((thrust_n / max(mass_kg, 0.001)) - gravity_component, 0.0)
        estimated_exit_velocity = math.sqrt(2.0 * average_accel * max(length_m, 0.0)) if average_accel > 0 else 0.0
        estimated_clear_time = estimated_exit_velocity / average_accel if average_accel > 0 else None
        return {
            "length_m": length_m,
            "angle_deg": angle_deg,
            "direction_deg": direction_deg,
            "min_exit_velocity_mps": min_exit_velocity,
            "estimated_exit_velocity_mps": estimated_exit_velocity,
            "estimated_clear_time_s": estimated_clear_time,
            "average_acceleration_mps2": average_accel,
            "burn_fraction_at_clear": (estimated_clear_time / burn_time_s) if estimated_clear_time and burn_time_s > 0 else None,
        }

    def _parse_active_drag_table(self, raw_table) -> List[Dict[str, float]]:
        if not isinstance(raw_table, list):
            return []
        points = []
        for point in raw_table:
            if isinstance(point, dict):
                deployment = self._as_float(
                    self._first_value(point, ["deployment", "surfaceDeployment", "surface_deployment"], None),
                    math.nan,
                )
                cd_increment = self._as_float(
                    self._first_value(point, ["cdIncrement", "dragCoefficientIncrement", "activeCd", "cd"], None),
                    math.nan,
                )
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                deployment = self._as_float(point[0], math.nan)
                cd_increment = self._as_float(point[1], math.nan)
            else:
                continue
            if math.isfinite(deployment) and math.isfinite(cd_increment) and cd_increment >= 0:
                points.append({
                    "deployment": self._clamp(deployment, 0.0, 1.0),
                    "cd_increment": cd_increment,
                })

        points = sorted(points, key=lambda item: item["deployment"])
        deduped = []
        for point in points:
            if deduped and abs(deduped[-1]["deployment"] - point["deployment"]) < 1e-9:
                deduped[-1] = point
            else:
                deduped.append(point)
        return deduped if len(deduped) >= 2 else []

    def _effective_drag_coefficient(
        self,
        deployment_fraction: float,
        active: Dict,
        aero: Dict,
        frontal_area_m2: float,
    ) -> float:
        if aero["active_drag_table"]:
            return aero["base_cd"] + self._interpolate_drag_increment(deployment_fraction, aero["active_drag_table"])
        airbrake_area = active["surface_area_m2"] * active["surface_count"] * deployment_fraction
        airbrake_cd = active["surface_cd"] * airbrake_area / max(frontal_area_m2, 1e-6)
        return aero["base_cd"] + airbrake_cd

    @staticmethod
    def _landing_drag_coefficient(
        landing: Dict,
        drogue_deployment: float,
        main_deployment: float,
        frontal_area_m2: float,
    ) -> float:
        if not landing["enabled"] or (drogue_deployment <= 0 and main_deployment <= 0):
            return 0.0
        drogue_area = 0.0
        if landing["system_type"] == "drogue_main":
            drogue_area = landing["drogue_drag_coefficient"] * landing["drogue_drag_area_m2"] * drogue_deployment
        main_area = landing["drag_coefficient"] * landing["drag_area_m2"] * main_deployment
        return (drogue_area + main_area) / max(frontal_area_m2, 1e-6)

    @staticmethod
    def _should_deploy_recovery(
        deploy_event: str,
        *,
        t: float,
        altitude: float,
        velocity_z: float,
        deploy_altitude_m: float,
        apogee_detected: bool,
        motor_ejection_time_s: Optional[float],
    ) -> bool:
        if deploy_event == "apogee":
            return apogee_detected
        if deploy_event == "altitude":
            return apogee_detected and velocity_z < -0.5 and altitude <= deploy_altitude_m
        if deploy_event == "motor_ejection":
            return motor_ejection_time_s is not None and t >= motor_ejection_time_s
        return False

    def _build_flight_events(
        self,
        *,
        burn_time_s: float,
        max_altitude: float,
        apogee_time: float,
        recovery_timing: Dict,
        max_deployment: float,
        max_deployment_time: float,
        landing: Dict,
        landing_deployed: bool,
        landing_deploy_time: Optional[float],
        landing_deploy_altitude: Optional[float],
        drogue_deployed: bool,
        drogue_deploy_time: Optional[float],
        drogue_deploy_altitude: Optional[float],
        touchdown_time: Optional[float],
        landing_velocity: float,
    ) -> List[Dict[str, float]]:
        events = [
            {
                "name": "Launch",
                "time": 0.0,
                "type": "liftoff",
                "value": 0.0,
                "unit": "m",
            },
            {
                "name": "Motor burnout",
                "time": round(burn_time_s, 3),
                "type": "propulsion",
                "value": round(burn_time_s, 3),
                "unit": "s",
            },
            {
                "name": "Apogee",
                "time": round(apogee_time, 3),
                "type": "trajectory",
                "value": round(max_altitude, 3),
                "unit": "m",
            },
        ]
        if recovery_timing.get("motor_delay_s", 0.0) > 0:
            events.append({
                "name": "Motor ejection",
                "time": round(recovery_timing["ejection_time_s"], 3),
                "type": "recovery",
                "value": round(recovery_timing["timing_error_s"], 3),
                "unit": "s from apogee",
            })
        if max_deployment > 0.001:
            events.append({
                "name": "Max airbrake",
                "time": round(max_deployment_time, 3),
                "type": "active_control",
                "value": round(max_deployment * 100.0, 2),
                "unit": "%",
            })
        if landing["enabled"] and drogue_deployed:
            events.append({
                "name": "Drogue deploy",
                "time": round(drogue_deploy_time or 0.0, 3),
                "type": "landing",
                "value": round(drogue_deploy_altitude or 0.0, 3),
                "unit": "m",
            })
        if landing["enabled"] and landing_deployed:
            event_name = "Main deploy" if landing["system_type"] == "drogue_main" else "Landing deploy"
            events.append({
                "name": event_name,
                "time": round(landing_deploy_time or 0.0, 3),
                "type": "landing",
                "value": round(landing_deploy_altitude or 0.0, 3),
                "unit": "m",
            })
        if touchdown_time is not None:
            events.append({
                "name": "Touchdown",
                "time": round(touchdown_time, 3),
                "type": "landing",
                "value": round(landing_velocity, 3),
                "unit": "m/s",
            })
        return sorted(events, key=lambda item: item["time"])

    @staticmethod
    def _build_recovery_timing(
        *,
        burn_time_s: float,
        motor_delay_s: float,
        apogee_time: float,
        touchdown_time: Optional[float],
    ) -> Dict[str, float]:
        ejection_time_s = burn_time_s + max(motor_delay_s, 0.0)
        timing_error_s = ejection_time_s - apogee_time
        abs_error = abs(timing_error_s)
        if abs_error <= 1.0:
            status = "optimal"
        elif timing_error_s < 0:
            status = "early"
        else:
            status = "late"
        return {
            "motor_delay_s": motor_delay_s,
            "optimal_delay_s": max(apogee_time - burn_time_s, 0.0),
            "ejection_time_s": ejection_time_s,
            "apogee_time_s": apogee_time,
            "timing_error_s": timing_error_s,
            "status": status,
            "before_touchdown": touchdown_time is None or ejection_time_s <= touchdown_time,
        }

    def _recovery_event_summary(
        self,
        name: str,
        *,
        time_s: Optional[float],
        altitude_m: Optional[float],
        velocity_z_mps: Optional[float],
        x_m: Optional[float],
        y_m: Optional[float],
    ) -> Optional[Dict[str, float]]:
        if time_s is None:
            return None
        return {
            "name": name,
            "time_s": time_s,
            "altitude_m": altitude_m,
            "velocity_z_mps": velocity_z_mps,
            "range_m": self._distance_xy(x_m, y_m),
            "bearing_deg": self._bearing_deg(x_m, y_m),
        }

    def _recovery_phase_summary(
        self,
        name: str,
        *,
        start_time_s: Optional[float],
        start_altitude_m: Optional[float],
        start_x_m: Optional[float],
        start_y_m: Optional[float],
        end_time_s: Optional[float],
        end_altitude_m: Optional[float],
        end_x_m: Optional[float],
        end_y_m: Optional[float],
    ) -> Optional[Dict[str, float]]:
        if start_time_s is None or end_time_s is None or end_time_s <= start_time_s:
            return None
        if start_altitude_m is None or end_altitude_m is None:
            return None
        duration_s = end_time_s - start_time_s
        altitude_loss_m = max(start_altitude_m - end_altitude_m, 0.0)
        drift_m = (
            self._distance_xy(end_x_m - start_x_m, end_y_m - start_y_m)
            if None not in (start_x_m, start_y_m, end_x_m, end_y_m)
            else None
        )
        return {
            "name": name,
            "start_time_s": start_time_s,
            "end_time_s": end_time_s,
            "duration_s": duration_s,
            "start_altitude_m": start_altitude_m,
            "end_altitude_m": end_altitude_m,
            "altitude_loss_m": altitude_loss_m,
            "average_descent_rate_mps": altitude_loss_m / duration_s if duration_s > 0 else None,
            "start_range_m": self._distance_xy(start_x_m, start_y_m),
            "end_range_m": self._distance_xy(end_x_m, end_y_m),
            "drift_m": drift_m,
        }

    @staticmethod
    def _terminal_velocity_mps(
        *,
        mass_kg: float,
        gravity: float,
        density: float,
        drag_area_m2: float,
        drag_coefficient: float,
    ) -> Optional[float]:
        drag_term = density * drag_coefficient * drag_area_m2
        if drag_term <= 0:
            return None
        return math.sqrt((2.0 * mass_kg * gravity) / drag_term)

    @staticmethod
    def _opening_load(
        *,
        density: float,
        deploy_speed_mps: Optional[float],
        drag_area_m2: float,
        drag_coefficient: float,
        mass_kg: float,
        gravity: float,
    ) -> Dict[str, Optional[float]]:
        if deploy_speed_mps is None:
            return {"load_n": None, "load_g": None}
        load_n = 0.5 * density * deploy_speed_mps * deploy_speed_mps * drag_coefficient * drag_area_m2
        return {
            "load_n": load_n,
            "load_g": load_n / max(mass_kg * gravity, 1e-9),
        }

    @staticmethod
    def _load_status(load_g: Optional[float], limit_g: float) -> str:
        if load_g is None:
            return "not_deployed"
        if load_g <= limit_g:
            return "safe"
        if load_g <= limit_g * 1.25:
            return "warn"
        return "hard"

    def _build_recovery_safety(
        self,
        *,
        landing: Dict,
        density: float,
        mass_kg: float,
        gravity: float,
        main_deploy_speed_air: Optional[float],
        drogue_deploy_speed_air: Optional[float],
        touchdown_velocity: float,
    ) -> Dict[str, Optional[float]]:
        if not landing["enabled"]:
            return {
                "enabled": False,
                "required_main_drag_area_m2": None,
                "main_area_margin_m2": None,
                "main_terminal_velocity_mps": None,
                "drogue_terminal_velocity_mps": None,
                "main_opening_load_n": None,
                "main_opening_load_g": None,
                "main_opening_load_status": "disabled",
                "drogue_opening_load_n": None,
                "drogue_opening_load_g": None,
                "drogue_opening_load_status": "disabled",
                "touchdown_status": "disabled",
                "overall_status": "disabled",
            }

        safe_velocity = landing["max_safe_velocity_mps"]
        main_terminal = self._terminal_velocity_mps(
            mass_kg=mass_kg,
            gravity=gravity,
            density=density,
            drag_area_m2=landing["drag_area_m2"],
            drag_coefficient=landing["drag_coefficient"],
        )
        required_main_area = (
            (2.0 * mass_kg * gravity)
            / max(density * landing["drag_coefficient"] * safe_velocity * safe_velocity, 1e-9)
        )
        main_opening = self._opening_load(
            density=density,
            deploy_speed_mps=main_deploy_speed_air,
            drag_area_m2=landing["drag_area_m2"],
            drag_coefficient=landing["drag_coefficient"],
            mass_kg=mass_kg,
            gravity=gravity,
        )
        drogue_terminal = self._terminal_velocity_mps(
            mass_kg=mass_kg,
            gravity=gravity,
            density=density,
            drag_area_m2=landing["drogue_drag_area_m2"],
            drag_coefficient=landing["drogue_drag_coefficient"],
        ) if landing["system_type"] == "drogue_main" else None
        drogue_opening = self._opening_load(
            density=density,
            deploy_speed_mps=drogue_deploy_speed_air,
            drag_area_m2=landing["drogue_drag_area_m2"],
            drag_coefficient=landing["drogue_drag_coefficient"],
            mass_kg=mass_kg,
            gravity=gravity,
        ) if landing["system_type"] == "drogue_main" else {"load_n": None, "load_g": None}

        main_load_status = self._load_status(main_opening["load_g"], landing["max_opening_load_g"])
        drogue_load_status = self._load_status(drogue_opening["load_g"], landing["max_opening_load_g"])
        touchdown_status = "safe" if touchdown_velocity <= safe_velocity else "hard"
        statuses = {main_load_status, drogue_load_status, touchdown_status}
        if "hard" in statuses:
            overall_status = "hard"
        elif "warn" in statuses:
            overall_status = "warn"
        else:
            overall_status = "safe"

        return {
            "enabled": True,
            "air_density_kg_m3": density,
            "required_main_drag_area_m2": required_main_area,
            "main_area_margin_m2": landing["drag_area_m2"] - required_main_area,
            "main_terminal_velocity_mps": main_terminal,
            "drogue_terminal_velocity_mps": drogue_terminal,
            "max_safe_velocity_mps": safe_velocity,
            "max_opening_load_g": landing["max_opening_load_g"],
            "main_deploy_speed_mps": main_deploy_speed_air,
            "main_opening_load_n": main_opening["load_n"],
            "main_opening_load_g": main_opening["load_g"],
            "main_opening_load_status": main_load_status,
            "drogue_deploy_speed_mps": drogue_deploy_speed_air,
            "drogue_opening_load_n": drogue_opening["load_n"],
            "drogue_opening_load_g": drogue_opening["load_g"],
            "drogue_opening_load_status": drogue_load_status,
            "touchdown_velocity_mps": touchdown_velocity,
            "touchdown_status": touchdown_status,
            "overall_status": overall_status,
        }

    def _build_recovery_analysis(
        self,
        *,
        max_altitude: float,
        apogee_time: float,
        apogee_x: float,
        apogee_y: float,
        drogue_deploy_time: Optional[float],
        drogue_deploy_altitude: Optional[float],
        drogue_deploy_velocity_z: Optional[float],
        drogue_deploy_x: Optional[float],
        drogue_deploy_y: Optional[float],
        landing_deploy_time: Optional[float],
        landing_deploy_altitude: Optional[float],
        landing_deploy_velocity_z: Optional[float],
        landing_deploy_x: Optional[float],
        landing_deploy_y: Optional[float],
        touchdown_time: Optional[float],
        touchdown_velocity: float,
        touchdown_x: float,
        touchdown_y: float,
        footprint: Dict[str, float],
    ) -> Dict[str, List[Dict[str, float]]]:
        sequence = [
            self._recovery_event_summary(
                "Apogee",
                time_s=apogee_time,
                altitude_m=max_altitude,
                velocity_z_mps=0.0,
                x_m=apogee_x,
                y_m=apogee_y,
            ),
            self._recovery_event_summary(
                "Drogue deploy",
                time_s=drogue_deploy_time,
                altitude_m=drogue_deploy_altitude,
                velocity_z_mps=drogue_deploy_velocity_z,
                x_m=drogue_deploy_x,
                y_m=drogue_deploy_y,
            ),
            self._recovery_event_summary(
                "Main deploy",
                time_s=landing_deploy_time,
                altitude_m=landing_deploy_altitude,
                velocity_z_mps=landing_deploy_velocity_z,
                x_m=landing_deploy_x,
                y_m=landing_deploy_y,
            ),
            self._recovery_event_summary(
                "Touchdown",
                time_s=touchdown_time,
                altitude_m=0.0,
                velocity_z_mps=-abs(touchdown_velocity),
                x_m=touchdown_x,
                y_m=touchdown_y,
            ),
        ]
        sequence = [event for event in sequence if event is not None]

        phases = [
            self._recovery_phase_summary(
                "Total descent",
                start_time_s=apogee_time,
                start_altitude_m=max_altitude,
                start_x_m=apogee_x,
                start_y_m=apogee_y,
                end_time_s=touchdown_time,
                end_altitude_m=0.0,
                end_x_m=touchdown_x,
                end_y_m=touchdown_y,
            )
        ]
        if drogue_deploy_time is not None:
            drogue_end_time = landing_deploy_time if landing_deploy_time is not None else touchdown_time
            drogue_end_altitude = landing_deploy_altitude if landing_deploy_time is not None else 0.0
            drogue_end_x = landing_deploy_x if landing_deploy_time is not None else touchdown_x
            drogue_end_y = landing_deploy_y if landing_deploy_time is not None else touchdown_y
            phases.append(self._recovery_phase_summary(
                "Drogue descent",
                start_time_s=drogue_deploy_time,
                start_altitude_m=drogue_deploy_altitude,
                start_x_m=drogue_deploy_x,
                start_y_m=drogue_deploy_y,
                end_time_s=drogue_end_time,
                end_altitude_m=drogue_end_altitude,
                end_x_m=drogue_end_x,
                end_y_m=drogue_end_y,
            ))
        phases.append(self._recovery_phase_summary(
            "Main descent",
            start_time_s=landing_deploy_time,
            start_altitude_m=landing_deploy_altitude,
            start_x_m=landing_deploy_x,
            start_y_m=landing_deploy_y,
            end_time_s=touchdown_time,
            end_altitude_m=0.0,
            end_x_m=touchdown_x,
            end_y_m=touchdown_y,
        ))
        phases = [phase for phase in phases if phase is not None]

        return {
            "deployment_sequence": sequence,
            "phases": phases,
            "total_descent_time_s": footprint["descent_time_s"],
            "touchdown_range_m": footprint["touchdown_range_m"],
            "touchdown_bearing_deg": footprint["touchdown_bearing_deg"],
            "main_drift_m": footprint["drift_after_main_deploy_m"],
            "drogue_drift_m": footprint["drift_after_drogue_deploy_m"],
        }

    @staticmethod
    def _interpolate_drag_increment(deployment_fraction: float, table: List[Dict[str, float]]) -> float:
        if deployment_fraction <= table[0]["deployment"]:
            return table[0]["cd_increment"]
        if deployment_fraction >= table[-1]["deployment"]:
            return table[-1]["cd_increment"]
        for left, right in zip(table, table[1:]):
            if left["deployment"] <= deployment_fraction <= right["deployment"]:
                span = right["deployment"] - left["deployment"]
                if span <= 1e-9:
                    return right["cd_increment"]
                fraction = (deployment_fraction - left["deployment"]) / span
                return left["cd_increment"] + (right["cd_increment"] - left["cd_increment"]) * fraction
        return table[-1]["cd_increment"]

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
            "location_from_nose_m": self._distance_m(active.get("locationFromNose"), 0.42),
            "max_dynamic_pressure_pa": self._as_float(active.get("maxDynamicPressure"), 85000.0),
        }

    def _build_landing_config(self, config: Dict) -> Dict:
        landing = config.get("landingSystem") or config.get("recoverySystem") or {}
        deploy_altitude = self._as_float(landing.get("deployAltitude"), 120.0)
        system_type = landing.get("type") or landing.get("systemType") or "main_parachute"
        return {
            "enabled": self._as_bool(landing.get("enabled"), True),
            "system_type": system_type,
            "main_deploy_event": self._normalize_deploy_event(
                self._first_value(landing, ["mainDeployEvent", "deployEvent", "deploymentEvent"], "altitude"),
                "altitude",
            ),
            "drogue_deploy_event": self._normalize_deploy_event(
                self._first_value(landing, ["drogueDeployEvent", "drogueDeploymentEvent"], "apogee"),
                "apogee",
            ),
            "deploy_altitude_m": deploy_altitude,
            "drogue_deploy_altitude_m": self._as_float(landing.get("drogueDeployAltitude"), deploy_altitude),
            "drag_area_m2": self._as_float(landing.get("dragArea"), 0.18),
            "drag_coefficient": self._as_float(landing.get("dragCoefficient"), 1.55),
            "drogue_drag_area_m2": self._as_float(landing.get("drogueDragArea"), 0.04),
            "drogue_drag_coefficient": self._as_float(landing.get("drogueDragCoefficient"), 1.25),
            "max_safe_velocity_mps": self._as_float(landing.get("maxSafeVelocity"), 7.5),
            "max_opening_load_g": self._as_float(landing.get("maxOpeningLoadG"), 15.0),
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

    def _build_stage_splits(self, split_points: List[Dict], components: List[Dict]) -> List[Dict]:
        if not isinstance(split_points, list):
            return []

        structural = []
        cursor_m = 0.0
        for component in components:
            if str(component.get("type", "")).lower() in {"fins", "motor", "rail button"}:
                continue
            length = self._distance_m(self._first_value(component, ["length", "totalHeight"], 0.0), 0.0)
            structural.append({
                "id": str(component.get("id", "")),
                "name": component.get("name") or component.get("type") or "Component",
                "start_m": cursor_m,
                "end_m": cursor_m + max(length, 0.0),
            })
            cursor_m += max(length, 0.0)

        boundaries = {}
        for index, component in enumerate(structural[:-1]):
            next_component = structural[index + 1]
            boundaries[component["id"]] = {
                "after_component_id": component["id"],
                "after_component_name": component["name"],
                "before_component_id": next_component["id"],
                "before_component_name": next_component["name"],
                "position_m": component["end_m"],
                "position_mm": component["end_m"] * 1000.0,
            }

        stage_splits = []
        seen = set()
        for index, split in enumerate(split_points):
            if not isinstance(split, dict):
                continue
            after_component_id = str(
                split.get("afterComponentId")
                or split.get("after_component_id")
                or split.get("componentId")
                or ""
            )
            boundary = boundaries.get(after_component_id)
            if not boundary or after_component_id in seen:
                continue
            seen.add(after_component_id)
            stage_splits.append({
                "id": str(split.get("id") or f"split-{index + 1}"),
                "label": split.get("label") or split.get("name") or f"Split {len(stage_splits) + 1}",
                **boundary,
            })

        return stage_splits

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

    def _aerodynamic_center_m(self, components: List[Dict], total_length_m: float, diameter_m: float) -> Dict:
        def length_m(component: Dict) -> float:
            raw = self._as_float(self._first_value(component, ["length", "totalHeight"], 0.0), 0.0)
            return raw / 1000.0 if raw > 5 else raw

        def diameter_value_m(component: Dict, key: str = "diameter") -> float:
            raw = self._as_float(
                self._first_value(component, [key, "diameter", "bottomDiameter", "topDiameter"], 0.0),
                0.0,
            )
            return raw / 1000.0 if raw > 1 else raw

        def axial_position_m(component: Dict, default_m: float) -> float:
            raw = self._first_value(
                component,
                ["axialPosition", "positionFromNose", "position", "axial_position", "position_from_nose"],
                None,
            )
            if raw in (None, ""):
                return self._clamp(default_m, 0.0, total_length_m)
            position = self._as_float(raw, default_m)
            position_m = position / 1000.0 if abs(position) > 5 else position
            return self._clamp(position_m, 0.0, total_length_m)

        structural = []
        cursor = 0.0
        for component in components:
            component_type = str(component.get("type", "")).lower()
            if component_type in {"fins", "motor", "rail button"}:
                continue
            component_length = max(length_m(component), 0.0)
            structural.append((component, cursor, component_length))
            cursor += component_length

        reference_diameter = max(diameter_m, 0.001)
        contributions = []
        for component, start_m, component_length in structural:
            component_type = str(component.get("type", "")).lower()
            if component_type == "nose cone":
                shape = str(component.get("shape", "ogive")).lower()
                cp_fraction = {
                    "conical": 0.667,
                    "elliptical": 0.5,
                    "von-karman": 0.5,
                    "ogive": 0.466,
                }.get(shape, 0.466)
                ratio = diameter_value_m(component) / reference_diameter
                normal_force = 2.0 * ratio * ratio
                contributions.append({
                    "name": component.get("name", "Nose cone"),
                    "type": component.get("type", "Nose Cone"),
                    "normal_force": normal_force,
                    "cp_m": start_m + component_length * cp_fraction,
                })
            elif component_type == "transition" and component_length > 0:
                front = diameter_value_m(component, "topDiameter")
                rear = diameter_value_m(component, "bottomDiameter")
                normal_force = 2.0 * ((rear / reference_diameter) ** 2 - (front / reference_diameter) ** 2)
                if abs(normal_force) > 0.01:
                    contributions.append({
                        "name": component.get("name", "Transition"),
                        "type": component.get("type", "Transition"),
                        "normal_force": normal_force,
                        "cp_m": start_m + component_length * 0.55,
                    })

        for component in components:
            if str(component.get("type", "")).lower() != "fins":
                continue
            fin_count = max(self._as_float(self._first_value(component, ["finCount", "fin_count"], 3), 3), 1)
            span = max(self._as_float(self._first_value(component, ["finHeight", "span"], 0.0), 0.0), 1.0)
            root = max(self._as_float(self._first_value(component, ["finWidth", "rootChord"], 0.0), 0.0), 1.0)
            sweep = max(self._as_float(self._first_value(component, ["finSweep", "sweep"], 0.0), 0.0), 0.0)
            if span > 1:
                span /= 1000.0
            if root > 1:
                root /= 1000.0
            if sweep > 1:
                sweep /= 1000.0
            tip = max(root * 0.45, root - sweep, root * 0.2)
            mid_chord = math.sqrt(span**2 + (sweep + (root - tip) / 2.0) ** 2)
            denominator = 1.0 + math.sqrt(1.0 + ((2.0 * mid_chord) / max(root + tip, 1e-6)) ** 2)
            normal_force = 1.8 * fin_count * ((span / reference_diameter) ** 2) / denominator
            leading_edge = axial_position_m(component, max(0.0, total_length_m - root))
            cp_m = (
                leading_edge
                + (sweep * (root + 2.0 * tip)) / (3.0 * max(root + tip, 1e-6))
                + (root + tip - (root * tip) / max(root + tip, 1e-6)) / 6.0
            )
            contributions.append({
                "name": component.get("name", "Fins"),
                "type": component.get("type", "Fins"),
                "normal_force": normal_force,
                "position_m": leading_edge,
                "cp_m": self._clamp(cp_m, 0.0, total_length_m),
            })

        total_normal_force = sum(item["normal_force"] for item in contributions)
        if abs(total_normal_force) > 1e-6:
            cp_m = sum(item["normal_force"] * item["cp_m"] for item in contributions) / total_normal_force
        else:
            cp_m = total_length_m * 0.65
        cp_m = self._clamp(cp_m, 0.0, total_length_m)
        return {
            "cp_m": cp_m,
            "total_normal_force": total_normal_force,
            "contributions": [
                {
                    **item,
                    "share": (item["normal_force"] / total_normal_force * 100.0) if total_normal_force else 0.0,
                }
                for item in contributions
            ],
        }

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
