from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from rocketsim.structural import (
    StructuralConfig,
    extract_load_cases,
    load_structural_config,
    run_structural_analysis,
    write_structural_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]
STRUCTURAL_CONFIG = ROOT / "config" / "structural.yaml"
GOLDEN = ROOT / "tests" / "golden" / "phase11_structural.json"


def telemetry_rows(touchdown_vertical_speed_m_s: float = -12.0) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for index in range(41):
        time_s = index * 0.1
        descent_fraction = index / 40.0
        velocity_z = 18.0 * (1.0 - 2.0 * descent_fraction)
        if index == 40:
            velocity_z = touchdown_vertical_speed_m_s
        rows.append(
            {
                "time_s": time_s,
                "mass_kg": 0.9,
                "position_z_m": max(0.0, 20.0 * (1.0 - descent_fraction)),
                "velocity_x_m_s": 0.3 * descent_fraction,
                "velocity_y_m_s": -0.1 * descent_fraction,
                "velocity_z_m_s": velocity_z,
                "solid_thrust_n": max(0.0, 20.0 * (1.0 - time_s / 1.8)),
                "dynamic_pressure_pa": 800.0 * descent_fraction * (1.0 - 0.4 * descent_fraction),
            }
        )
    return rows


def test_structural_config_loads() -> None:
    config = load_structural_config(STRUCTURAL_CONFIG)

    assert config.data.solver_preference == "calculix"
    assert config.data.external_solver.allow_internal_fallback is True
    assert len(config.data.members) >= 4


def test_extracts_event_triggered_load_cases() -> None:
    config = load_structural_config(STRUCTURAL_CONFIG)
    load_cases = extract_load_cases(config, telemetry_rows())

    assert [case.id for case in load_cases] == [
        "landing_impact",
        "thrust_transient",
        "max_q",
        "leg_deploy",
    ]
    landing = load_cases[0]
    assert landing.force_n[2] < 0.0
    assert landing.metadata["touchdown_speed_m_s"] > 0.0


def test_internal_fea_fallback_reports_stress_displacement_and_convergence() -> None:
    config = load_structural_config(STRUCTURAL_CONFIG)
    result = run_structural_analysis(config, extract_load_cases(config, telemetry_rows()))

    assert result.summary["solver_used"] == "internal_linear_truss"
    assert result.summary["external_solver_available"] is False
    assert result.summary["load_case_count"] == 4
    assert result.summary["peak_stress_pa"] > 0.0
    assert result.summary["peak_displacement_m"] > 0.0
    assert len(result.mesh_convergence_frame) == 3
    assert result.results_frame["solver_warning"].isna().all()


def test_structural_regression_matches_golden() -> None:
    config = load_structural_config(STRUCTURAL_CONFIG)
    result = run_structural_analysis(config, extract_load_cases(config, telemetry_rows()))
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert result.summary["peak_stress_pa"] == pytest.approx(golden["peak_stress_pa"])
    assert result.summary["peak_displacement_m"] == pytest.approx(
        golden["peak_displacement_m"]
    )
    assert result.summary["peak_stress_case_id"] == golden["peak_stress_case_id"]
    assert result.summary["peak_displacement_case_id"] == golden["peak_displacement_case_id"]
    for row, expected in zip(
        result.mesh_convergence_frame.to_dict(orient="records"),
        golden["mesh_convergence"],
        strict=True,
    ):
        assert row["peak_stress_pa"] == pytest.approx(expected["peak_stress_pa"])
        assert row["peak_displacement_m"] == pytest.approx(expected["peak_displacement_m"])


def test_structural_artifacts_are_written(tmp_path: Path) -> None:
    config = load_structural_config(STRUCTURAL_CONFIG)
    result = run_structural_analysis(config, extract_load_cases(config, telemetry_rows()))
    artifacts = write_structural_artifacts(result, config, tmp_path)

    assert artifacts.load_cases_json.exists()
    assert artifacts.fea_results_parquet.exists()
    assert artifacts.mesh_convergence_csv.exists()
    assert artifacts.calculix_input.exists()
    assert "*Heading" in artifacts.calculix_input.read_text(encoding="utf-8")
    assert len(artifacts.plot_paths) == 3
    assert all(path.stat().st_size > 0 for path in artifacts.plot_paths)


@given(
    touchdown_vertical_speed_m_s=st.floats(
        min_value=-30.0,
        max_value=-1.0,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_property_landing_stress_increases_with_impact_speed(
    touchdown_vertical_speed_m_s: float,
) -> None:
    config = load_structural_config(STRUCTURAL_CONFIG)
    slow = run_structural_analysis(config, extract_load_cases(config, telemetry_rows(-1.0)))
    dispersed = run_structural_analysis(
        config,
        extract_load_cases(config, telemetry_rows(touchdown_vertical_speed_m_s)),
    )

    assert dispersed.summary["cases"]["landing_impact"]["peak_stress_pa"] >= (
        slow.summary["cases"]["landing_impact"]["peak_stress_pa"]
    )


def test_invalid_structural_member_reference_is_rejected() -> None:
    payload = load_structural_config(STRUCTURAL_CONFIG).model_dump(mode="python")
    payload["data"]["members"][0]["to_node"] = "missing"

    with pytest.raises(ValidationError, match="members must reference"):
        StructuralConfig.model_validate(payload)
