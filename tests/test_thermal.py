from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from rocketsim.thermal import (
    MaterialLimitsDocument,
    ThermalConfig,
    load_material_limits,
    load_thermal_config,
    run_thermal_analysis,
    write_thermal_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]
THERMAL_CONFIG = ROOT / "config" / "thermal.yaml"
MATERIALS = ROOT / "inputs" / "materials_placeholder.yaml"
GOLDEN = ROOT / "tests" / "golden" / "phase10_thermal.json"


def telemetry_rows() -> list[dict[str, float | bool]]:
    rows: list[dict[str, float | bool]] = []
    for index in range(31):
        time_s = index * 0.1
        thrust_n = max(0.0, 18.0 * (1.0 - time_s / 1.6))
        valve_open = 2.0 <= time_s <= 2.6 and index % 2 == 0
        rows.append(
            {
                "time_s": time_s,
                "solid_thrust_n": thrust_n,
                "velocity_x_m_s": 0.0,
                "velocity_y_m_s": 0.0,
                "velocity_z_m_s": 25.0 - 5.0 * time_s,
                "valve_0_open": valve_open,
                "valve_1_open": False,
                "valve_2_open": valve_open,
            }
        )
    return rows


def config_and_limits() -> tuple[ThermalConfig, MaterialLimitsDocument]:
    return load_thermal_config(THERMAL_CONFIG), load_material_limits(MATERIALS)


def test_thermal_config_and_material_limits_load() -> None:
    config, limits = config_and_limits()

    assert len(config.data.nodes) == 6
    assert config.data.nodes[0].id == "motor_casing"
    assert "petg" in limits.materials


def test_thermal_solver_reports_temperatures_and_margins() -> None:
    config, limits = config_and_limits()
    result = run_thermal_analysis(config, limits, telemetry_rows())

    assert "thermal_motor_casing_temperature_deg_c" in result.frame
    assert "thermal_printed_body_margin_deg_c" in result.frame
    assert result.frame["thermal_motor_casing_temperature_deg_c"].iloc[-1] > 20.0
    assert result.summary["nodes"]["printed_body"]["material_limit_deg_c"] == pytest.approx(78.0)
    assert "crossed_limit_nodes" in result.summary


def test_thermal_artifacts_are_written(tmp_path: Path) -> None:
    config, limits = config_and_limits()
    result = run_thermal_analysis(config, limits, telemetry_rows())
    artifacts = write_thermal_artifacts(result, tmp_path)

    assert artifacts.timeseries_csv.exists()
    assert artifacts.timeseries_parquet.exists()
    assert artifacts.summary_json.exists()
    assert len(artifacts.plot_paths) == 2
    assert all(path.stat().st_size > 0 for path in artifacts.plot_paths)
    manifest_payload = artifacts.manifest_payload(tmp_path)
    assert manifest_payload["timeseries_csv"] == "thermal/thermal_timeseries.csv"


def test_thermal_regression_matches_golden() -> None:
    config, limits = config_and_limits()
    result = run_thermal_analysis(config, limits, telemetry_rows())
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert result.summary["peak_temperature_deg_c"] == pytest.approx(
        golden["peak_temperature_deg_c"]
    )
    assert result.summary["minimum_margin_deg_c"] == pytest.approx(golden["minimum_margin_deg_c"])
    for node_id, node_golden in golden["nodes"].items():
        node = result.summary["nodes"][node_id]
        assert node["peak_temperature_deg_c"] == pytest.approx(
            node_golden["peak_temperature_deg_c"]
        )
        assert node["minimum_margin_deg_c"] == pytest.approx(
            node_golden["minimum_margin_deg_c"]
        )


@given(
    temperature_deg_c=st.floats(
        min_value=-20.0,
        max_value=80.0,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_property_no_sources_at_ambient_stays_at_ambient(temperature_deg_c: float) -> None:
    config, limits = config_and_limits()
    payload = config.model_dump(mode="python")
    payload["data"]["ambient_temperature_deg_c"] = temperature_deg_c
    payload["data"]["heat_sources"] = ()
    payload["data"]["conductive_links"] = ()
    payload["data"]["radiative_links"] = ()
    for node in payload["data"]["nodes"]:
        node["initial_temperature_deg_c"] = temperature_deg_c
    no_source = ThermalConfig.model_validate(payload)

    result = run_thermal_analysis(no_source, limits, telemetry_rows())

    for node in no_source.data.nodes:
        column = f"thermal_{node.id}_temperature_deg_c"
        assert result.frame[column].min() == pytest.approx(temperature_deg_c)
        assert result.frame[column].max() == pytest.approx(temperature_deg_c)


def test_missing_material_limit_is_rejected() -> None:
    config, limits = config_and_limits()
    payload = limits.model_dump(mode="python")
    del payload["materials"]["steel"]

    with pytest.raises(ValueError, match="has no limit"):
        run_thermal_analysis(config, type(limits).model_validate(payload), telemetry_rows())


def test_invalid_thermal_config_rejects_bad_link() -> None:
    payload = load_thermal_config(THERMAL_CONFIG).model_dump(mode="python")
    payload["data"]["conductive_links"][0]["to_node"] = "missing"

    with pytest.raises(ValidationError, match="thermal links"):
        ThermalConfig.model_validate(payload)
