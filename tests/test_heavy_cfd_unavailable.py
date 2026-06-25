import unittest

from backend.openfoam_integration import HeavyCFDManager


class HeavyCFDUnavailableTests(unittest.TestCase):
    def test_heavy_cfd_fails_honestly_without_openfoam(self):
        manager = HeavyCFDManager()
        manager.openfoam_available = False

        response = manager.start_simulation([], 0, 0, {})
        serialized = str(response).lower()

        self.assertFalse(response["success"])
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["source"], "openfoam_unavailable")
        self.assertNotIn("simulation mode", serialized)
        self.assertNotIn("simulated", serialized)
        self.assertNotIn("fake", serialized)

    def test_status_marks_openfoam_unavailable(self):
        manager = HeavyCFDManager()
        manager.openfoam_available = False

        status = manager.get_status()

        self.assertEqual(status["source"], "openfoam_unavailable")
        self.assertFalse(status["openfoam_available"])


if __name__ == "__main__":
    unittest.main()
