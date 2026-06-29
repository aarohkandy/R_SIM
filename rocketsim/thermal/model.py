"""Post-flight lumped-node thermal analysis."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from matplotlib import pyplot as plt
from numpy.typing import NDArray

from rocketsim.thermal.schema import (
    MaterialLimitsDocument,
    ThermalConfig,
    load_material_limits,
    load_thermal_config,
)

plt.switch_backend("Agg")

STEFAN_BOLTZMANN_W_M2_K4 = 5.670374419e-8
KELVIN_OFFSET = 273.15


@dataclass(frozen=True)
class ThermalResult:
    """In-memory thermal analysis products."""

    frame: pd.DataFrame
    summary: dict[str, Any]


@dataclass(frozen=True)
class ThermalArtifacts:
    """Paths to written Phase-10 thermal products."""

    timeseries_csv: Path
    timeseries_parquet: Path
    summary_json: Path
    plot_paths: tuple[Path, ...]

    def manifest_payload(self, output_dir: Path) -> dict[str, Any]:
        """Return relative artifact paths for the run manifest."""

        return {
            "timeseries_csv": self.timeseries_csv.relative_to(output_dir).as_posix(),
            "timeseries_parquet": self.timeseries_parquet.relative_to(output_dir).as_posix(),
            "summary_json": self.summary_json.relative_to(output_dir).as_posix(),
            "plots": [path.relative_to(output_dir).as_posix() for path in self.plot_paths],
        }


@dataclass(frozen=True)
class _ThermalInputs:
    time_s: float
    solid_thrust_fraction: float
    flight_speed_m_s: float
    open_valve_count: float


@dataclass(frozen=True)
class _TelemetryInterpolator:
    times_s: NDArray[np.float64]
    solid_thrust_fraction: NDArray[np.float64]
    flight_speed_m_s: NDArray[np.float64]
    open_valve_count: NDArray[np.float64]

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> _TelemetryInterpolator:
        times = frame["time_s"].to_numpy(dtype=float)
        thrust = np.clip(_series(frame, "solid_thrust_n"), 0.0, None)
        peak_thrust = float(np.max(thrust))
        thrust_fraction = thrust / peak_thrust if peak_thrust > 0.0 else np.zeros(len(frame))
        vx = _series(frame, "velocity_x_m_s")
        vy = _series(frame, "velocity_y_m_s")
        vz = _series(frame, "velocity_z_m_s")
        speed = np.sqrt(vx * vx + vy * vy + vz * vz)
        valve_columns = sorted(
            column
            for column in frame.columns
            if column.startswith("valve_") and column.endswith("_open")
        )
        if valve_columns:
            open_valves = np.zeros(len(frame), dtype=np.float64)
            for column in valve_columns:
                open_valves += _series(frame, column)
        else:
            open_valves = np.zeros(len(frame), dtype=np.float64)
        return cls(
            times_s=times,
            solid_thrust_fraction=np.asarray(thrust_fraction, dtype=np.float64),
            flight_speed_m_s=np.asarray(speed, dtype=np.float64),
            open_valve_count=open_valves,
        )

    def sample(self, t_s: float) -> _ThermalInputs:
        return _ThermalInputs(
            time_s=t_s,
            solid_thrust_fraction=float(np.interp(t_s, self.times_s, self.solid_thrust_fraction)),
            flight_speed_m_s=float(np.interp(t_s, self.times_s, self.flight_speed_m_s)),
            open_valve_count=float(np.interp(t_s, self.times_s, self.open_valve_count)),
        )


def run_configured_thermal_analysis(
    config_path: Path | str,
    telemetry_rows: list[dict[str, Any]] | pd.DataFrame,
    repo_root: Path | str,
) -> ThermalResult:
    """Load thermal inputs from disk and run the logged-flight thermal analysis."""

    root = Path(repo_root)
    config = load_thermal_config(config_path)
    limits_path = root / config.data.material_limits_path
    limits = load_material_limits(limits_path)
    return run_thermal_analysis(config, limits, telemetry_rows)


def run_thermal_analysis(
    config: ThermalConfig,
    material_limits: MaterialLimitsDocument,
    telemetry_rows: list[dict[str, Any]] | pd.DataFrame,
) -> ThermalResult:
    """Integrate the configured thermal network over logged flight telemetry."""

    telemetry = _telemetry_frame(telemetry_rows)
    inputs = _TelemetryInterpolator.from_frame(telemetry)
    node_ids = tuple(node.id for node in config.data.nodes)
    node_index = {node_id: index for index, node_id in enumerate(node_ids)}
    capacities = np.asarray(
        [node.thermal_mass_j_per_k for node in config.data.nodes],
        dtype=np.float64,
    )
    limits_by_node = _limits_by_node(config, material_limits)
    temperatures = np.asarray(
        [node.initial_temperature_deg_c for node in config.data.nodes],
        dtype=np.float64,
    )
    rows = [_thermal_row(config, inputs, limits_by_node, temperatures, telemetry.time_s.iloc[0])]
    current_time = float(telemetry.time_s.iloc[0])

    for target_time in telemetry.time_s.iloc[1:].to_numpy(dtype=float):
        while current_time < target_time:
            dt_s = min(config.data.max_step_s, target_time - current_time)
            temperatures = _rk4_step(
                temperatures,
                current_time,
                dt_s,
                lambda t_s, temps: _temperature_derivative(
                    config=config,
                    node_index=node_index,
                    capacities=capacities,
                    inputs=inputs.sample(t_s),
                    temperatures_deg_c=temps,
                ),
            )
            current_time += dt_s
            if not np.all(np.isfinite(temperatures)):
                msg = "thermal integration produced a non-finite temperature"
                raise ValueError(msg)
        rows.append(_thermal_row(config, inputs, limits_by_node, temperatures, target_time))

    frame = pd.DataFrame(rows)
    return ThermalResult(frame=frame, summary=_thermal_summary(config, frame, limits_by_node))


def write_thermal_artifacts(result: ThermalResult, output_dir: Path) -> ThermalArtifacts:
    """Write Phase-10 thermal timeseries, summary, and plots."""

    thermal_dir = output_dir / "thermal"
    plots_dir = output_dir / "plots"
    thermal_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    timeseries_csv = thermal_dir / "thermal_timeseries.csv"
    timeseries_parquet = thermal_dir / "thermal_timeseries.parquet"
    summary_json = thermal_dir / "thermal_summary.json"
    result.frame.to_csv(timeseries_csv, index=False)
    result.frame.to_parquet(timeseries_parquet, index=False)
    _write_json(summary_json, result.summary)
    plot_paths = (
        plots_dir / "thermal_node_temperatures.png",
        plots_dir / "thermal_margin_to_limits.png",
    )
    _plot_node_temperatures(result.frame).savefig(plot_paths[0], dpi=140, bbox_inches="tight")
    plt.close()
    _plot_temperature_margins(result.frame).savefig(plot_paths[1], dpi=140, bbox_inches="tight")
    plt.close()
    return ThermalArtifacts(
        timeseries_csv=timeseries_csv,
        timeseries_parquet=timeseries_parquet,
        summary_json=summary_json,
        plot_paths=plot_paths,
    )


def _temperature_derivative(
    config: ThermalConfig,
    node_index: dict[str, int],
    capacities: NDArray[np.float64],
    inputs: _ThermalInputs,
    temperatures_deg_c: NDArray[np.float64],
) -> NDArray[np.float64]:
    heat_w = _source_heat_by_node(config, node_index, inputs)
    for conductive_link in config.data.conductive_links:
        left = node_index[conductive_link.from_node]
        right = node_index[conductive_link.to_node]
        q_w = conductive_link.conductance_w_per_k * (
            temperatures_deg_c[right] - temperatures_deg_c[left]
        )
        heat_w[left] += q_w
        heat_w[right] -= q_w
    for radiative_link in config.data.radiative_links:
        source = node_index[radiative_link.from_node]
        target = node_index[radiative_link.to_node]
        source_k = temperatures_deg_c[source] + KELVIN_OFFSET
        target_k = temperatures_deg_c[target] + KELVIN_OFFSET
        q_w = (
            STEFAN_BOLTZMANN_W_M2_K4
            * radiative_link.emissivity
            * radiative_link.view_factor
            * radiative_link.area_m2
            * (source_k**4 - target_k**4)
        )
        heat_w[source] -= q_w
        heat_w[target] += q_w
    for index, node in enumerate(config.data.nodes):
        h_w_m2_k = (
            node.convection_h_base_w_m2_k
            + node.convection_h_per_m_s_w_m2_k * inputs.flight_speed_m_s
        )
        heat_w[index] += (
            h_w_m2_k
            * node.convection_area_m2
            * (config.data.ambient_temperature_deg_c - temperatures_deg_c[index])
        )
    return heat_w / capacities


def _source_heat_by_node(
    config: ThermalConfig,
    node_index: dict[str, int],
    inputs: _ThermalInputs,
) -> NDArray[np.float64]:
    heat_w = np.zeros(len(config.data.nodes), dtype=np.float64)
    for source in config.data.heat_sources:
        if inputs.time_s < source.start_time_s:
            continue
        if source.end_time_s is not None and inputs.time_s > source.end_time_s:
            continue
        if source.kind == "motor_thrust_scaled":
            power_w = source.power_w * inputs.solid_thrust_fraction
        elif source.kind == "valve_power":
            power_w = source.power_w * inputs.open_valve_count
        else:
            power_w = source.power_w
        heat_w[node_index[source.node]] += power_w
    return heat_w


def _rk4_step(
    temperatures_deg_c: NDArray[np.float64],
    time_s: float,
    dt_s: float,
    derivative: Callable[[float, NDArray[np.float64]], NDArray[np.float64]],
) -> NDArray[np.float64]:
    k1 = derivative(time_s, temperatures_deg_c)
    k2 = derivative(time_s + 0.5 * dt_s, temperatures_deg_c + 0.5 * dt_s * k1)
    k3 = derivative(time_s + 0.5 * dt_s, temperatures_deg_c + 0.5 * dt_s * k2)
    k4 = derivative(time_s + dt_s, temperatures_deg_c + dt_s * k3)
    return temperatures_deg_c + dt_s / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def _thermal_row(
    config: ThermalConfig,
    inputs: _TelemetryInterpolator,
    limits_by_node: dict[str, float],
    temperatures_deg_c: NDArray[np.float64],
    time_s: float,
) -> dict[str, float]:
    sample = inputs.sample(time_s)
    node_index = {node.id: index for index, node in enumerate(config.data.nodes)}
    heat_w = _source_heat_by_node(config, node_index, sample)
    row = {
        "time_s": float(time_s),
        "thermal_ambient_temperature_deg_c": config.data.ambient_temperature_deg_c,
        "thermal_flight_speed_m_s": sample.flight_speed_m_s,
    }
    for index, node in enumerate(config.data.nodes):
        temperature = float(temperatures_deg_c[index])
        limit = limits_by_node[node.id]
        row[f"thermal_{node.id}_temperature_deg_c"] = temperature
        row[f"thermal_{node.id}_margin_deg_c"] = limit - temperature
        row[f"thermal_{node.id}_heat_input_w"] = float(heat_w[index])
    return row


def _thermal_summary(
    config: ThermalConfig,
    frame: pd.DataFrame,
    limits_by_node: dict[str, float],
) -> dict[str, Any]:
    nodes: dict[str, Any] = {}
    peak_temperature = -float("inf")
    minimum_margin = float("inf")
    crossed: list[str] = []
    times = frame["time_s"].to_numpy(dtype=float)
    for node in config.data.nodes:
        temp_col = f"thermal_{node.id}_temperature_deg_c"
        margin_col = f"thermal_{node.id}_margin_deg_c"
        temperatures = frame[temp_col].to_numpy(dtype=float)
        margins = frame[margin_col].to_numpy(dtype=float)
        node_peak = float(np.max(temperatures))
        node_min_margin = float(np.min(margins))
        crossing_times = times[margins < 0.0]
        first_crossing: float | None = None
        if len(crossing_times) > 0:
            first_crossing = float(crossing_times[0])
            crossed.append(node.id)
        nodes[node.id] = {
            "material": node.material,
            "material_limit_deg_c": limits_by_node[node.id],
            "peak_temperature_deg_c": node_peak,
            "minimum_margin_deg_c": node_min_margin,
            "first_limit_crossing_time_s": first_crossing,
        }
        peak_temperature = max(peak_temperature, node_peak)
        minimum_margin = min(minimum_margin, node_min_margin)
    return {
        "ambient_temperature_deg_c": config.data.ambient_temperature_deg_c,
        "duration_s": float(times[-1] - times[0]),
        "peak_temperature_deg_c": peak_temperature,
        "minimum_margin_deg_c": minimum_margin,
        "crossed_limit_nodes": crossed,
        "nodes": nodes,
    }


def _limits_by_node(
    config: ThermalConfig,
    material_limits: MaterialLimitsDocument,
) -> dict[str, float]:
    limits: dict[str, float] = {}
    for node in config.data.nodes:
        material = material_limits.materials.get(node.material)
        if material is None:
            msg = f"thermal material {node.material!r} for node {node.id!r} has no limit"
            raise ValueError(msg)
        limits[node.id] = material.heat_deflection_temperature_deg_c
    return limits


def _telemetry_frame(telemetry_rows: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = (
        telemetry_rows.copy()
        if isinstance(telemetry_rows, pd.DataFrame)
        else pd.DataFrame(telemetry_rows)
    )
    if "time_s" not in frame:
        msg = "thermal analysis requires telemetry time_s"
        raise ValueError(msg)
    frame = frame.sort_values("time_s").reset_index(drop=True)
    if len(frame) < 2:
        msg = "thermal analysis requires at least two telemetry rows"
        raise ValueError(msg)
    times = frame["time_s"].to_numpy(dtype=float)
    if not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0.0):
        msg = "thermal telemetry time_s must be finite and strictly increasing"
        raise ValueError(msg)
    return frame


def _series(frame: pd.DataFrame, name: str) -> NDArray[np.float64]:
    if name not in frame:
        return np.zeros(len(frame), dtype=np.float64)
    values: NDArray[np.float64] = np.asarray(
        frame[name].fillna(0.0).to_numpy(dtype=float),
        dtype=np.float64,
    )
    return values


def _plot_node_temperatures(frame: pd.DataFrame) -> Any:
    fig, ax = plt.subplots(figsize=(10, 6))
    time_s = _series(frame, "time_s")
    for column in sorted(frame.columns):
        if column.startswith("thermal_") and column.endswith("_temperature_deg_c"):
            label = column.removeprefix("thermal_").removesuffix("_temperature_deg_c")
            ax.plot(time_s, _series(frame, column), label=label)
    ax.set_xlabel("time s")
    ax.set_ylabel("temperature degC")
    ax.set_title("Thermal Node Temperatures")
    ax.legend(loc="best")
    return fig


def _plot_temperature_margins(frame: pd.DataFrame) -> Any:
    fig, ax = plt.subplots(figsize=(10, 6))
    time_s = _series(frame, "time_s")
    for column in sorted(frame.columns):
        if column.startswith("thermal_") and column.endswith("_margin_deg_c"):
            label = column.removeprefix("thermal_").removesuffix("_margin_deg_c")
            ax.plot(time_s, _series(frame, column), label=label)
    ax.axhline(0.0, color="#111827", lw=1, linestyle="--")
    ax.set_xlabel("time s")
    ax.set_ylabel("margin to material limit degC")
    ax.set_title("Thermal Margins to Material Limits")
    ax.legend(loc="best")
    return fig


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
