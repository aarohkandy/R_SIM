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
    require(len(motors.get("motors", [])) >= 18, "Motor database returned too few motors for a useful local catalog.")
    motor_filters = motors.get("filters") or {}
    require("AeroTech" in motor_filters.get("manufacturers", []), "Motor filters are missing AeroTech manufacturer metadata.")
    require("G" in motor_filters.get("impulse_classes", []), "Motor filters are missing G impulse-class metadata.")
    filtered_motors = json_body(client.get("/api/environment/motors?manufacturer=AeroTech&impulse_class=G&query=G40"))
    require(filtered_motors.get("count", 0) >= 1, f"Filtered motor search returned no matches: {filtered_motors}")
    require(
        all(motor.get("manufacturer") == "AeroTech" for motor in filtered_motors.get("motors", [])),
        f"Filtered motor search returned the wrong manufacturer: {filtered_motors}",
    )
    require(
        all(motor.get("impulse_class") == "G" for motor in filtered_motors.get("motors", [])),
        f"Filtered motor search returned the wrong impulse class: {filtered_motors}",
    )
    motor_import = json_body(client.post(
        "/api/environment/motors/import",
        data={
            "file": (
                io.BytesIO(b"PGX9 24 70 5 0.010 0.025 PreGoal\n0 0\n0.05 20\n0.20 10\n0.40 0\n"),
                "pre-goal-x9.eng",
            )
        },
        content_type="multipart/form-data",
    ))
    require(motor_import.get("success"), f"Motor file import failed: {motor_import}")
    require(len(motor_import.get("motor", {}).get("thrust_curve", [])) == 4, f"Imported motor curve was not preserved: {motor_import}")
    frontend_source = (ROOT / "frontend" / "main.jsx").read_text(encoding="utf-8")
    frontend_style = (ROOT / "frontend" / "App.css").read_text(encoding="utf-8")
    backend_source = (ROOT / "backend" / "f_backend.py").read_text(encoding="utf-8")
    active_sim_source = (ROOT / "backend" / "active_simulation.py").read_text(encoding="utf-8")
    openrocket_source = (ROOT / "backend" / "openrocket_import.py").read_text(encoding="utf-8")
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
    require("/api/environment/motors/import" in frontend_source and "Import motor file" in frontend_source, "Frontend motor picker cannot import motor curve files.")
    require("parse_motor_file" in backend_source, "Backend is missing common motor-file import parsing.")
    require("motorFilters" in frontend_source, "Frontend motor picker is missing catalog filters.")
    require("Impulse" in frontend_source and "Manufacturer" in frontend_source and "TARC approved" in frontend_source, "Frontend motor picker is missing expected filter controls.")
    require("/api/environment/launch-sites" in frontend_source, "Frontend launch-site picker is not wired to the backend launch-site database.")
    require("mockMotors" not in frontend_source, "Frontend motor picker still contains a mock motor list.")
    require("pneumaticPressureStd" in frontend_source, "Frontend setup is missing explicit pneumatic pressure noise controls.")
    require("function LineChart" in frontend_source, "Frontend results view is missing live chart rendering.")
    require("exportResults('forces')" in frontend_source, "Frontend force/moment CSV export is missing.")
    require("exportResults('active')" in frontend_source, "Frontend active-system CSV export is missing.")
    require("exportResults('recovery')" in frontend_source, "Frontend recovery CSV export is missing.")
    require("exportResults('recovery-summary')" in frontend_source, "Frontend recovery summary CSV export is missing.")
    require("getDesignChecks" in frontend_source, "Frontend is missing live design checks.")
    require("fieldChecks" in frontend_source, "Frontend design checks are not wired to inputs.")
    require("field-message" in frontend_source, "Frontend fields do not render design-check messages.")
    require("field-message" in frontend_style, "Frontend fields do not style design-check messages.")
    require("SimulationSetupPanel" in frontend_source, "Frontend is missing the named simulation setup manager.")
    require("simulationSetups" in frontend_source, "Frontend does not persist named simulation setups.")
    require("runSetup" in frontend_source, "Frontend cannot run a selected simulation setup.")
    require("setup-row" in frontend_style, "Frontend simulation setup manager is missing list styling.")
    require("getComponentAxialPosition" in frontend_source, "Frontend does not model editable component axial placement.")
    require("Axial position" in frontend_source, "Component inspector is missing axial position editing.")
    require("attachmentHostTypes" in frontend_source, "Frontend is missing valid subpart attachment hosts.")
    require("Attached to" in frontend_source, "Component inspector is missing subpart attachment editing.")
    require("getAttachmentHost(component, components)" in frontend_source, "Component table is missing subpart attachment visibility.")
    require("getTreeAttachmentGroups" in frontend_source and "tree-children" in frontend_style, "Frontend design tree does not nest attached subparts under their host.")
    require("Mass Component" in frontend_source, "Frontend is missing internal payload/ballast mass components.")
    require("mass-marker" in frontend_source and "mass-marker" in frontend_style, "Rocket drawing is missing internal mass markers.")
    require("Tube Coupler" in frontend_source, "Frontend is missing internal tube coupler components.")
    require("tube-coupler-marker" in frontend_source and "tube-coupler-marker" in frontend_style, "Rocket drawing is missing tube coupler markers.")
    require("Bulkhead" in frontend_source, "Frontend is missing internal bulkhead components.")
    require("bulkhead-marker" in frontend_source and "bulkhead-marker" in frontend_style, "Rocket drawing is missing bulkhead markers.")
    require("Parachute" in frontend_source, "Frontend is missing explicit recovery parachute components.")
    require("parachute-marker" in frontend_source and "parachute-marker" in frontend_style, "Rocket drawing is missing parachute recovery markers.")
    require("Streamer" in frontend_source, "Frontend is missing explicit recovery streamer components.")
    require("streamer-marker" in frontend_source and "streamer-marker" in frontend_style, "Rocket drawing is missing streamer recovery markers.")
    require("Shock Cord" in frontend_source, "Frontend is missing explicit recovery shock-cord components.")
    require("shock-cord-marker" in frontend_source and "shock-cord-marker" in frontend_style, "Rocket drawing is missing shock-cord recovery markers.")
    require("Motor Mount" in frontend_source, "Frontend is missing internal motor mount components.")
    require("motor-mount-marker" in frontend_source and "motor-mount-marker" in frontend_style, "Rocket drawing is missing motor mount markers.")
    require("Centering Ring" in frontend_source, "Frontend is missing internal centering ring components.")
    require("centering-ring-marker" in frontend_source and "centering-ring-marker" in frontend_style, "Rocket drawing is missing centering ring markers.")
    require("rail-button-dot" in frontend_style, "Rocket drawing does not render rail button placement.")
    require("position_m" in active_sim_source, "Backend CP contributions do not expose fin axial placement.")
    require("attachment must reference" in active_sim_source, "Backend does not reject invalid subpart attachment references.")
    require("mass component" in active_sim_source and "internal_component_types" in active_sim_source, "Backend does not treat mass components as internal geometry.")
    require("_apply_recovery_components_to_config" in active_sim_source, "Backend does not derive landing config from parachute components.")
    require("masscomponent" in openrocket_source, "OpenRocket import does not preserve mass components.")
    require("parachute" in openrocket_source, "OpenRocket import does not preserve parachute components.")
    require("streamer" in openrocket_source, "OpenRocket import does not preserve streamer components.")
    require("shockcord" in openrocket_source, "OpenRocket import does not preserve shock-cord components.")
    require("motor mount" in active_sim_source and "centering ring" in active_sim_source, "Backend does not treat motor mount hardware as internal geometry.")
    require("innertube" in openrocket_source and "centeringring" in openrocket_source, "OpenRocket import does not preserve motor mount hardware.")
    require("tube coupler" in active_sim_source and "bulkhead" in active_sim_source, "Backend does not treat airframe internal hardware as internal geometry.")
    require("tubecoupler" in openrocket_source and "bulkhead" in openrocket_source, "OpenRocket import does not preserve airframe internal hardware.")
    require("Airbrake station" in frontend_source, "Frontend is missing active airbrake station controls.")
    require("active.locationFromNose" in frontend_source, "Frontend design checks do not target active airbrake station.")
    require("moment_arm_m" in active_sim_source, "Backend active system does not report active airbrake moment arm.")
    require("active_drag_force" in active_sim_source, "Backend force history is missing active drag force.")
    require("MotorCurvePanel" in frontend_source, "Frontend is missing selected motor thrust curve inspection.")
    require("Simplify to edit" in frontend_source, "Frontend motor curve editor is missing sampled editing controls.")
    require("motorPatchFromCurve" in frontend_source, "Frontend motor curve edits do not sync motor impulse fields.")
    require("Motor thrust curve must include at least two valid time/thrust points." in active_sim_source, "Backend does not reject invalid supplied thrust curves.")
    require("LandingFootprintMap" in frontend_source, "Frontend results view is missing landing footprint map.")
    require("RecoveryAnalysisPanel" in frontend_source, "Frontend results view is missing recovery analysis panel.")
    require("RecoverySafetyPanel" in frontend_source, "Frontend results view is missing recovery safety panel.")
    require("tree-add-split" in frontend_source, "Frontend design tree is missing split-marker controls.")
    require("split-marker" in frontend_source, "Frontend rocket drawing is missing split-marker rendering.")
    require("rocketSplitPoints" in frontend_source, "Frontend simulation payload does not include split markers.")
    require("landing_footprint" in active_sim_source, "Backend does not report landing footprint output.")
    require("recovery_analysis" in active_sim_source, "Backend does not report recovery analysis output.")
    require("recovery_safety" in active_sim_source, "Backend does not report recovery safety output.")
    require("harness_limit_n" in active_sim_source and "effective_opening_load_limit_g" in active_sim_source, "Backend recovery safety does not apply shock-cord harness limits.")
    require("stage_splits" in active_sim_source, "Backend does not report stage/split marker output.")
    require("drift_after_main_deploy_m" in active_sim_source, "Backend does not report recovery drift after main deployment.")
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
          <masscomponent><name>Tracker Battery</name><mass>0.065</mass><position>0.240</position><role>battery</role></masscomponent>
          <parachute><name>Main Parachute</name><mass>0.038</mass><diameter>0.550</diameter><cd>1.60</cd><deployAltitude>0.080</deployAltitude></parachute>
          <streamer><name>Drogue Streamer</name><mass>0.016</mass><stripLength>1.200</stripLength><stripWidth>0.080</stripWidth><cd>1.05</cd><deployEvent>apogee</deployEvent></streamer>
          <shockcord><name>Nylon Harness</name><mass>0.024</mass><length>3.000</length><diameter>0.003</diameter><maxTensionN>450</maxTensionN></shockcord>
          <tubeCoupler><name>Payload Coupler</name><mass>0.028</mass><length>0.084</length><innerRadius>0.024</innerRadius><outerRadius>0.026</outerRadius></tubeCoupler>
          <bulkhead><name>Avionics Bulkhead</name><mass>0.022</mass><outerRadius>0.020</outerRadius><thickness>0.005</thickness></bulkhead>
          <innertube><name>Motor Mount Tube</name><mass>0.036</mass><length>0.160</length><innerRadius>0.0145</innerRadius><outerRadius>0.017</outerRadius></innertube>
          <centeringring><name>Centering Rings</name><mass>0.018</mass><ringCount>2</ringCount><innerRadius>0.017</innerRadius><outerRadius>0.020</outerRadius><thickness>0.004</thickness></centeringring>
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
    imported_mass = next((component for component in imported_components if component.get("type") == "Mass Component"), {})
    imported_parachute = next((component for component in imported_components if component.get("type") == "Parachute"), {})
    imported_streamer = next((component for component in imported_components if component.get("type") == "Streamer"), {})
    imported_shock_cord = next((component for component in imported_components if component.get("type") == "Shock Cord"), {})
    imported_motor_mount = next((component for component in imported_components if component.get("type") == "Motor Mount"), {})
    imported_centering_ring = next((component for component in imported_components if component.get("type") == "Centering Ring"), {})
    imported_coupler = next((component for component in imported_components if component.get("type") == "Tube Coupler"), {})
    imported_bulkhead = next((component for component in imported_components if component.get("type") == "Bulkhead"), {})
    require(len(imported_motor.get("thrustCurve", [])) > 5, f"Imported motor was not enriched with thrust curve: {imported_motor}")
    require(imported_mass.get("massRole") == "battery", f"Imported OpenRocket mass component was not preserved: {imported_components}")
    require(imported_parachute.get("dragArea", 0) > 0.2, f"Imported OpenRocket parachute was not preserved: {imported_components}")
    require(abs(imported_streamer.get("dragArea", 0) - 0.096) < 1e-9, f"Imported OpenRocket streamer was not preserved: {imported_components}")
    require(imported_shock_cord.get("maxTensionN") == 450, f"Imported OpenRocket shock cord was not preserved: {imported_components}")
    require(imported_motor_mount.get("mountLength") == 160, f"Imported OpenRocket motor mount was not preserved: {imported_components}")
    require(imported_centering_ring.get("ringCount") == 2, f"Imported OpenRocket centering ring was not preserved: {imported_components}")
    require(imported_coupler.get("couplerLength") == 84, f"Imported OpenRocket tube coupler was not preserved: {imported_components}")
    require(imported_bulkhead.get("thickness") == 5, f"Imported OpenRocket bulkhead was not preserved: {imported_components}")

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
            {"id": 3, "type": "Fins", "name": "Prep Fins", "finCount": 3, "finHeight": 55, "finWidth": 90, "weight": 45, "attachedToComponent": 2},
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
                "attachedToComponent": 2,
            },
            {"id": 5, "type": "Mass Component", "name": "Tracker Battery", "weight": 65, "massRole": "battery", "axialPosition": 240, "attachedToComponent": 2},
            {"id": 6, "type": "Parachute", "name": "Prep Main Parachute", "weight": 38, "recoveryRole": "main", "deployEvent": "altitude", "deployAltitude": 80, "dragArea": 0.18, "dragCoefficient": 1.55, "maxOpeningLoadG": 15, "axialPosition": 240, "attachedToComponent": 2},
            {"id": 7, "type": "Streamer", "name": "Prep Drogue Streamer", "weight": 16, "recoveryRole": "drogue", "deployEvent": "apogee", "streamerLength": 1.2, "streamerWidth": 0.08, "dragCoefficient": 1.05, "maxOpeningLoadG": 12, "axialPosition": 245, "attachedToComponent": 2},
            {"id": 8, "type": "Shock Cord", "name": "Prep Nylon Harness", "weight": 24, "cordLength": 3.0, "cordDiameter": 3.0, "maxTensionN": 450, "axialPosition": 250, "attachedToComponent": 2},
            {"id": 9, "type": "Motor Mount", "name": "Prep Motor Mount Tube", "weight": 36, "mountLength": 160, "innerDiameter": 29, "outerDiameter": 34, "axialPosition": 500, "attachedToComponent": 2},
            {"id": 10, "type": "Centering Ring", "name": "Prep Centering Rings", "weight": 18, "ringCount": 2, "innerDiameter": 34, "outerDiameter": 40, "thickness": 4, "axialPosition": 505, "attachedToComponent": 2},
            {"id": 11, "type": "Tube Coupler", "name": "Prep Payload Coupler", "weight": 28, "couplerLength": 84, "innerDiameter": 36, "outerDiameter": 39, "axialPosition": 180, "attachedToComponent": 2},
            {"id": 12, "type": "Bulkhead", "name": "Prep Avionics Bulkhead", "weight": 22, "outerDiameter": 40, "thickness": 5, "axialPosition": 210, "attachedToComponent": 2},
        ],
        "rocketSplitPoints": [
            {"id": "prep-split", "afterComponentId": "1", "label": "Payload split"},
        ],
        "rocketWeight": 425,
        "rocketCG": 296,
        "totalHeight": 680,
        "simulationConfig": {
            "timeStep": 0.02,
            "maxTime": 80,
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
            "landingSystem": {
                "enabled": True,
                "type": "main_parachute",
                "mainDeployEvent": "altitude",
                "deployAltitude": 80,
                "dragArea": 0.18,
                "dragCoefficient": 1.55,
                "maxSafeVelocity": 7.5,
                "maxOpeningLoadG": 15,
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
    landing_system = results.get("landing_system") or {}
    require(landing_system.get("type") == "drogue_main", f"Streamer drogue did not enable drogue-main landing: {landing_system}")
    require(abs(landing_system.get("drag_area_m2", 0) - 0.18) < 1e-9, f"Parachute component did not drive landing drag area: {landing_system}")
    require(abs(landing_system.get("drogue_drag_area_m2", 0) - 0.096) < 1e-9, f"Streamer component did not drive drogue drag area: {landing_system}")
    require(abs(landing_system.get("harness_limit_n", 0) - 450) < 1e-9, f"Shock cord did not drive harness limit: {landing_system}")
    stage_splits = results.get("stage_splits") or []
    require(len(stage_splits) == 1, f"Stage split markers were not preserved: {stage_splits}")
    require(stage_splits[0].get("label") == "Payload split", f"Stage split label was not preserved: {stage_splits}")
    require(abs(stage_splits[0].get("position_mm", 0) - 120.0) < 1e-6, f"Stage split position is wrong: {stage_splits}")
    landing_footprint = results.get("landing_footprint") or {}
    require(landing_footprint.get("touchdown_range_m") is not None, "Landing footprint touchdown range is missing.")
    require(landing_footprint.get("touchdown_bearing_deg") is not None, "Landing footprint touchdown bearing is missing.")
    require(landing_footprint.get("drift_after_main_deploy_m") is not None, "Landing footprint main-deployment drift is missing.")
    recovery_analysis = results.get("recovery_analysis") or {}
    require(len(recovery_analysis.get("deployment_sequence", [])) >= 3, "Recovery analysis deployment sequence is missing.")
    require(any(phase.get("name") == "Main descent" for phase in recovery_analysis.get("phases", [])), "Recovery analysis main descent phase is missing.")
    recovery_safety = results.get("recovery_safety") or {}
    require(recovery_safety.get("main_terminal_velocity_mps") is not None, "Recovery safety terminal velocity is missing.")
    require(recovery_safety.get("required_main_drag_area_m2") is not None, "Recovery safety required area is missing.")
    require(recovery_safety.get("main_opening_load_g") is not None, "Recovery safety opening load is missing.")
    require(abs(recovery_safety.get("harness_load_limit_n", 0) - 450) < 1e-9, f"Recovery safety harness limit is missing: {recovery_safety}")
    require(recovery_safety.get("effective_opening_load_limit_g") is not None, "Recovery safety effective opening limit is missing.")
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
        "motor_catalog": len(motors.get("motors", [])),
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
        "touchdown_range": round(landing_footprint["touchdown_range_m"], 2),
        "recovery_phases": len(recovery_analysis["phases"]),
        "main_opening_load_g": round(recovery_safety["main_opening_load_g"], 2),
        "stage_splits": len(stage_splits),
        "source": results["source"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
