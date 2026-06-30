"""Phase-14 Monte Carlo dispersion study."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import yaml
from matplotlib import pyplot as plt

from rocketsim.sim.flight import (
    SILMetricsResult,
    SILRunResult,
    run_native_sil_e2e,
    run_native_sil_metrics,
)
from rocketsim.sim.schema import Phase14Settings, SimConfig, load_sim_config

plt.switch_backend("Agg")

SilResult = SILRunResult | SILMetricsResult
SilRunner = Callable[..., SilResult]
Vector3 = tuple[float, float, float]
NozzleCant = tuple[float, float]

MONTE_CARLO_METRICS = (
    "landing_speed_m_s",
    "touchdown_tilt_deg",
    "touchdown_lateral_error_m",
    "co2_margin_kg",
)


@dataclass(frozen=True)
class MonteCarloScenario:
    """One deterministic Phase-14 input dispersion."""

    index: int
    seed: int
    spawn_key: tuple[int, ...]
    sensor_seed: int
    wind_m_s: Vector3
    mass_scale: float
    cg_shift_m: Vector3
    nozzle_cant_deg: tuple[NozzleCant, ...]
    valve_latency_delta_s: float

    def flat_row(self) -> dict[str, Any]:
        """Return CSV/parquet-friendly scenario parameters."""

        row: dict[str, Any] = {
            "run_index": self.index,
            "scenario_seed": self.seed,
            "spawn_key": ".".join(str(item) for item in self.spawn_key),
            "sensor_seed": self.sensor_seed,
            "wind_x_m_s": self.wind_m_s[0],
            "wind_y_m_s": self.wind_m_s[1],
            "wind_z_m_s": self.wind_m_s[2],
            "mass_scale": self.mass_scale,
            "cg_shift_x_m": self.cg_shift_m[0],
            "cg_shift_y_m": self.cg_shift_m[1],
            "cg_shift_z_m": self.cg_shift_m[2],
            "valve_latency_delta_s": self.valve_latency_delta_s,
        }
        for index, (cant_x_deg, cant_y_deg) in enumerate(self.nozzle_cant_deg):
            row[f"nozzle_{index}_cant_x_deg"] = cant_x_deg
            row[f"nozzle_{index}_cant_y_deg"] = cant_y_deg
        return row


@dataclass(frozen=True)
class Phase14Result:
    """Phase-14 artifact paths and summary."""

    output_dir: Path
    samples_csv: Path
    samples_parquet: Path
    summary_json: Path
    stability_csv: Path
    manifest_json: Path
    histogram_paths: tuple[Path, ...]
    summary: dict[str, Any]


def read_phase14_status(repo_root: Path | str = Path(".")) -> dict[str, Any]:
    """Read the latest Phase-14 Monte Carlo status for CLI/GUI surfaces."""

    root = Path(repo_root).resolve()
    sim_config = load_sim_config(root / "config" / "sim.yaml")
    phase = sim_config.data.phase14
    output_dir = (root / phase.output_dir).resolve()
    summary_path = output_dir / "montecarlo_summary.json"
    manifest_path = output_dir / "phase14_manifest.json"
    samples_path = output_dir / "montecarlo_samples.csv"
    summary = _read_json(summary_path)
    manifest = _read_json(manifest_path)
    histogram_paths = [
        path
        for path in sorted(output_dir.glob("hist_*.png"))
        if path.is_file() and output_dir in path.resolve().parents
    ]
    return {
        "configured": {
            "target_runs": phase.target_runs,
            "batch_size": phase.batch_size,
            "checkpoint_interval_runs": phase.checkpoint_interval_runs,
            "retained_bundle_stride": phase.retained_bundle_stride,
            "max_new_runs_per_invocation": phase.max_new_runs_per_invocation,
            "resume_enabled": phase.resume_enabled,
            "output_dir": phase.output_dir,
        },
        "available": summary_path.exists(),
        "summary": summary,
        "manifest": manifest,
        "samples_csv_exists": samples_path.exists(),
        "histograms": [path.name for path in histogram_paths],
    }


def run_phase14_monte_carlo(
    repo_root: Path | str = Path("."),
    *,
    runner: SilRunner | None = None,
    full_runner: SilRunner = run_native_sil_e2e,
    metrics_runner: SilRunner = run_native_sil_metrics,
    run_count_override: int | None = None,
    max_new_runs_override: int | None = None,
    resume_enabled_override: bool | None = None,
) -> Phase14Result:
    """Run the configured native-SIL Monte Carlo study."""

    root = Path(repo_root).resolve()
    sim_config = load_sim_config(root / "config" / "sim.yaml")
    phase = sim_config.data.phase14
    run_count = _resolve_run_count(phase, run_count_override)
    nozzle_count = nozzle_count_from_config(root)
    scenarios = generate_monte_carlo_scenarios(
        sim_config,
        run_count=run_count,
        nozzle_count=nozzle_count,
    )

    output_dir = (root / phase.output_dir).resolve()
    runs_dir = output_dir / "retained_runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(exist_ok=True)
    samples_csv = output_dir / "montecarlo_samples.csv"
    samples_parquet = output_dir / "montecarlo_samples.parquet"
    summary_json = output_dir / "montecarlo_summary.json"
    stability_csv = output_dir / "stability_table.csv"
    manifest_json = output_dir / "phase14_manifest.json"
    resume_enabled = _resolve_resume_enabled(phase, resume_enabled_override)
    signature = phase14_resume_signature(
        sim_config=sim_config,
        phase=phase,
        nozzle_count=nozzle_count,
    )
    rows_by_index = (
        _load_resume_rows(samples_csv, signature=signature, requested_runs=run_count)
        if resume_enabled
        else {}
    )
    resumed_rows = len(rows_by_index)
    max_new_runs = _resolve_max_new_runs(phase, max_new_runs_override)
    new_rows_completed = 0
    for scenario in scenarios:
        if scenario.index in rows_by_index:
            continue
        if max_new_runs > 0 and new_rows_completed >= max_new_runs:
            break
        run_id = f"phase14_mc{scenario.index:04d}_seed{scenario.sensor_seed}"
        retain_bundle = _retain_bundle(phase, scenario.index)
        temp_prefix = f"rocketsim_phase14_case_{scenario.index:04d}_"
        with tempfile.TemporaryDirectory(prefix=temp_prefix) as tmp:
            scenario_root = Path(tmp) / "scenario"
            apply_scenario_to_repo(root, scenario, scenario_root)
            scenario_output = runs_dir if retain_bundle else Path(tmp) / "discarded_outputs"
            selected_runner = runner or (full_runner if retain_bundle else metrics_runner)
            result = selected_runner(
                repo_root=scenario_root,
                output_root=scenario_output,
                run_id_override=run_id,
            )
        row = scenario.flat_row()
        row.update(_result_metric_row(result, run_id=run_id, retained_bundle=retain_bundle))
        row["phase14_signature"] = signature
        rows_by_index[scenario.index] = row
        new_rows_completed += 1
        if len(rows_by_index) % phase.checkpoint_interval_runs == 0:
            _write_phase14_artifacts(
                output_dir=output_dir,
                samples_csv=samples_csv,
                samples_parquet=samples_parquet,
                summary_json=summary_json,
                stability_csv=stability_csv,
                manifest_json=manifest_json,
                rows=_ordered_rows(rows_by_index),
                phase=phase,
                sim_config=sim_config,
                requested_runs=run_count,
                resumed_rows=resumed_rows,
                new_rows_completed=new_rows_completed,
                max_new_runs=max_new_runs,
                resume_enabled=resume_enabled,
                signature=signature,
                checkpoint=True,
            )

    artifacts = _write_phase14_artifacts(
        output_dir=output_dir,
        samples_csv=samples_csv,
        samples_parquet=samples_parquet,
        summary_json=summary_json,
        stability_csv=stability_csv,
        manifest_json=manifest_json,
        rows=_ordered_rows(rows_by_index),
        phase=phase,
        sim_config=sim_config,
        requested_runs=run_count,
        resumed_rows=resumed_rows,
        new_rows_completed=new_rows_completed,
        max_new_runs=max_new_runs,
        resume_enabled=resume_enabled,
        signature=signature,
        checkpoint=False,
    )
    return Phase14Result(
        output_dir=output_dir,
        samples_csv=samples_csv,
        samples_parquet=samples_parquet,
        summary_json=summary_json,
        stability_csv=stability_csv,
        manifest_json=manifest_json,
        histogram_paths=artifacts["histogram_paths"],
        summary=artifacts["summary"],
    )


def phase14_resume_signature(
    *,
    sim_config: SimConfig,
    phase: Phase14Settings,
    nozzle_count: int,
) -> str:
    """Hash the scenario-generation inputs that make completed rows resumable."""

    payload = {
        "master_seed": sim_config.data.master_seed,
        "nozzle_count": nozzle_count,
        "retained_bundle_stride": phase.retained_bundle_stride,
        "dispersions": phase.dispersions.model_dump(mode="json"),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_phase14_artifacts(
    *,
    output_dir: Path,
    samples_csv: Path,
    samples_parquet: Path,
    summary_json: Path,
    stability_csv: Path,
    manifest_json: Path,
    rows: Sequence[dict[str, Any]],
    phase: Phase14Settings,
    sim_config: SimConfig,
    requested_runs: int,
    resumed_rows: int,
    new_rows_completed: int,
    max_new_runs: int,
    resume_enabled: bool,
    signature: str,
    checkpoint: bool,
) -> dict[str, Any]:
    if not rows:
        msg = "Phase 14 cannot write artifacts without at least one completed run"
        raise ValueError(msg)
    frame = _samples_frame(rows)
    frame.to_csv(samples_csv, index=False)
    frame.to_parquet(samples_parquet, index=False)

    histogram_paths = write_histograms(frame, output_dir, phase)
    distributions = distribution_summary(frame, MONTE_CARLO_METRICS, phase.percentiles)
    stability = stability_report(frame, phase)
    pd.DataFrame(stability["rows"]).to_csv(stability_csv, index=False)
    runs_completed = len(frame)
    gate_complete = bool(
        runs_completed >= phase.target_runs
        and stability["status"] == "stable"
        and stability["stable"]
    )
    retained_bundles = int(frame["retained_bundle"].astype(bool).sum())
    summary = {
        "runs_completed": runs_completed,
        "requested_runs": requested_runs,
        "target_runs": phase.target_runs,
        "batch_size": phase.batch_size,
        "gate_complete": gate_complete,
        "checkpoint": checkpoint,
        "resume_enabled": resume_enabled,
        "resumed_rows": resumed_rows,
        "new_rows_completed": new_rows_completed,
        "max_new_runs_per_invocation": max_new_runs,
        "invocation_limited": max_new_runs > 0 and new_rows_completed >= max_new_runs,
        "phase14_signature": signature,
        "checkpoint_interval_runs": phase.checkpoint_interval_runs,
        "stability": stability,
        "distributions": distributions,
        "retained_bundle_stride": phase.retained_bundle_stride,
        "retained_bundles": retained_bundles,
        "notes": (
            "Physics outcomes are reported as distributions only. The Phase-14 gate is "
            "complete only when the configured large-N target and percentile stability "
            "criteria are both satisfied."
        ),
    }
    _write_json(summary_json, summary)

    manifest = {
        "phase": 14,
        "summary": summary,
        "artifacts": {
            "samples_csv": samples_csv.relative_to(output_dir).as_posix(),
            "samples_parquet": samples_parquet.relative_to(output_dir).as_posix(),
            "summary_json": summary_json.relative_to(output_dir).as_posix(),
            "stability_csv": stability_csv.relative_to(output_dir).as_posix(),
            "histograms": [path.relative_to(output_dir).as_posix() for path in histogram_paths],
        },
        "scenario_generation": {
            "master_seed": sim_config.data.master_seed,
            "seed_strategy": "numpy.random.SeedSequence.spawn",
            "resume_signature": signature,
            "dispersion_fields": [
                "wind",
                "mass_scale",
                "cg_shift",
                "nozzle_cant",
                "valve_latency",
                "sensor_seed",
            ],
        },
    }
    _write_json(manifest_json, manifest)
    return {"histogram_paths": histogram_paths, "summary": summary}


def _load_resume_rows(
    samples_csv: Path,
    *,
    signature: str,
    requested_runs: int,
) -> dict[int, dict[str, Any]]:
    if not samples_csv.exists():
        return {}
    frame = pd.read_csv(
        samples_csv,
        dtype={
            "spawn_key": "string",
            "run_id": "string",
            "artifact_mode": "string",
            "telemetry_hash": "string",
            "state_hash": "string",
            "phase14_signature": "string",
        },
    )
    required_columns = {"run_index", "phase14_signature"}
    if not required_columns.issubset(frame.columns):
        return {}
    resumable = frame[
        (frame["phase14_signature"] == signature) & (frame["run_index"] < requested_runs)
    ].copy()
    if resumable.empty:
        return {}
    resumable = resumable.drop_duplicates(subset=["run_index"], keep="first")
    rows: dict[int, dict[str, Any]] = {}
    for row in resumable.to_dict(orient="records"):
        if _row_has_metric_payload(row):
            rows[int(row["run_index"])] = cast(dict[str, Any], row)
    return dict(sorted(rows.items()))


def _row_has_metric_payload(row: dict[str, Any]) -> bool:
    required = {
        "run_id",
        "retained_bundle",
        "artifact_mode",
        "touchdown",
        "landing_speed_m_s",
        "touchdown_tilt_deg",
        "touchdown_lateral_error_m",
        "co2_margin_kg",
        "telemetry_hash",
        "state_hash",
    }
    return required.issubset(row)


def _samples_frame(rows: Sequence[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    string_columns = (
        "spawn_key",
        "run_id",
        "artifact_mode",
        "telemetry_hash",
        "state_hash",
        "phase14_signature",
    )
    for column in string_columns:
        if column in frame.columns:
            frame[column] = frame[column].astype("string").fillna("")
    for column in ("retained_bundle", "touchdown"):
        if column in frame.columns:
            frame[column] = frame[column].astype(bool)
    return frame


def _ordered_rows(rows_by_index: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    return [rows_by_index[index] for index in sorted(rows_by_index)]


def generate_monte_carlo_scenarios(
    sim_config: SimConfig,
    *,
    run_count: int,
    nozzle_count: int,
) -> tuple[MonteCarloScenario, ...]:
    """Generate deterministic Phase-14 scenarios using spawned child streams."""

    if run_count <= 0:
        msg = "run_count must be positive"
        raise ValueError(msg)
    if nozzle_count <= 0:
        msg = "nozzle_count must be positive"
        raise ValueError(msg)
    phase = sim_config.data.phase14
    dispersions = phase.dispersions
    parent = np.random.SeedSequence(sim_config.data.master_seed)
    children = parent.spawn(run_count)
    scenarios: list[MonteCarloScenario] = []
    cg_stds = np.asarray(dispersions.cg_shift_std_m, dtype=np.float64)
    for index, child in enumerate(children):
        seed_words = child.generate_state(2, dtype=np.uint32)
        rng = np.random.default_rng(child)
        wind_xy = rng.normal(0.0, dispersions.wind_xy_std_m_s, size=2)
        cg_shift = rng.normal(0.0, cg_stds, size=3)
        nozzle_cants = tuple(
            (
                float(rng.normal(0.0, dispersions.nozzle_cant_std_deg)),
                float(rng.normal(0.0, dispersions.nozzle_cant_std_deg)),
            )
            for _ in range(nozzle_count)
        )
        sensor_seed = (
            int(seed_words[1])
            if dispersions.sensor_seed_enabled
            else sim_config.data.master_seed
        )
        scenarios.append(
            MonteCarloScenario(
                index=index,
                seed=int(seed_words[0]),
                spawn_key=tuple(int(item) for item in child.spawn_key),
                sensor_seed=sensor_seed,
                wind_m_s=(float(wind_xy[0]), float(wind_xy[1]), 0.0),
                mass_scale=max(
                    0.01,
                    1.0 + float(rng.normal(0.0, dispersions.mass_scale_std_fraction)),
                ),
                cg_shift_m=(float(cg_shift[0]), float(cg_shift[1]), float(cg_shift[2])),
                nozzle_cant_deg=nozzle_cants,
                valve_latency_delta_s=float(rng.normal(0.0, dispersions.valve_latency_std_s)),
            )
        )
    return tuple(scenarios)


def apply_scenario_to_repo(
    source_root: Path | str,
    scenario: MonteCarloScenario,
    target_root: Path | str,
) -> Path:
    """Copy the runnable repo inputs and apply one scenario's dispersions."""

    source = Path(source_root).resolve()
    target = Path(target_root).resolve()
    target.mkdir(parents=True, exist_ok=True)
    for directory_name in ("config", "inputs"):
        destination = target / directory_name
        if destination.exists():
            msg = f"target scenario directory already contains {directory_name}"
            raise FileExistsError(msg)
        shutil.copytree(source / directory_name, destination)

    _apply_wind(target / "config" / "environment.yaml", scenario)
    _apply_bom_mass_and_cg(target / "inputs" / "bom_placeholder.yaml", scenario)
    _apply_nozzle_cant(target / "config" / "coldgas.yaml", scenario)
    _apply_valve_latency(target / "config" / "actuation.yaml", scenario)
    _apply_sensor_seed(target / "config" / "sim.yaml", scenario)
    return target


def nozzle_count_from_config(repo_root: Path | str) -> int:
    """Read the configured nozzle count without importing the propulsion model."""

    raw = _load_yaml_mapping(Path(repo_root) / "config" / "coldgas.yaml")
    data = _mapping(raw, "data")
    nozzles = _mapping(data, "nozzles")
    items = _list(nozzles, "items")
    return len(items)


def distribution_summary(
    frame: pd.DataFrame,
    metrics: Sequence[str],
    percentiles: Sequence[float],
) -> dict[str, Any]:
    """Summarize metric distributions without judging the flight outcomes."""

    distributions: dict[str, Any] = {}
    for metric in metrics:
        values = frame[metric].to_numpy(dtype=np.float64)
        distributions[metric] = {
            "count": int(values.size),
            "mean": float(np.mean(values)),
            "std": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "percentiles": {
                f"p{percentile:g}": float(np.percentile(values, percentile))
                for percentile in percentiles
            },
        }
    return distributions


def stability_report(frame: pd.DataFrame, phase: Phase14Settings) -> dict[str, Any]:
    """Compare recent cumulative percentile estimates for statistical stability."""

    completed = len(frame)
    full_batches = completed // phase.batch_size
    rows: list[dict[str, Any]] = []
    for batch_index in range(1, full_batches + 1):
        subset = frame.iloc[: batch_index * phase.batch_size]
        row: dict[str, Any] = {"batch": batch_index, "sample_count": len(subset)}
        for metric in MONTE_CARLO_METRICS:
            values = subset[metric].to_numpy(dtype=np.float64)
            for percentile in phase.percentiles:
                row[f"{metric}_p{percentile:g}"] = float(np.percentile(values, percentile))
        rows.append(row)

    minimum_batches = phase.stability_window_batches + 1
    if full_batches < minimum_batches:
        return {
            "status": "insufficient_batches",
            "stable": False,
            "full_batches": full_batches,
            "required_batches_for_check": minimum_batches,
            "max_relative_change": None,
            "rows": rows,
        }

    final_row = rows[-1]
    comparison_rows = rows[-phase.stability_window_batches - 1 : -1]
    max_relative_change = 0.0
    for prior_row in comparison_rows:
        for metric in MONTE_CARLO_METRICS:
            for percentile in phase.percentiles:
                key = f"{metric}_p{percentile:g}"
                reference = float(final_row[key])
                delta = abs(float(prior_row[key]) - reference)
                relative = delta / max(abs(reference), 1.0e-12)
                max_relative_change = max(max_relative_change, relative)
    stable = max_relative_change <= phase.percentile_stability_tolerance
    return {
        "status": "stable" if stable else "not_stable",
        "stable": stable,
        "full_batches": full_batches,
        "required_batches_for_check": minimum_batches,
        "max_relative_change": max_relative_change,
        "rows": rows,
    }


def write_histograms(
    frame: pd.DataFrame,
    output_dir: Path,
    phase: Phase14Settings,
) -> tuple[Path, ...]:
    """Write one histogram per reported Monte Carlo metric."""

    paths: list[Path] = []
    labels = {
        "landing_speed_m_s": "Landing speed (m/s)",
        "touchdown_tilt_deg": "Touchdown tilt (deg)",
        "touchdown_lateral_error_m": "Lateral error (m)",
        "co2_margin_kg": "CO2 remaining (kg)",
    }
    for metric in MONTE_CARLO_METRICS:
        path = output_dir / f"hist_{metric}.png"
        fig, axis = plt.subplots(figsize=(7, 4))
        axis.hist(frame[metric].to_numpy(dtype=np.float64), bins=phase.histogram_bins)
        axis.set_xlabel(labels[metric])
        axis.set_ylabel("count")
        axis.grid(True, alpha=0.25)
        axis.set_title(f"Phase 14 {labels[metric]}")
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)
    return tuple(paths)


def _resolve_run_count(phase: Phase14Settings, override: int | None) -> int:
    if override is not None:
        if override <= 0:
            msg = "run_count_override must be positive"
            raise ValueError(msg)
        return override
    env_value = os.environ.get("ROCKETSIM_MC_RUNS")
    if env_value is None:
        return phase.target_runs
    try:
        run_count = int(env_value)
    except ValueError as exc:
        msg = "ROCKETSIM_MC_RUNS must be a positive integer"
        raise ValueError(msg) from exc
    if run_count <= 0:
        msg = "ROCKETSIM_MC_RUNS must be positive"
        raise ValueError(msg)
    return run_count


def _resolve_resume_enabled(phase: Phase14Settings, override: bool | None) -> bool:
    if override is not None:
        return override
    env_value = os.environ.get("ROCKETSIM_MC_RESUME")
    if env_value is None:
        return phase.resume_enabled
    normalized = env_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    msg = "ROCKETSIM_MC_RESUME must be one of 1/0, true/false, yes/no, or on/off"
    raise ValueError(msg)


def _resolve_max_new_runs(phase: Phase14Settings, override: int | None) -> int:
    if override is not None:
        if override < 0:
            msg = "max_new_runs_override must be non-negative"
            raise ValueError(msg)
        return override
    env_value = os.environ.get("ROCKETSIM_MC_MAX_NEW_RUNS")
    if env_value is None:
        return phase.max_new_runs_per_invocation
    try:
        max_new_runs = int(env_value)
    except ValueError as exc:
        msg = "ROCKETSIM_MC_MAX_NEW_RUNS must be a non-negative integer"
        raise ValueError(msg) from exc
    if max_new_runs < 0:
        msg = "ROCKETSIM_MC_MAX_NEW_RUNS must be non-negative"
        raise ValueError(msg)
    return max_new_runs


def _retain_bundle(phase: Phase14Settings, run_index: int) -> bool:
    return phase.retained_bundle_stride > 0 and run_index % phase.retained_bundle_stride == 0


def _result_metric_row(
    result: SilResult,
    *,
    run_id: str,
    retained_bundle: bool,
) -> dict[str, Any]:
    summary = result.summary
    return {
        "run_id": run_id,
        "retained_bundle": retained_bundle,
        "artifact_mode": "full_bundle" if retained_bundle else "metrics_only",
        "touchdown": bool(summary["touchdown"]),
        "touchdown_time_s": float(summary["touchdown_time_s"]),
        "landing_speed_m_s": float(summary["touchdown_speed_m_s"]),
        "touchdown_vertical_speed_m_s": float(summary["touchdown_vertical_speed_m_s"]),
        "touchdown_tilt_deg": float(summary["touchdown_tilt_deg"]),
        "touchdown_lateral_error_m": float(summary["touchdown_lateral_error_m"]),
        "co2_margin_kg": float(summary["co2_remaining_kg"]),
        "max_altitude_m": float(summary["max_altitude_m"]),
        "max_dynamic_pressure_pa": float(summary["max_dynamic_pressure_pa"]),
        "telemetry_rows": int(summary["telemetry_rows"]),
        "telemetry_hash": result.telemetry_hash,
        "state_hash": result.state_hash,
    }


def _apply_wind(path: Path, scenario: MonteCarloScenario) -> None:
    raw = _load_yaml_mapping(path)
    wind = _mapping(_mapping(raw, "data"), "wind")
    wind["enabled"] = True
    wind["steady_m_s"] = list(scenario.wind_m_s)
    _write_yaml_mapping(path, raw)


def _apply_bom_mass_and_cg(path: Path, scenario: MonteCarloScenario) -> None:
    raw = _load_yaml_mapping(path)
    parts = _list(raw, "parts")
    for part_item in parts:
        part = _ensure_mapping(part_item)
        mass = part.get("mass_kg")
        if isinstance(mass, int | float):
            part["mass_kg"] = max(0.0, float(mass) * scenario.mass_scale)
        if "position_m" in part:
            part["position_m"] = _shift_vector(part["position_m"], scenario.cg_shift_m)
        position_profile = part.get("position_profile")
        if isinstance(position_profile, dict):
            for point_item in _list(position_profile, "points"):
                point = _ensure_mapping(point_item)
                if "position_m" in point:
                    point["position_m"] = _shift_vector(point["position_m"], scenario.cg_shift_m)
        deployable_leg = part.get("deployable_leg")
        if isinstance(deployable_leg, dict) and "hinge_position_m" in deployable_leg:
            deployable_leg["hinge_position_m"] = _shift_vector(
                deployable_leg["hinge_position_m"],
                scenario.cg_shift_m,
            )
    _write_yaml_mapping(path, raw)


def _apply_nozzle_cant(path: Path, scenario: MonteCarloScenario) -> None:
    raw = _load_yaml_mapping(path)
    items = _list(_mapping(_mapping(raw, "data"), "nozzles"), "items")
    for index, item in enumerate(items):
        if index >= len(scenario.nozzle_cant_deg):
            break
        nozzle = _ensure_mapping(item)
        nozzle["axis_unit"] = list(_axis_from_cant(scenario.nozzle_cant_deg[index]))
    _write_yaml_mapping(path, raw)


def _apply_valve_latency(path: Path, scenario: MonteCarloScenario) -> None:
    raw = _load_yaml_mapping(path)
    data = _mapping(raw, "data")
    for key in ("open_latency_s", "close_latency_s"):
        value = data.get(key)
        if isinstance(value, int | float):
            data[key] = max(0.0, float(value) + scenario.valve_latency_delta_s)
    _write_yaml_mapping(path, raw)


def _apply_sensor_seed(path: Path, scenario: MonteCarloScenario) -> None:
    raw = _load_yaml_mapping(path)
    _mapping(raw, "data")["master_seed"] = scenario.sensor_seed
    _write_yaml_mapping(path, raw)


def _axis_from_cant(cant_deg: NozzleCant) -> Vector3:
    x_deg, y_deg = cant_deg
    axis = np.asarray(
        (
            np.tan(np.radians(x_deg)),
            np.tan(np.radians(y_deg)),
            1.0,
        ),
        dtype=np.float64,
    )
    axis /= max(float(np.linalg.norm(axis)), 1.0e-12)
    return (float(axis[0]), float(axis[1]), float(axis[2]))


def _shift_vector(value: Any, delta: Vector3) -> list[float]:
    if not isinstance(value, list | tuple) or len(value) != 3:
        msg = "position vectors must contain three values"
        raise TypeError(msg)
    return [
        float(component) + float(offset)
        for component, offset in zip(value, delta, strict=True)
    ]


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{path} must contain a YAML mapping"
        raise TypeError(msg)
    return cast(dict[str, Any], raw)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _write_yaml_mapping(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        msg = f"{key} must be a YAML mapping"
        raise TypeError(msg)
    return cast(dict[str, Any], value)


def _list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        msg = f"{key} must be a YAML list"
        raise TypeError(msg)
    return value


def _ensure_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        msg = "expected YAML list item to be a mapping"
        raise TypeError(msg)
    return cast(dict[str, Any], value)


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
