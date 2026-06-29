"""Phase-13 convergence and cross-validation studies."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from matplotlib import pyplot as plt

from rocketsim.aero import AeroModel, compare_to_openrocket, load_openrocket_anchors
from rocketsim.dynamics import (
    ForceMoment,
    RigidBodyState,
    analytic_ballistic_position,
    integrate_fixed_step,
)
from rocketsim.sim.flight import SILRunResult, run_native_sil_e2e
from rocketsim.sim.schema import SimConfig, load_sim_config

plt.switch_backend("Agg")

SilRunner = Callable[..., SILRunResult]


@dataclass(frozen=True)
class Phase13Result:
    """Phase-13 artifact paths and summary."""

    output_dir: Path
    convergence_csv: Path
    convergence_json: Path
    cross_validation_json: Path
    openrocket_csv: Path
    plot_path: Path
    manifest_json: Path
    summary: dict[str, Any]


def run_phase13_convergence(
    repo_root: Path | str = Path("."),
    *,
    runner: SilRunner = run_native_sil_e2e,
) -> Phase13Result:
    """Run configured timestep refinement and cross-validation studies."""

    root = Path(repo_root).resolve()
    sim_config = load_sim_config(root / "config" / "sim.yaml")
    phase = sim_config.data.phase13
    if len(phase.integrator_dt_values_s) != len(phase.renode_sync_quantum_values_s):
        msg = "Phase 13 dt and Renode quantum ladders must have the same length"
        raise ValueError(msg)

    output_dir = (root / phase.output_dir).resolve()
    runs_dir = output_dir / "runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(exist_ok=True)

    raw_rows: list[dict[str, Any]] = []
    for dt_s, quantum_s in zip(
        phase.integrator_dt_values_s,
        phase.renode_sync_quantum_values_s,
        strict=True,
    ):
        study_config = sim_config_with_timing(sim_config, dt_s=dt_s, renode_quantum_s=quantum_s)
        run_id = f"phase13_dt{_dt_token(dt_s)}_seed{study_config.data.master_seed}"
        result = runner(
            repo_root=root,
            output_root=runs_dir,
            sim_config_override=study_config,
            run_id_override=run_id,
        )
        raw_rows.append(
            {
                "run_id": run_id,
                "integrator_dt_s": dt_s,
                "renode_sync_quantum_s": quantum_s,
                "touchdown_time_s": result.summary["touchdown_time_s"],
                "touchdown_speed_m_s": result.summary["touchdown_speed_m_s"],
                "touchdown_vertical_speed_m_s": result.summary["touchdown_vertical_speed_m_s"],
                "max_altitude_m": result.summary["max_altitude_m"],
                "co2_remaining_kg": result.summary["co2_remaining_kg"],
                "telemetry_rows": result.summary["telemetry_rows"],
                "telemetry_hash": result.telemetry_hash,
                "state_hash": result.state_hash,
            }
        )

    convergence_rows = convergence_rows_with_deltas(raw_rows)
    convergence_csv = output_dir / "convergence_table.csv"
    convergence_json = output_dir / "convergence_table.json"
    pd.DataFrame(convergence_rows).to_csv(convergence_csv, index=False)
    _write_json(convergence_json, {"rows": convergence_rows})

    cross_validation = cross_validation_report(root, sim_config)
    cross_validation_json = output_dir / "cross_validation.json"
    _write_json(cross_validation_json, cross_validation)
    openrocket_csv = output_dir / "openrocket_anchor_comparison.csv"
    pd.DataFrame(cross_validation["openrocket_anchor"]["rows"]).to_csv(openrocket_csv, index=False)

    plot_path = output_dir / "convergence_metrics.png"
    _write_convergence_plot(convergence_rows, plot_path)

    summary = {
        "convergence_rows": len(convergence_rows),
        "finest_integrator_dt_s": convergence_rows[-1]["integrator_dt_s"],
        "max_touchdown_speed_abs_delta_m_s": max(
            abs(row["touchdown_speed_abs_delta_m_s"]) for row in convergence_rows
        ),
        "max_touchdown_time_abs_delta_s": max(
            abs(row["touchdown_time_abs_delta_s"]) for row in convergence_rows
        ),
        "landing_metric_relative_tolerance": phase.landing_metric_relative_tolerance,
        "landing_metric_absolute_tolerance": phase.landing_metric_absolute_tolerance,
        "rocketpy_available": cross_validation["rocketpy"]["available"],
        "rocketpy_status": cross_validation["rocketpy"]["status"],
        "openrocket_all_within_tolerance": cross_validation["openrocket_anchor"][
            "all_within_tolerance"
        ],
    }
    manifest = {
        "phase": 13,
        "summary": summary,
        "artifacts": {
            "convergence_csv": convergence_csv.relative_to(output_dir).as_posix(),
            "convergence_json": convergence_json.relative_to(output_dir).as_posix(),
            "cross_validation_json": cross_validation_json.relative_to(output_dir).as_posix(),
            "openrocket_csv": openrocket_csv.relative_to(output_dir).as_posix(),
            "plot": plot_path.relative_to(output_dir).as_posix(),
        },
        "notes": (
            "Landing metrics are convergence data, not physics pass/fail verdicts. "
            "RocketPy cross-validation is reported as unavailable when the package is absent."
        ),
    }
    manifest_json = output_dir / "phase13_manifest.json"
    _write_json(manifest_json, manifest)
    return Phase13Result(
        output_dir=output_dir,
        convergence_csv=convergence_csv,
        convergence_json=convergence_json,
        cross_validation_json=cross_validation_json,
        openrocket_csv=openrocket_csv,
        plot_path=plot_path,
        manifest_json=manifest_json,
        summary=summary,
    )


def sim_config_with_timing(
    sim_config: SimConfig,
    *,
    dt_s: float,
    renode_quantum_s: float,
) -> SimConfig:
    """Return a copy of the sim config with refined plant/Renode timing."""

    data = sim_config.data.model_copy(
        update={
            "integrator_dt_s": dt_s,
            "renode_sync_quantum_s": renode_quantum_s,
        }
    )
    return sim_config.model_copy(update={"data": data})


def convergence_rows_with_deltas(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add deltas relative to the finest timestep row."""

    if len(rows) < 2:
        msg = "convergence requires at least two rows"
        raise ValueError(msg)
    ordered = sorted(rows, key=lambda row: float(row["integrator_dt_s"]), reverse=True)
    finest = min(ordered, key=lambda row: float(row["integrator_dt_s"]))
    metrics = (
        "touchdown_time_s",
        "touchdown_speed_m_s",
        "touchdown_vertical_speed_m_s",
        "max_altitude_m",
        "co2_remaining_kg",
    )
    expanded: list[dict[str, Any]] = []
    for row in ordered:
        item = dict(row)
        for metric in metrics:
            delta = float(row[metric]) - float(finest[metric])
            item[f"{metric.removesuffix('_s').removesuffix('_m_s')}_abs_delta"] = delta
            item[f"{metric}_relative_delta"] = _relative_delta(delta, float(finest[metric]))
        item["touchdown_speed_abs_delta_m_s"] = float(row["touchdown_speed_m_s"]) - float(
            finest["touchdown_speed_m_s"]
        )
        item["touchdown_time_abs_delta_s"] = float(row["touchdown_time_s"]) - float(
            finest["touchdown_time_s"]
        )
        expanded.append(item)
    return expanded


def cross_validation_report(root: Path, sim_config: SimConfig) -> dict[str, Any]:
    """Run analytic, OpenRocket-anchor, and RocketPy-availability cross-checks."""

    ballistic = ballistic_cross_validation(sim_config.data.phase13.ballistic_validation_duration_s)
    openrocket = openrocket_cross_validation(root)
    rocketpy_available = importlib.util.find_spec("rocketpy") is not None
    rocketpy = {
        "available": rocketpy_available,
        "status": "available_not_exercised" if rocketpy_available else "unavailable_documented",
        "note": (
            "RocketPy package is available; a passive-ascent comparison can be expanded "
            "with a RocketPy scenario adapter."
            if rocketpy_available
            else "RocketPy is not installed in this environment; analytic ballistic and "
            "OpenRocket-anchor checks are emitted and the missing tool is documented."
        ),
    }
    return {
        "ballistic": ballistic,
        "openrocket_anchor": openrocket,
        "rocketpy": rocketpy,
    }


def ballistic_cross_validation(duration_s: float) -> dict[str, Any]:
    """Cross-check fixed-step no-thrust dynamics against analytic ballistic motion."""

    gravity = 9.80665
    mass = 2.0
    inertia = np.diag([0.04, 0.05, 0.06])
    initial = RigidBodyState(
        time_s=0.0,
        position_m=np.asarray((10.0, -2.0, 100.0), dtype=np.float64),
        velocity_m_s=np.asarray((3.0, -1.0, 40.0), dtype=np.float64),
        attitude_quat=np.asarray((1.0, 0.0, 0.0, 0.0), dtype=np.float64),
        angular_velocity_rad_s=np.zeros(3, dtype=np.float64),
    )

    def provider(_state: RigidBodyState) -> ForceMoment:
        return ForceMoment(
            force_inertial_n=np.asarray((0.0, 0.0, -mass * gravity), dtype=np.float64),
            moment_body_n_m=np.zeros(3, dtype=np.float64),
            mass_kg=mass,
            inertia_tensor_kg_m2=inertia,
        )

    dt_s = 0.001
    final = integrate_fixed_step(initial, duration_s=duration_s, dt_s=dt_s, provider=provider)[-1]
    expected_position = analytic_ballistic_position(
        initial.position_m,
        initial.velocity_m_s,
        duration_s,
        gravity,
    )
    expected_velocity = initial.velocity_m_s + np.asarray((0.0, 0.0, -gravity * duration_s))
    position_error = final.position_m - expected_position
    velocity_error = final.velocity_m_s - expected_velocity
    return {
        "duration_s": duration_s,
        "dt_s": dt_s,
        "position_error_norm_m": float(np.linalg.norm(position_error)),
        "velocity_error_norm_m_s": float(np.linalg.norm(velocity_error)),
        "final_position_m": final.position_m.tolist(),
        "analytic_position_m": expected_position.tolist(),
        "final_velocity_m_s": final.velocity_m_s.tolist(),
        "analytic_velocity_m_s": expected_velocity.tolist(),
    }


def openrocket_cross_validation(root: Path) -> dict[str, Any]:
    """Compare live aero build-up against configured OpenRocket anchor CSV."""

    model = AeroModel.from_config_path(root / "config" / "aero.yaml")
    anchors = load_openrocket_anchors(root / "inputs" / "openrocket" / "frozen_placeholder.csv")
    report = compare_to_openrocket(model, anchors)
    return {
        "all_within_tolerance": report.all_within_tolerance,
        "rows": [
            {
                "mach": row.anchor.mach,
                "leg_angle_deg": row.anchor.leg_angle_deg,
                "cp_anchor_m": row.anchor.cp_axial_m,
                "cp_model_m": row.anchor.cp_axial_m + row.cp_delta_m,
                "cp_delta_m": row.cp_delta_m,
                "cd_anchor": row.anchor.cd,
                "cd_model": row.anchor.cd + row.cd_delta,
                "cd_delta": row.cd_delta,
                "within_tolerance": row.cp_within_tolerance and row.cd_within_tolerance,
            }
            for row in report.rows
        ],
    }


def _write_convergence_plot(rows: Sequence[dict[str, Any]], path: Path) -> None:
    frame = pd.DataFrame(rows)
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    axes[0].plot(frame["integrator_dt_s"], frame["touchdown_speed_m_s"], marker="o")
    axes[0].set_ylabel("touchdown speed m/s")
    axes[1].plot(frame["integrator_dt_s"], frame["touchdown_time_s"], marker="o")
    axes[1].set_ylabel("touchdown time s")
    axes[2].plot(frame["integrator_dt_s"], frame["co2_remaining_kg"], marker="o")
    axes[2].set_ylabel("CO2 remaining kg")
    axes[2].set_xlabel("integrator dt s")
    for axis in axes:
        axis.invert_xaxis()
        axis.grid(True, alpha=0.3)
    fig.suptitle("Phase 13 Timestep Convergence Metrics")
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def _relative_delta(delta: float, reference: float) -> float:
    denominator = max(abs(reference), 1.0e-12)
    return delta / denominator


def _dt_token(dt_s: float) -> str:
    return f"{dt_s:.7f}".rstrip("0").rstrip(".").replace(".", "p")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value
