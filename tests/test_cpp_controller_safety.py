import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from f_backend import CPPControlSystem, HardwareLimitations, app  # noqa: E402


def hardware_limits():
    return HardwareLimitations(
        servo_max_speed=180.0,
        servo_max_torque=0.5,
        servo_response_time=0.02,
        sensor_noise_level=5.0,
        sensor_update_rate=100.0,
        max_fin_deflection=15.0,
        battery_voltage=7.4,
        processing_delay=0.001,
    )


SAFE_CODE = """
ControlOutput control_function(SensorData sensor_data) {
    ControlOutput out{};
    double command = sensor_data.predicted_apogee > 100.0 ? 0.25 : 0.0;
    out.fin_deflection_1 = 0.0;
    out.fin_deflection_2 = 0.0;
    out.fin_deflection_3 = 0.0;
    out.fin_deflection_4 = 0.0;
    out.valve_command = command;
    out.surface_target = command;
    out.recovery_trigger = false;
    return out;
}
"""


class CPPControllerSafetyTests(unittest.TestCase):
    def test_safe_controller_compiles_and_runs(self):
        control = CPPControlSystem(hardware_limits())
        program_id = "safe-controller-test"
        try:
            success, message = control.compile_cpp_code(SAFE_CODE, program_id)
            self.assertTrue(success, message)
            output = control.run_control_program(program_id, {"predicted_apogee": 150.0})
            self.assertEqual(output["valve_command"], 0.25)
            self.assertEqual(output["surface_target"], 0.25)
        finally:
            control.cleanup_program(program_id)

    def test_rejects_preprocessor_and_console_io(self):
        control = CPPControlSystem(hardware_limits())
        include_code = '#include <fstream>\n' + SAFE_CODE
        io_code = SAFE_CODE.replace("return out;", "std::cout << 1; return out;")

        include_success, include_message = control.validate_cpp_code(include_code)
        io_success, io_message = control.validate_cpp_code(io_code)

        self.assertFalse(include_success)
        self.assertIn("preprocessor", include_message)
        self.assertFalse(io_success)
        self.assertIn("console I/O", io_message)

    def test_comments_and_string_literals_do_not_trigger_forbidden_scanner(self):
        control = CPPControlSystem(hardware_limits())
        commented = SAFE_CODE.replace(
            "double command",
            '// system("nope"); std::cout << "nope";\n    double command',
        )

        success, message = control.validate_cpp_code(commented)

        self.assertTrue(success, message)

    def test_compile_endpoint_rejects_process_escape(self):
        client = app.test_client()
        unsafe_code = SAFE_CODE.replace("return out;", 'system("echo unsafe"); return out;')

        response = client.post("/api/control-code/compile", json={"code": unsafe_code})
        body = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(body["success"])
        self.assertIsNone(body["program_id"])
        self.assertIn("shell execution", body["message"])

    def test_runtime_timeout_returns_clear_error(self):
        control = CPPControlSystem(hardware_limits(), runtime_timeout_seconds=0.05)
        program_id = "timeout-controller-test"
        slow_code = """
ControlOutput control_function(SensorData sensor_data) {
    ControlOutput out{};
    double acc = 0.0;
    for (long long i = 0; i < 500000000LL; ++i) {
        acc += std::sin(sensor_data.timestamp + static_cast<double>(i));
    }
    out.valve_command = acc;
    out.surface_target = acc;
    return out;
}
"""
        try:
            success, message = control.compile_cpp_code(slow_code, program_id)
            self.assertTrue(success, message)
            with self.assertRaisesRegex(RuntimeError, "runtime timeout"):
                control.run_control_program(program_id, {"timestamp": 1.0})
        finally:
            control.cleanup_program(program_id)

    def test_controller_outputs_are_clamped(self):
        control = CPPControlSystem(hardware_limits())
        program_id = "clamp-controller-test"
        clamp_code = """
ControlOutput control_function(SensorData sensor_data) {
    ControlOutput out{};
    out.fin_deflection_1 = 999.0;
    out.fin_deflection_2 = -999.0;
    out.fin_deflection_3 = 20.0;
    out.fin_deflection_4 = -20.0;
    out.valve_command = 5.0;
    out.surface_target = -3.0;
    out.recovery_trigger = true;
    return out;
}
"""
        try:
            success, message = control.compile_cpp_code(clamp_code, program_id)
            self.assertTrue(success, message)
            output = control.run_control_program(program_id, {})
            self.assertEqual(output["fin_deflection_1"], 15.0)
            self.assertEqual(output["fin_deflection_2"], -15.0)
            self.assertEqual(output["valve_command"], 1.0)
            self.assertEqual(output["surface_target"], 0.0)
            self.assertTrue(output["recovery_trigger"])
        finally:
            control.cleanup_program(program_id)


if __name__ == "__main__":
    unittest.main()
