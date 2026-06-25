#!/usr/bin/env python3
"""Pre-goal backend smoke checks for local R_SIM readiness."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SIMULATION_MODE", "local")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def json_body(response):
    body = response.get_json(silent=True)
    require(body is not None, f"Expected JSON response, got {response.status_code}")
    return body


def main() -> int:
    import f_backend

    client = f_backend.app.test_client()

    health = json_body(client.get("/api/health"))
    require(health.get("status") == "healthy", "Health endpoint is not healthy.")

    motors = json_body(client.get("/api/environment/motors"))
    require(len(motors.get("motors", [])) >= 1, "Motor database returned no motors.")

    sites = json_body(client.get("/api/environment/launch-sites"))
    require(len(sites.get("launch_sites", {})) >= 1, "Launch-site endpoint returned no sites.")

    controller_code = r"""
ControlOutput control_function(SensorData sensor_data) {
    ControlOutput out{};
    double command = 0.0;
    double error = sensor_data.predicted_apogee - 80.0;
    if (sensor_data.altitude > 8.0 && sensor_data.velocity_z > 0.0 && error > 0.0) {
        command = error * 0.02 + sensor_data.velocity_z * 0.01;
    }
    if (sensor_data.velocity_z < -2.0 && sensor_data.altitude < 70.0) {
        command = 1.0;
    }
    if (command < 0.0) command = 0.0;
    if (command > 1.0) command = 1.0;
    out.fin_deflection_1 = 0.0;
    out.fin_deflection_2 = 0.0;
    out.fin_deflection_3 = 0.0;
    out.fin_deflection_4 = 0.0;
    out.valve_command = command;
    out.surface_target = command;
    out.recovery_trigger = false;
    out.data_logging["altitude"] = sensor_data.altitude;
    return out;
}
"""
    compile_result = json_body(client.post("/api/control-code/compile", json={"code": controller_code}))
    require(compile_result.get("success") is True, f"Controller did not compile: {compile_result}")

    payload = {
        "rocketComponents": [
            {"id": 1, "type": "Nose Cone", "name": "Prep Nose", "length": 120, "diameter": 40, "weight": 35},
            {"id": 2, "type": "Body Tube", "name": "Prep Body", "length": 560, "diameter": 40, "weight": 135},
            {"id": 3, "type": "Fins", "name": "Prep Fins", "finCount": 3, "finHeight": 55, "finWidth": 90, "weight": 45},
            {
                "id": 4,
                "type": "Motor",
                "name": "Estes C6-5",
                "length": 70,
                "diameter": 18,
                "motorThrust": 6.0,
                "motorBurnTime": 1.6,
                "motorTotalImpulse": 10.0,
                "motorWeight": 17,
                "weight": 17,
            },
        ],
        "rocketWeight": 232,
        "rocketCG": 320,
        "totalHeight": 680,
        "simulationConfig": {
            "timeStep": 0.02,
            "maxTime": 20,
            "windSpeed": 1.5,
            "temperature": 15,
            "pressure": 101325,
            "controllerLanguage": "cpp",
            "controlCode": controller_code,
            "activeSystem": {
                "enabled": True,
                "tankPressure": 650000,
                "tankVolume": 0.18,
                "regulatorPressure": 450000,
                "minOperatingPressure": 180000,
                "valveFlowRate": 14,
                "ventRate": 2.5,
                "lineVolume": 0.035,
                "cylinderBore": 0.012,
                "cylinderStroke": 0.035,
                "cylinderFriction": 5,
                "returnSpring": 18,
                "linkageRatio": 1,
                "surfaceMaxAngle": 65,
                "surfaceArea": 0.0024,
                "surfaceCount": 3,
                "surfaceCd": 1.35,
                "locationFromNose": 0.42,
                "maxDynamicPressure": 85000,
            },
            "controller": {
                "mode": "target_apogee",
                "targetApogee": 80,
                "deployAltitude": 8,
                "descentDeployAltitude": 70,
                "kp": 0.02,
                "kd": 0.01,
                "minimumCommand": 0.03,
            },
            "noise": {
                "seed": 20260625,
                "altitudeStd": 0.15,
                "velocityStd": 0.05,
                "accelStd": 0.12,
                "ambientPressureStd": 8,
                "pneumaticPressureStd": 120,
                "temperatureStd": 0.05,
                "initialAttitudeStd": 0.35,
            },
        },
    }
    start = json_body(client.post("/api/simulation/start", json=payload))
    require(start.get("success") is True, f"Simulation did not start: {start}")
    simulation_id = start.get("simulation_id")
    require(bool(simulation_id), f"Simulation start did not return simulation_id: {start}")

    status = None
    for _ in range(8):
        status = json_body(client.post("/api/simulation/status", json={"simulation_id": simulation_id}))
        if status.get("status") == "completed":
            break
        time.sleep(0.25)

    require(status is not None, "Simulation status did not return.")
    require(status.get("status") == "completed", f"Simulation did not complete: {status}")
    results = status.get("results") or {}
    require(results.get("is_placeholder") is False, f"Simulation result is marked placeholder: {results}")
    require(results.get("source") == "active_pneumatic_local_dynamics", f"Unexpected result source: {results}")
    for key in ("max_altitude", "max_velocity", "total_flight_time", "drag_coefficient", "stability_margin"):
        require(isinstance(results.get(key), (int, float)), f"Missing numeric result: {key}")
        require(results[key] > 0, f"Non-positive result for {key}: {results[key]}")
    active_system = results.get("active_system") or {}
    require(active_system.get("enabled") is True, f"Active system did not run: {active_system}")
    require(active_system.get("max_surface_deployment", 0) > 0, f"Active surface never deployed: {active_system}")
    require(active_system.get("tank_pressure_final", 0) < active_system.get("tank_pressure_start", 0), f"Tank pressure did not decrease: {active_system}")
    require(len(active_system.get("history", [])) > 5, "Active-system history is missing or too short.")
    require(len(results.get("trajectory", [])) > 5, "Trajectory history is missing or too short.")
    require((results.get("controller") or {}).get("compiled_cpp") is True, "C++ controller was not compiled into the simulation.")

    string_values = " ".join(str(value).lower() for value in results.values() if isinstance(value, str))
    forbidden = ("simulated_data", "random result", "fake result")
    require(not any(token in string_values for token in forbidden), f"Result contains forbidden placeholder marker: {results}")

    summary = {
        "health": "ok",
        "motors": len(motors.get("motors", [])),
        "launch_sites": len(sites.get("launch_sites", {})),
        "controller_compile": "ok",
        "simulation_id": simulation_id,
        "max_altitude": round(results["max_altitude"], 2),
        "max_velocity": round(results["max_velocity"], 2),
        "max_deployment": round(active_system["max_surface_deployment"], 3),
        "final_tank_kpa": round(active_system["tank_pressure_final"] / 1000, 1),
        "source": results["source"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
