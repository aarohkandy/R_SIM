import unittest

from backend.active_simulation import ActiveSimulationManager


def sample_rocket():
    return {
        "components": [
            {"id": 1, "type": "Nose Cone", "length": 120, "diameter": 40, "weight": 35},
            {"id": 2, "type": "Body Tube", "length": 560, "diameter": 40, "weight": 135},
            {"id": 3, "type": "Fins", "finCount": 3, "finHeight": 55, "finWidth": 90, "weight": 45},
            {
                "id": 4,
                "type": "Motor",
                "length": 70,
                "diameter": 18,
                "motorThrust": 6.0,
                "motorBurnTime": 1.6,
                "motorTotalImpulse": 10.0,
                "weight": 17,
            },
        ],
        "weight": 232,
        "cg": 320,
        "totalHeight": 680,
    }


def base_config(enabled=True, target_apogee=60):
    return {
        "timeStep": 0.02,
        "maxTime": 20,
        "windSpeed": 1.5,
        "windDirection": 25,
        "temperature": 15,
        "pressure": 101325,
        "activeSystem": {
            "enabled": enabled,
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
            "targetApogee": target_apogee,
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
    }


class ActiveSimulationTests(unittest.TestCase):
    def test_active_simulation_is_deterministic_for_same_seed(self):
        manager = ActiveSimulationManager()
        first = manager.submit_cfd_simulation(sample_rocket(), base_config())
        second = manager.submit_cfd_simulation(sample_rocket(), base_config())

        first_results = first["results"]
        second_results = second["results"]
        self.assertAlmostEqual(first_results["max_altitude"], second_results["max_altitude"], places=9)
        self.assertAlmostEqual(first_results["max_velocity"], second_results["max_velocity"], places=9)
        self.assertEqual(first_results["trajectory"], second_results["trajectory"])
        self.assertEqual(first_results["active_system"]["history"], second_results["active_system"]["history"])

    def test_active_system_deploys_and_consumes_pressure(self):
        manager = ActiveSimulationManager()
        result = manager.submit_cfd_simulation(sample_rocket(), base_config())["results"]
        active = result["active_system"]

        self.assertTrue(active["enabled"])
        self.assertGreater(active["max_surface_deployment"], 0.1)
        self.assertLess(active["tank_pressure_final"], active["tank_pressure_start"])
        self.assertGreater(len(active["history"]), 5)
        self.assertGreater(len(result["trajectory"]), 5)

    def test_active_drag_changes_flight_profile(self):
        manager = ActiveSimulationManager()
        passive = manager.submit_cfd_simulation(sample_rocket(), base_config(enabled=False))["results"]
        active = manager.submit_cfd_simulation(sample_rocket(), base_config(enabled=True, target_apogee=35))["results"]

        self.assertEqual(passive["active_system"]["max_surface_deployment"], 0)
        self.assertGreater(active["active_system"]["max_surface_deployment"], 0.1)
        self.assertLess(active["max_altitude"], passive["max_altitude"])
        self.assertGreater(active["max_drag_force"], passive["max_drag_force"])

    def test_pressure_warning_when_tank_is_too_small(self):
        config = base_config()
        config["activeSystem"]["tankPressure"] = 175000
        config["activeSystem"]["tankVolume"] = 0.03
        manager = ActiveSimulationManager()
        result = manager.submit_cfd_simulation(sample_rocket(), config)["results"]

        self.assertTrue(any("minimum operating pressure" in warning for warning in result["warnings"]))

    def test_missing_motor_is_rejected(self):
        rocket = sample_rocket()
        rocket["components"] = [component for component in rocket["components"] if component["type"] != "Motor"]
        manager = ActiveSimulationManager()
        result = manager.submit_cfd_simulation(rocket, base_config())

        self.assertFalse(result["success"])
        self.assertIn("Rocket must include a motor.", result["validation_errors"])

    def test_invalid_active_pressure_is_rejected(self):
        config = base_config()
        config["activeSystem"]["tankPressure"] = 90000
        manager = ActiveSimulationManager()
        result = manager.submit_cfd_simulation(sample_rocket(), config)

        self.assertFalse(result["success"])
        self.assertIn("Active tank pressure must be above ambient pressure.", result["validation_errors"])

    def test_force_and_moment_histories_are_exported(self):
        manager = ActiveSimulationManager()
        result = manager.submit_cfd_simulation(sample_rocket(), base_config())["results"]
        sample = result["trajectory"][0]

        self.assertGreater(len(result["force_history"]), 5)
        self.assertGreater(len(result["moment_history"]), 5)
        self.assertIn("net_force_z", sample)
        self.assertIn("pitch_moment", sample)
        self.assertIn("angular_velocity_y_deg_s", sample)
        self.assertGreater(result["max_net_force"], 0)

    def test_motor_thrust_curve_is_interpolated(self):
        rocket = sample_rocket()
        motor = next(component for component in rocket["components"] if component["type"] == "Motor")
        motor["thrustCurve"] = [
            {"time": 0.0, "thrust": 0.0},
            {"time": 0.08, "thrust": 18.0},
            {"time": 0.35, "thrust": 12.0},
            {"time": 1.25, "thrust": 4.0},
            {"time": 1.65, "thrust": 0.0},
        ]
        manager = ActiveSimulationManager()
        result = manager.submit_cfd_simulation(rocket, base_config())["results"]
        thrust_values = {row["thrust_force"] for row in result["force_history"][:10]}

        self.assertEqual(result["thrust_profile"]["source"], "curve")
        self.assertGreater(result["thrust_profile"]["integrated_impulse"], 0)
        self.assertGreater(len(thrust_values), 2)

    def test_aero_drag_table_changes_effective_drag(self):
        manager = ActiveSimulationManager()
        baseline = manager.submit_cfd_simulation(sample_rocket(), base_config(target_apogee=35))["results"]
        config = base_config(target_apogee=35)
        config["aerodynamics"] = {
            "baseDragCoefficient": 0.5,
            "activeDragCoefficientTable": [
                {"deployment": 0.0, "cdIncrement": 0.0},
                {"deployment": 0.5, "cdIncrement": 4.0},
                {"deployment": 1.0, "cdIncrement": 7.5},
            ],
        }
        calibrated = manager.submit_cfd_simulation(sample_rocket(), config)["results"]

        self.assertEqual(calibrated["aerodynamics"]["active_drag_model"], "table")
        self.assertGreater(calibrated["max_drag_coefficient"], baseline["max_drag_coefficient"])
        self.assertGreater(calibrated["max_drag_force"], baseline["max_drag_force"])


if __name__ == "__main__":
    unittest.main()
