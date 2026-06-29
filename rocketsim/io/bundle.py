"""Flight data bundle, plotting, and animation writers."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from matplotlib import animation
from matplotlib import pyplot as plt

plt.switch_backend("Agg")


@dataclass(frozen=True)
class DataBundleArtifacts:
    """Paths to Phase-9 bundle products."""

    telemetry_csv: Path
    telemetry_parquet: Path
    landing_summary_json: Path
    landing_summary_csv: Path
    run_manifest_json: Path
    plot_paths: tuple[Path, ...]
    animation_gif: Path
    animation_html: Path
    animation_mp4: Path | None

    def manifest_payload(self, output_dir: Path) -> dict[str, Any]:
        """Return relative artifact paths for the run manifest."""

        payload: dict[str, Any] = {
            "telemetry_csv": self.telemetry_csv.relative_to(output_dir).as_posix(),
            "telemetry_parquet": self.telemetry_parquet.relative_to(output_dir).as_posix(),
            "landing_summary_json": self.landing_summary_json.relative_to(output_dir).as_posix(),
            "landing_summary_csv": self.landing_summary_csv.relative_to(output_dir).as_posix(),
            "plots": [path.relative_to(output_dir).as_posix() for path in self.plot_paths],
            "animation_gif": self.animation_gif.relative_to(output_dir).as_posix(),
            "animation_html": self.animation_html.relative_to(output_dir).as_posix(),
        }
        if self.animation_mp4 is not None:
            payload["animation_mp4"] = self.animation_mp4.relative_to(output_dir).as_posix()
        return payload


def write_full_data_bundle(
    output_dir: Path,
    telemetry_rows: list[dict[str, Any]],
    landing_summary: dict[str, Any],
    manifest: dict[str, Any],
    extra_artifacts: dict[str, Any] | None = None,
    extra_deferred_artifacts: dict[str, str] | None = None,
) -> DataBundleArtifacts:
    """Write Phase-9 telemetry, plots, summary, manifest, and animation artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = output_dir / "plots"
    plots_dir.mkdir(exist_ok=True)

    frame = telemetry_dataframe(telemetry_rows)
    telemetry_csv = output_dir / "telemetry.csv"
    telemetry_parquet = output_dir / "telemetry.parquet"
    frame.to_csv(telemetry_csv, index=False)
    frame.to_parquet(telemetry_parquet, index=False)

    landing_summary_json = output_dir / "landing_summary.json"
    landing_summary_csv = output_dir / "landing_summary.csv"
    write_json(landing_summary_json, landing_summary)
    pd.DataFrame([landing_summary]).to_csv(landing_summary_csv, index=False)

    plot_paths = write_plots(frame, plots_dir)
    animation_gif, animation_html, animation_mp4 = write_animation_artifacts(frame, output_dir)

    artifacts = DataBundleArtifacts(
        telemetry_csv=telemetry_csv,
        telemetry_parquet=telemetry_parquet,
        landing_summary_json=landing_summary_json,
        landing_summary_csv=landing_summary_csv,
        run_manifest_json=output_dir / "run_manifest.json",
        plot_paths=plot_paths,
        animation_gif=animation_gif,
        animation_html=animation_html,
        animation_mp4=animation_mp4,
    )
    artifact_payload = artifacts.manifest_payload(output_dir)
    if extra_artifacts:
        artifact_payload.update(extra_artifacts)
    deferred_artifacts = {
        "fea_stress_summary_plots": "Phase 11",
    }
    if not extra_artifacts or "thermal" not in extra_artifacts:
        deferred_artifacts["thermal_node_temperature_plots"] = "Phase 10"
    if animation_mp4 is None:
        deferred_artifacts["animation_mp4"] = "ffmpeg not installed"
    if extra_deferred_artifacts:
        deferred_artifacts.update(extra_deferred_artifacts)

    manifest = {
        **manifest,
        "artifacts": artifact_payload,
        "deferred_artifacts": deferred_artifacts,
    }
    write_json(artifacts.run_manifest_json, manifest)
    return artifacts


def telemetry_dataframe(telemetry_rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert telemetry rows to a deterministic dataframe."""

    frame = pd.DataFrame(telemetry_rows)
    if frame.empty:
        return frame
    columns = sorted(frame.columns)
    return frame[columns]


def write_plots(frame: pd.DataFrame, plots_dir: Path) -> tuple[Path, ...]:
    """Write the Phase-9 plot suite."""

    plot_specs = (
        ("altitude_velocity_accel.png", _plot_altitude_velocity_accel),
        ("attitude_rates.png", _plot_attitude_rates),
        ("stability_aero.png", _plot_stability_aero),
        ("thrust_co2.png", _plot_thrust_co2),
        ("valve_activity.png", _plot_valve_activity),
        ("sensors_controller.png", _plot_sensors_controller),
    )
    paths: list[Path] = []
    for filename, plotter in plot_specs:
        path = plots_dir / filename
        fig = plotter(frame)
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)
    return tuple(paths)


def write_animation_artifacts(
    frame: pd.DataFrame,
    output_dir: Path,
) -> tuple[Path, Path, Path | None]:
    """Write GIF + interactive HTML animation, and MP4 when ffmpeg is available."""

    gif_path = output_dir / "flight_animation.gif"
    html_path = output_dir / "flight_animation.html"
    mp4_path = output_dir / "flight_animation.mp4" if shutil.which("ffmpeg") else None
    _write_animation_gif(frame, gif_path, mp4_path)
    _write_animation_html(frame, html_path)
    return gif_path, html_path, mp4_path if mp4_path is not None and mp4_path.exists() else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic JSON."""

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plot_altitude_velocity_accel(frame: pd.DataFrame) -> Any:
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    t = _series(frame, "time_s")
    axes[0].plot(t, _series(frame, "position_z_m"), color="#1f77b4")
    axes[0].set_ylabel("altitude m")
    axes[1].plot(t, _series(frame, "velocity_z_m_s"), color="#d62728")
    axes[1].set_ylabel("vertical speed m/s")
    axes[2].plot(t, _series(frame, "accel_z_m_s2"), color="#2ca02c")
    axes[2].set_ylabel("accel z m/s^2")
    axes[2].set_xlabel("time s")
    fig.suptitle("Altitude, Velocity, Acceleration")
    return fig


def _plot_attitude_rates(frame: pd.DataFrame) -> Any:
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    t = _series(frame, "time_s")
    for name in ("euler_roll_deg", "euler_pitch_deg", "euler_yaw_deg"):
        axes[0].plot(t, _series(frame, name), label=name.replace("euler_", "").replace("_deg", ""))
    axes[0].set_ylabel("Euler angle deg")
    axes[0].legend(loc="best")
    for name in ("body_rate_x_rad_s", "body_rate_y_rad_s", "body_rate_z_rad_s"):
        label = name.replace("body_rate_", "").replace("_rad_s", "")
        axes[1].plot(t, _series(frame, name), label=label)
    axes[1].set_ylabel("body rate rad/s")
    axes[1].set_xlabel("time s")
    axes[1].legend(loc="best")
    fig.suptitle("Attitude and Body Rates")
    return fig


def _plot_stability_aero(frame: pd.DataFrame) -> Any:
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    t = _series(frame, "time_s")
    axes[0].plot(t, _series(frame, "static_margin_calibers"), color="#9467bd")
    axes[0].set_ylabel("static margin calibers")
    axes[1].plot(t, _series(frame, "mach"), color="#8c564b")
    axes[1].set_ylabel("Mach")
    axes[2].plot(t, _series(frame, "dynamic_pressure_pa"), color="#17becf")
    axes[2].set_ylabel("q Pa")
    axes[2].set_xlabel("time s")
    fig.suptitle("Stability and Aerodynamic State")
    return fig


def _plot_thrust_co2(frame: pd.DataFrame) -> Any:
    fig, axes = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    t = _series(frame, "time_s")
    axes[0].plot(t, _series(frame, "solid_thrust_n"), label="solid")
    axes[0].plot(t, _series(frame, "coldgas_thrust_n"), label="cold gas")
    for index in range(3):
        axes[0].plot(t, _series(frame, f"nozzle_{index}_thrust_n"), label=f"nozzle {index}")
    axes[0].set_ylabel("thrust N")
    axes[0].legend(loc="best")
    axes[1].plot(t, _series(frame, "co2_mass_kg"), color="#2ca02c")
    axes[1].set_ylabel("CO2 kg")
    axes[2].plot(t, _series(frame, "tank_pressure_pa"), color="#d62728")
    axes[2].set_ylabel("tank pressure Pa")
    axes[2].set_xlabel("time s")
    fig.suptitle("Thrust and CO2 State")
    return fig


def _plot_valve_activity(frame: pd.DataFrame) -> Any:
    fig, ax = plt.subplots(figsize=(9, 3))
    t = _series(frame, "time_s")
    valves = np.vstack([_series(frame, f"valve_{index}_open") for index in range(3)])
    ax.imshow(
        valves,
        aspect="auto",
        interpolation="nearest",
        extent=(float(t.min()), float(t.max()), -0.5, 2.5),
        cmap="Greys",
        origin="lower",
    )
    ax.set_yticks([0, 1, 2], labels=["valve 0", "valve 1", "valve 2"])
    ax.set_xlabel("time s")
    ax.set_title("Valve Activity Raster")
    return fig


def _plot_sensors_controller(frame: pd.DataFrame) -> Any:
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    t = _series(frame, "time_s")
    axes[0].plot(t, _series(frame, "position_z_m"), label="truth altitude")
    axes[0].plot(t, _series(frame, "baro_altitude_m"), label="baro altitude", alpha=0.8)
    axes[0].set_ylabel("altitude m")
    axes[0].legend(loc="best")
    axes[1].plot(t, _series(frame, "sensor_truth_accel_z_m_s2"), label="truth specific force z")
    axes[1].plot(t, _series(frame, "imu_accel_z_m_s2"), label="IMU accel z", alpha=0.8)
    axes[1].set_ylabel("m/s^2")
    axes[1].legend(loc="best")
    axes[2].plot(t, _series(frame, "controller_collective_duty"), label="collective")
    axes[2].plot(t, _series(frame, "controller_vertical_rate_m_s"), label="est vertical rate")
    axes[2].set_ylabel("controller")
    axes[2].set_xlabel("time s")
    axes[2].legend(loc="best")
    fig.suptitle("Sensors and Controller Signals")
    return fig


def _write_animation_gif(frame: pd.DataFrame, gif_path: Path, mp4_path: Path | None) -> None:
    sample = _animation_sample(frame)
    fig = plt.figure(figsize=(6, 5))
    ax = fig.add_subplot(111, projection="3d")
    x = sample["position_x_m"].to_numpy(dtype=float)
    y = sample["position_y_m"].to_numpy(dtype=float)
    z = sample["position_z_m"].to_numpy(dtype=float)
    margin = max(1.0, float(np.nanmax(np.abs(np.concatenate((x, y)))) + 1.0))
    z_min = min(0.0, float(np.nanmin(z)) - 2.0)
    z_max = float(np.nanmax(z)) + 5.0

    def update(frame_index: int) -> list[Any]:
        ax.clear()
        ax.set_xlim(-margin, margin)
        ax.set_ylim(-margin, margin)
        ax.set_zlim(z_min, z_max)
        ax.set_xlabel("x m")
        ax.set_ylabel("y m")
        ax.set_zlabel("z m")
        ax.set_title("SIL Flight Animation")
        ax.plot(x[: frame_index + 1], y[: frame_index + 1], z[: frame_index + 1], color="#1f77b4")
        ax.scatter([x[frame_index]], [y[frame_index]], [z[frame_index]], color="#d62728", s=35)
        axis = _body_axis(sample.iloc[frame_index])
        base = np.asarray([x[frame_index], y[frame_index], z[frame_index]], dtype=float)
        nose = base + 0.5 * axis
        ax.plot([base[0], nose[0]], [base[1], nose[1]], [base[2], nose[2]], color="#222222", lw=2)
        for valve in range(3):
            if bool(sample.iloc[frame_index].get(f"valve_{valve}_open", False)):
                plume_end = base - np.asarray([0.0, 0.0, 0.7 + 0.1 * valve])
                ax.plot(
                    [base[0], plume_end[0]],
                    [base[1], plume_end[1]],
                    [base[2], plume_end[2]],
                    color="#ff7f0e",
                    lw=3,
                )
        return []

    anim = animation.FuncAnimation(fig, update, frames=len(sample), interval=80, blit=False)
    anim.save(gif_path, writer=animation.PillowWriter(fps=12))
    if mp4_path is not None:
        anim.save(mp4_path, writer=animation.FFMpegWriter(fps=24))
    plt.close(fig)


def _write_animation_html(frame: pd.DataFrame, html_path: Path) -> None:
    sample = _animation_sample(frame)
    payload = {
        "x": sample["position_x_m"].round(4).tolist(),
        "y": sample["position_y_m"].round(4).tolist(),
        "z": sample["position_z_m"].round(4).tolist(),
        "time": sample["time_s"].round(4).tolist(),
        "valves": [
            [
                bool(row.get("valve_0_open", False)),
                bool(row.get("valve_1_open", False)),
                bool(row.get("valve_2_open", False)),
            ]
            for _, row in sample.iterrows()
        ],
    }
    html_path.write_text(_animation_html_template(payload), encoding="utf-8")


def _animation_html_template(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>Flight Animation</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1rem; color: #1f2933; }}
canvas {{ border: 1px solid #ccd3dc; background: #f8fafc; max-width: 100%; }}
.row {{ display: flex; gap: 1rem; align-items: center; margin-top: .75rem; }}
</style>
<h1>Native SIL Flight Animation</h1>
<canvas id="flight" width="900" height="620"></canvas>
<div class="row">
  <button id="toggle">Pause</button>
  <input id="slider" type="range" min="0" value="0">
  <span id="readout"></span>
</div>
<script>
const data = {data};
const canvas = document.getElementById("flight");
const ctx = canvas.getContext("2d");
const slider = document.getElementById("slider");
const readout = document.getElementById("readout");
const toggle = document.getElementById("toggle");
slider.max = data.x.length - 1;
let i = 0;
let playing = true;
const minX = Math.min(...data.x), maxX = Math.max(...data.x);
const minY = Math.min(...data.y), maxY = Math.max(...data.y);
const minZ = Math.min(...data.z), maxZ = Math.max(...data.z);
function sx(x, y) {{
  const denom = Math.max(1e-6, maxX - minX + 0.35*(maxY-minY));
  return 70 + (x - minX + 0.35*y) / denom * 760;
}}
function sz(z, y) {{
  const denom = Math.max(1e-6, maxZ - minZ + 0.15*(maxY-minY));
  return 560 - (z - minZ + 0.15*y) / denom * 500;
}}
function draw(k) {{
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.strokeStyle = "#94a3b8"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(60,560); ctx.lineTo(840,560); ctx.stroke();
  ctx.strokeStyle = "#2563eb"; ctx.lineWidth = 2; ctx.beginPath();
  for (let j=0; j<=k; j++) {{
    const px = sx(data.x[j], data.y[j]), pz = sz(data.z[j], data.y[j]);
    if (j===0) ctx.moveTo(px,pz); else ctx.lineTo(px,pz);
  }}
  ctx.stroke();
  const px = sx(data.x[k], data.y[k]), pz = sz(data.z[k], data.y[k]);
  ctx.fillStyle = "#dc2626"; ctx.beginPath(); ctx.arc(px,pz,8,0,Math.PI*2); ctx.fill();
  ctx.strokeStyle = "#111827";
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(px,pz+16);
  ctx.lineTo(px,pz-24);
  ctx.stroke();
  for (let v=0; v<3; v++) if (data.valves[k][v]) {{
    ctx.strokeStyle = ["#f97316","#fb923c","#fdba74"][v]; ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(px + (v-1)*8, pz+18);
    ctx.lineTo(px + (v-1)*18, pz+55+8*v);
    ctx.stroke();
  }}
  const valves = data.valves[k].map(Number).join("");
  readout.textContent = `t=${{data.time[k].toFixed(3)}} s, `
    + `z=${{data.z[k].toFixed(2)}} m, valves=${{valves}}`;
  slider.value = k;
}}
toggle.onclick = () => {{ playing = !playing; toggle.textContent = playing ? "Pause" : "Play"; }};
slider.oninput = () => {{ i = Number(slider.value); draw(i); }};
setInterval(() => {{ if (playing) {{ i = (i + 1) % data.x.length; draw(i); }} }}, 80);
draw(0);
</script>
</html>
"""


def _animation_sample(frame: pd.DataFrame, max_frames: int = 96) -> pd.DataFrame:
    if len(frame) <= max_frames:
        return frame.reset_index(drop=True)
    indices = np.unique(np.linspace(0, len(frame) - 1, max_frames).astype(int))
    return frame.iloc[indices].reset_index(drop=True)


def _body_axis(row: pd.Series) -> np.ndarray:
    q = np.asarray(
        [row["quat_w"], row["quat_x"], row["quat_y"], row["quat_z"]],
        dtype=float,
    )
    w, x, y, z = q / max(1.0e-12, float(np.linalg.norm(q)))
    return np.asarray(
        [
            2.0 * (x * z + w * y),
            2.0 * (y * z - w * x),
            1.0 - 2.0 * (x * x + y * y),
        ],
        dtype=float,
    )


def _series(frame: pd.DataFrame, name: str) -> np.ndarray:
    if name not in frame:
        return np.zeros(len(frame), dtype=float)
    return np.asarray(frame[name].fillna(0.0).to_numpy(dtype=float), dtype=float)
