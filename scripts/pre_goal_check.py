#!/usr/bin/env python3
"""Pre-goal backend smoke checks for local R_SIM readiness."""

from __future__ import annotations

import json
import io
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
    root_health = json_body(client.get("/health"))
    require(root_health.get("status") == "healthy", "Root health endpoint is not healthy.")

    motors = json_body(client.get("/api/environment/motors"))
    require(len(motors.get("motors", [])) >= 1, "Motor database returned no motors.")
    frontend_source = (ROOT / "frontend" / "main.jsx").read_text(encoding="utf-8")
    frontend_style = (ROOT / "frontend" / "App.css").read_text(encoding="utf-8")
    backend_source = (ROOT / "backend" / "f_backend.py").read_text(encoding="utf-8")
    gcp_client_source = (ROOT / "backend" / "gcp_cfd_client.py").read_text(encoding="utf-8")
    heavy_cfd_source = (ROOT / "backend" / "openfoam_integration.py").read_text(encoding="utf-8")
    require("GCP_FUNCTION_URL" not in frontend_source, "Frontend still defaults to a hardcoded cloud function.")
    require("Google Cloud Function" not in frontend_source, "Frontend still tells users to use a cloud function for the local workflow.")
    require("deploy_gcp_function" not in frontend_source, "Frontend still recommends deploying GCP for the local workflow.")
    require("Math.random" not in frontend_source, "Frontend contains random behavior in the main workflow.")
    require("np.random" not in backend_source, "Backend main server contains random placeholder result generation.")
    require("simulated_data" not in gcp_client_source, "GCP CFD client still synthesizes placeholder CFD payloads.")
    require("Simulation submitted (simulation mode)" not in gcp_client_source, "GCP CFD client still reports unavailable cloud work as submitted.")
    require("falling back to simulation mode" not in heavy_cfd_source, "Heavy CFD still describes missing OpenFOAM as a simulation fallback.")
    require("/api/environment/motors" in frontend_source, "Frontend motor picker is not wired to the backend motor database.")
    require("/api/environment/launch-sites" in frontend_source, "Frontend launch-site picker is not wired to the backend launch-site database.")
    require("mockMotors" not in frontend_source, "Frontend motor picker still contains a mock motor list.")
    require("pneumaticPressureStd" in frontend_source, "Frontend setup is missing explicit pneumatic pressure noise controls.")
    require("function LineChart" in frontend_source, "Frontend results view is missing live chart rendering.")
    require("exportResults('forces')" in frontend_source, "Frontend force/moment CSV export is missing.")
    require("exportResults('active')" in frontend_source, "Frontend active-system CSV export is missing.")
    require("exportResults('recovery')" in frontend_source, "Frontend recovery CSV export is missing.")
    require("getDesignChecks" in frontend_source, "Frontend is missing live design checks.")
    require("fieldChecks" in frontend_source, "Frontend design checks are not wired to inputs.")
    require("field-message" in frontend_source, "Frontend fields do not render design-check messages.")
    require("field-message" in frontend_style, "Frontend fields do not style design-check messages.")
    database_motor = next(
        (motor for motor in motors.get("motors", []) if motor.get("designation") == "Estes C6-5"),
        motors["motors"][0],
    )
    database_thrust_curve = [
        {"time": time_point, "thrust": thrust_value}
        for time_point, thrust_value in database_motor.get("thrust_curve", [])
    ]
    require(len(database_thrust_curve) > 5, f"Backend motor database did not provide a usable thrust curve: {database_motor}")

    sites = json_body(client.get("/api/environment/launch-sites"))
    require(len(sites.get("launch_sites", {})) >= 1, "Launch-site endpoint returned no sites.")

    sample_openrocket = b"""<?xml version="1.0" encoding="UTF-8"?>
<openrocket>
  <rocket>
    <name>Pre Goal Imported Rocket</name>
    <subcomponents><stage><subcomponents>
      <nosecone><name>Nose</name><length>0.120</length><aftRadius>0.020</aftRadius><mass>0.035</mass></nosecone>
      <bodytube><name>Body</name><length>0.560</length><outerRadius>0.020</outerRadius><mass>0.135</mass>
        <subcomponents>
          <trapezoidfinset><name>Fins</name><finCount>3</finCount><rootChord>0.090</rootChord><height>0.055</height><mass>0.045</mass></trapezoidfinset>
          <motor><manufacturer>Estes</manufacturer><designation>Estes C6-5</designation><diameter>0.018</diameter><length>0.070</length><burnTime>1.600</burnTime><totalImpulse>10.000</totalImpulse><averageThrust>6.000</averageThrust><mass>0.017</mass></motor>
        </subcomponents>
      </bodytube>
    </subcomponents></stage></subcomponents>
  </rocket>
</openrocket>
"""
    imported = json_body(client.post(
        "/api/openrocket/import",
        data={"file": (io.BytesIO(sample_openrocket), "pre-goal.ork")},
        content_type="multipart/form-data",
    ))
    require(imported.get("success") is True, f"OpenRocket import failed: {imported}")
    imported_rocket = imported.get("rocketData") or {}
    imported_components = imported_rocket.get("components") or []
    require(len(imported_components) >= 4, f"OpenRocket import returned too few components: {imported}")
    imported_motor = next((component for component in imported_components if component.get("type") == "Motor"), {})
    require(len(imported_motor.get("thrustCurve", [])) > 5, f"Imported motor was not enriched with thrust curve: {imported_motor}")

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

    unsafe_code = controller_code.replace("return out;", 'system("echo unsafe"); return out;')
    unsafe_compile = json_body(client.post("/api/control-code/compile", json={"code": unsafe_code}))
    require(unsafe_compile.get("success") is False, f"Unsafe controller compiled unexpectedly: {unsafe_compile}")
    require("Forbidden" in unsafe_compile.get("message", ""), f"Unsafe controller did not return a clear safety message: {unsafe_compile}")

    payload = {
        "rocketComponents": [
            {"id": 1, "type": "Nose Cone", "name": "Prep Nose", "length": 120, "diameter": 40, "weight": 35},
            {"id": 2, "type": "Body Tube", "name": "Prep Body", "length": 560, "diameter": 40, "weight": 135},
            {"id": 3, "type": "Fins", "name": "Prep Fins", "finCount": 3, "finHeight": 55, "finWidth": 90, "weight": 45},
            {
                "id": 4,
                "type": "Motor",
                "name": f"{database_motor['manufacturer']} {database_motor['designation']}",
                "length": database_motor["length"],
                "diameter": database_motor["diameter"],
                "motorType": database_motor["manufacturer"],
                "motorModel": database_motor["designation"],
                "motorImpulse": database_motor["impulse_class"],
                "motorThrust": database_motor["average_thrust"],
                "motorBurnTime": database_motor["burn_time"],
                "motorTotalImpulse": database_motor["total_impulse"],
                "motorDelay": database_motor["delay_time"],
                "motorWeight": database_motor["total_mass"],
                "weight": database_motor["total_mass"],
                "thrustCurve": database_thrust_curve,
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
    require(len(results.get("force_history", [])) > 5, "Force history is missing or too short.")
    require(len(results.get("moment_history", [])) > 5, "Moment history is missing or too short.")
    first_sample = results["trajectory"][0]
    for key in ("net_force_z", "thrust_force", "pitch_moment", "angular_velocity_y_deg_s", "drag_coefficient"):
        require(key in first_sample, f"Trajectory sample missing {key}: {first_sample}")
    require((results.get("controller") or {}).get("compiled_cpp") is True, "C++ controller was not compiled into the simulation.")
    require((results.get("thrust_profile") or {}).get("source") == "curve", f"Sample simulation did not use backend motor thrust curve: {results.get('thrust_profile')}")

    string_values = " ".join(str(value).lower() for value in results.values() if isinstance(value, str))
    forbidden = ("simulated_data", "random result", "fake result")
    require(not any(token in string_values for token in forbidden), f"Result contains forbidden placeholder marker: {results}")

    summary = {
        "health": "ok",
        "motors": len(motors.get("motors", [])),
        "motor_curve_points": len(database_thrust_curve),
        "launch_sites": len(sites.get("launch_sites", {})),
        "openrocket_import": len(imported_components),
        "controller_compile": "ok",
        "controller_safety": "ok",
        "simulation_id": simulation_id,
        "max_altitude": round(results["max_altitude"], 2),
        "max_velocity": round(results["max_velocity"], 2),
        "max_deployment": round(active_system["max_surface_deployment"], 3),
        "final_tank_kpa": round(active_system["tank_pressure_final"] / 1000, 1),
        "force_samples": len(results["force_history"]),
        "moment_samples": len(results["moment_history"]),
        "source": results["source"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
