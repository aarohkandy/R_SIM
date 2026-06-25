import unittest

from backend.gcp_cfd_client import GCPCFDClient


class GCPCFDClientUnavailableTests(unittest.TestCase):
    def setUp(self):
        self.client = GCPCFDClient(service_account_path="/tmp/rsim-missing-service-account.json")
        self.client.set_function_url("rocket-cfd-simulator")

    def assert_fails_honestly(self, response):
        serialized = str(response).lower()
        self.assertFalse(response["success"])
        self.assertEqual(response["source"], "gcp_cfd_unavailable")
        self.assertNotIn("simulated_data", serialized)
        self.assertNotIn("simulation mode", serialized)
        self.assertNotIn("fake", serialized)

    def test_submit_fails_when_credentials_are_missing(self):
        response = self.client.submit_cfd_simulation({"components": []}, {})

        self.assert_fails_honestly(response)
        self.assertEqual(response["status"], "unavailable")

    def test_status_alias_fails_without_crashing(self):
        response = self.client.get_status("cloud-run-1")

        self.assert_fails_honestly(response)
        self.assertEqual(response["simulation_id"], "cloud-run-1")
        self.assertEqual(response["progress"], 0)

    def test_results_do_not_synthesize_payloads(self):
        response = self.client.get_simulation_results("cloud-run-1")

        self.assert_fails_honestly(response)
        self.assertNotIn("results", response)

    def test_cancel_fails_when_credentials_are_missing(self):
        response = self.client.cancel_simulation("cloud-run-1")

        self.assert_fails_honestly(response)
        self.assertEqual(response["simulation_id"], "cloud-run-1")


if __name__ == "__main__":
    unittest.main()
