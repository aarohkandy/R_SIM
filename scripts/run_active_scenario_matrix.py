#!/usr/bin/env python3
"""Run active-rocket scenario baselines and verify expected ranges."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.active_simulation import ActiveSimulationManager  # noqa: E402


SCENARIO_DIR = ROOT / "examples" / "scenarios"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def get_path(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        current = current[part]
    return current


def run_scenario(manager: ActiveSimulationManager, scenario: Dict[str, Any]) -> Dict[str, Any]:
    result = manager.submit_cfd_simulation(scenario["rocketData"], scenario["simulationConfig"])
    expectations = scenario.get("expectations", {})
    expected_success = expectations.get("success", True)
    require(result.get("success") is expected_success, f"{scenario['id']}: unexpected success state: {result}")

    if not expected_success:
        errors = " ".join(result.get("validation_errors", []))
        for expected in expectations.get("errorsContain", []):
            require(expected in errors, f"{scenario['id']}: missing validation error {expected!r}: {errors}")
        return {"id": scenario["id"], "success": False, "errors": result.get("validation_errors", [])}

    results = result["results"]
    require(results.get("source") == "active_pneumatic_local_dynamics", f"{scenario['id']}: unexpected source")
    require(results.get("is_placeholder") is False, f"{scenario['id']}: placeholder result")
    require(len(results.get("trajectory", [])) > 5, f"{scenario['id']}: trajectory too short")

    for path, bounds in expectations.get("ranges", {}).items():
        value = get_path(results, path)
        low, high = bounds
        require(low <= value <= high, f"{scenario['id']}: {path}={value} outside [{low}, {high}]")

    warnings = " ".join(results.get("warnings", []))
    for expected in expectations.get("warningsContain", []):
        require(expected in warnings, f"{scenario['id']}: missing warning {expected!r}: {warnings}")

    return {
        "id": scenario["id"],
        "success": True,
        "max_altitude": round(results["max_altitude"], 3),
        "max_velocity": round(results["max_velocity"], 3),
        "max_deployment": round(results["active_system"]["max_surface_deployment"], 4),
        "tank_final_kpa": round(results["active_system"]["tank_pressure_final"] / 1000, 2),
        "warnings": results.get("warnings", []),
        "raw_results": results,
    }


def main() -> int:
    manager = ActiveSimulationManager()
    scenario_files = sorted(SCENARIO_DIR.glob("*.json"))
    require(bool(scenario_files), f"No scenarios found in {SCENARIO_DIR}")

    summaries = {}
    scenarios_by_id = {}
    for path in scenario_files:
        scenario = json.loads(path.read_text())
        scenarios_by_id[scenario["id"]] = scenario
        summary = run_scenario(manager, scenario)
        summaries[scenario["id"]] = summary

    for scenario_id, scenario in scenarios_by_id.items():
        expectations = scenario.get("expectations", {})
        relation = expectations.get("lessThanScenario")
        if not relation:
            continue
        baseline_id = relation["scenario"]
        require(baseline_id in summaries, f"{scenario_id}: missing baseline scenario {baseline_id}")
        for path in relation.get("values", []):
            value = get_path(summaries[scenario_id]["raw_results"], path)
            baseline = get_path(summaries[baseline_id]["raw_results"], path)
            require(value < baseline, f"{scenario_id}: expected {path} {value} < {baseline_id} {baseline}")

    public = {
        key: {k: v for k, v in summary.items() if k != "raw_results"}
        for key, summary in summaries.items()
    }
    print(json.dumps(public, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

