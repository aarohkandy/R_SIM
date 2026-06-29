from __future__ import annotations

import json
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]
from PIL import Image

from rocketsim.io import telemetry_dataframe, write_full_data_bundle


def minimal_rows() -> list[dict[str, float | bool]]:
    rows: list[dict[str, float | bool]] = []
    for index in range(12):
        t_s = index * 0.1
        rows.append(
            {
                "time_s": t_s,
                "position_x_m": 0.1 * index,
                "position_y_m": 0.0,
                "position_z_m": 1.0 + index,
                "velocity_z_m_s": 10.0 - index,
                "accel_z_m_s2": -9.8,
                "quat_w": 1.0,
                "quat_x": 0.0,
                "quat_y": 0.0,
                "quat_z": 0.0,
                "euler_roll_deg": 0.0,
                "euler_pitch_deg": 0.0,
                "euler_yaw_deg": 0.0,
                "body_rate_x_rad_s": 0.0,
                "body_rate_y_rad_s": 0.0,
                "body_rate_z_rad_s": 0.0,
                "static_margin_calibers": 1.0,
                "mach": 0.05,
                "dynamic_pressure_pa": 10.0 * index,
                "solid_thrust_n": max(0.0, 10.0 - index),
                "coldgas_thrust_n": float(index % 2),
                "nozzle_0_thrust_n": float(index % 2),
                "nozzle_1_thrust_n": 0.0,
                "nozzle_2_thrust_n": 0.0,
                "co2_mass_kg": 0.08,
                "tank_pressure_pa": 5.0e6,
                "valve_0_open": index % 2 == 0,
                "valve_1_open": False,
                "valve_2_open": False,
                "position_z_truth_m": 1.0 + index,
                "baro_altitude_m": 1.0 + index + 0.1,
                "imu_accel_z_m_s2": -9.7,
                "sensor_truth_accel_z_m_s2": -9.8,
                "controller_collective_duty": 0.5,
                "controller_vertical_rate_m_s": -2.0,
            }
        )
    return rows


def test_telemetry_dataframe_has_deterministic_columns() -> None:
    frame = telemetry_dataframe([{"b": 2.0, "a": 1.0}])

    assert list(frame.columns) == ["a", "b"]


def test_write_full_data_bundle_outputs_expected_artifacts(tmp_path: Path) -> None:
    artifacts = write_full_data_bundle(
        output_dir=tmp_path,
        telemetry_rows=minimal_rows(),
        landing_summary={"touchdown": True, "touchdown_speed_m_s": 12.3},
        manifest={"run_id": "unit", "seed": 1, "backend": "sil"},
    )

    assert artifacts.telemetry_csv.exists()
    assert artifacts.telemetry_parquet.exists()
    assert artifacts.landing_summary_json.exists()
    assert artifacts.landing_summary_csv.exists()
    assert artifacts.animation_gif.exists()
    assert artifacts.animation_html.exists()
    assert len(artifacts.plot_paths) == 6
    assert all(path.stat().st_size > 0 for path in artifacts.plot_paths)
    assert pd.read_parquet(artifacts.telemetry_parquet).shape[0] == 12
    with Image.open(artifacts.animation_gif) as image:
        assert image.n_frames >= 2  # type: ignore[attr-defined]
    manifest = json.loads(artifacts.run_manifest_json.read_text(encoding="utf-8"))
    assert manifest["artifacts"]["telemetry_csv"] == "telemetry.csv"
    assert manifest["deferred_artifacts"]["thermal_node_temperature_plots"] == "Phase 10"
