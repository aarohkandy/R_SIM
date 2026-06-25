import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from f_backend import MotorDatabase, app  # noqa: E402


class MotorDatabaseTests(unittest.TestCase):
    def test_seed_catalog_contains_multiple_manufacturers_and_classes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = MotorDatabase(db_path=str(Path(tmpdir) / "motors.db"))
            motors = database.get_all_motors()
            manufacturers = {motor.manufacturer for motor in motors}
            classes = {motor.impulse_class for motor in motors}

            self.assertGreaterEqual(len(motors), 18)
            self.assertIn("AeroTech", manufacturers)
            self.assertIn("Quest", manufacturers)
            self.assertIn("Cesaroni", manufacturers)
            self.assertIn("G", classes)
            self.assertIn("H", classes)

    def test_filters_by_motor_name_manufacturer_class_and_diameter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = MotorDatabase(db_path=str(Path(tmpdir) / "motors.db"))

            name_matches = database.get_all_motors(query="G40")
            manufacturer_as_search = database.get_all_motors(query="AeroTech")
            filtered = database.get_all_motors(
                manufacturer="AeroTech",
                impulse_class="G",
                diameter_mm=29,
            )

            self.assertTrue(any(motor.designation == "AeroTech G40-7W" for motor in name_matches))
            self.assertEqual(manufacturer_as_search, [])
            self.assertGreaterEqual(len(filtered), 2)
            self.assertTrue(all(motor.manufacturer == "AeroTech" for motor in filtered))
            self.assertTrue(all(motor.impulse_class == "G" for motor in filtered))
            self.assertTrue(all(abs(motor.diameter - 29.0) < 0.05 for motor in filtered))

    def test_lookup_accepts_full_or_short_designation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = MotorDatabase(db_path=str(Path(tmpdir) / "motors.db"))

            by_full_name = database.get_motor("AeroTech G40-7W")
            by_model = database.get_motor("G40-7W")

            self.assertIsNotNone(by_full_name)
            self.assertIsNotNone(by_model)
            self.assertEqual(by_full_name.designation, by_model.designation)
            self.assertGreater(len(by_model.thrust_curve), 5)


class MotorEndpointTests(unittest.TestCase):
    def test_motor_endpoint_returns_filter_metadata_and_filtered_results(self):
        client = app.test_client()
        response = client.get(
            "/api/environment/motors?manufacturer=AeroTech&impulse_class=G&query=G40"
        )
        body = response.get_json()
        motors = body["motors"]

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(body["count"], 1)
        self.assertIn("AeroTech", body["filters"]["manufacturers"])
        self.assertIn("G", body["filters"]["impulse_classes"])
        self.assertTrue(all(motor["manufacturer"] == "AeroTech" for motor in motors))
        self.assertTrue(all(motor["impulse_class"] == "G" for motor in motors))
        self.assertTrue(any(motor["designation"] == "AeroTech G40-7W" for motor in motors))


if __name__ == "__main__":
    unittest.main()
