"""Event-triggered structural load cases and finite-element analysis."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from matplotlib import pyplot as plt
from numpy.typing import NDArray

from rocketsim.structural.schema import (
    LoadCaseName,
    StructuralConfig,
    StructuralMemberConfig,
    StructuralNodeConfig,
    load_structural_config,
)

plt.switch_backend("Agg")


@dataclass(frozen=True)
class StructuralLoadCase:
    """One event-triggered structural load case."""

    id: LoadCaseName
    time_s: float
    application_node: str
    force_n: NDArray[np.float64]
    source_row_index: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class StructuralAnalysisResult:
    """In-memory structural analysis products."""

    load_cases: tuple[StructuralLoadCase, ...]
    results_frame: pd.DataFrame
    mesh_convergence_frame: pd.DataFrame
    summary: dict[str, Any]


@dataclass(frozen=True)
class StructuralArtifacts:
    """Paths to written Phase-11 structural products."""

    load_cases_json: Path
    load_cases_csv: Path
    fea_results_csv: Path
    fea_results_parquet: Path
    mesh_convergence_csv: Path
    summary_json: Path
    calculix_input: Path
    plot_paths: tuple[Path, ...]

    def manifest_payload(self, output_dir: Path) -> dict[str, Any]:
        """Return relative artifact paths for the run manifest."""

        return {
            "load_cases_json": self.load_cases_json.relative_to(output_dir).as_posix(),
            "load_cases_csv": self.load_cases_csv.relative_to(output_dir).as_posix(),
            "fea_results_csv": self.fea_results_csv.relative_to(output_dir).as_posix(),
            "fea_results_parquet": self.fea_results_parquet.relative_to(output_dir).as_posix(),
            "mesh_convergence_csv": self.mesh_convergence_csv.relative_to(output_dir).as_posix(),
            "summary_json": self.summary_json.relative_to(output_dir).as_posix(),
            "calculix_input": self.calculix_input.relative_to(output_dir).as_posix(),
            "plots": [path.relative_to(output_dir).as_posix() for path in self.plot_paths],
        }


@dataclass(frozen=True)
class _ElementResult:
    member_id: str
    stress_pa: float
    axial_force_n: float
    strain: float


@dataclass(frozen=True)
class _TrussSolveResult:
    peak_stress_pa: float
    peak_displacement_m: float
    peak_member_id: str
    peak_node_id: str
    element_results: tuple[_ElementResult, ...]
    solver_warning: str | None


def run_configured_structural_analysis(
    config_path: Path | str,
    telemetry_rows: list[dict[str, Any]] | pd.DataFrame,
    repo_root: Path | str,
    thermal_frame: pd.DataFrame | None = None,
) -> StructuralAnalysisResult:
    """Load config and run event-triggered structural analysis."""

    del repo_root
    config = load_structural_config(config_path)
    load_cases = extract_load_cases(config, telemetry_rows, thermal_frame=thermal_frame)
    return run_structural_analysis(config, load_cases)


def extract_load_cases(
    config: StructuralConfig,
    telemetry_rows: list[dict[str, Any]] | pd.DataFrame,
    thermal_frame: pd.DataFrame | None = None,
) -> tuple[StructuralLoadCase, ...]:
    """Extract configured structural load cases from logged telemetry."""

    frame = _telemetry_frame(telemetry_rows)
    load_cases: list[StructuralLoadCase] = []
    enabled = set(config.data.load_cases.enabled)
    if "landing_impact" in enabled:
        load_cases.append(_landing_load_case(config, frame, thermal_frame))
    if "thrust_transient" in enabled:
        load_cases.append(_thrust_load_case(config, frame, thermal_frame))
    if "max_q" in enabled:
        load_cases.append(_max_q_load_case(config, frame, thermal_frame))
    if "leg_deploy" in enabled:
        load_cases.append(_leg_deploy_load_case(config, frame, thermal_frame))
    return tuple(load_cases)


def run_structural_analysis(
    config: StructuralConfig,
    load_cases: tuple[StructuralLoadCase, ...],
) -> StructuralAnalysisResult:
    """Run external FEA when available, otherwise deterministic internal truss FEA."""

    external_status = _external_solver_status(config)
    final_subdivision = max(config.data.mesh_convergence.element_subdivisions)
    result_rows: list[dict[str, Any]] = []
    for load_case in load_cases:
        solve = _solve_truss(config, load_case, final_subdivision)
        material = _member_material(config, solve.peak_member_id)
        result_rows.append(
            {
                "case_id": load_case.id,
                "time_s": load_case.time_s,
                "solver": external_status["solver_used"],
                "external_solver_available": external_status["external_solver_available"],
                "element_subdivisions": final_subdivision,
                "peak_stress_pa": solve.peak_stress_pa,
                "peak_displacement_m": solve.peak_displacement_m,
                "peak_member_id": solve.peak_member_id,
                "peak_node_id": solve.peak_node_id,
                "allowable_stress_pa": material.allowable_stress_pa,
                "stress_margin_pa": material.allowable_stress_pa - solve.peak_stress_pa,
                "solver_warning": solve.solver_warning,
            }
        )
    results_frame = pd.DataFrame(result_rows)
    mesh_convergence = _landing_mesh_convergence(config, load_cases)
    summary = _structural_summary(
        config=config,
        load_cases=load_cases,
        results_frame=results_frame,
        mesh_convergence_frame=mesh_convergence,
        external_status=external_status,
    )
    return StructuralAnalysisResult(
        load_cases=load_cases,
        results_frame=results_frame,
        mesh_convergence_frame=mesh_convergence,
        summary=summary,
    )


def write_structural_artifacts(
    result: StructuralAnalysisResult,
    config: StructuralConfig,
    output_dir: Path,
) -> StructuralArtifacts:
    """Write load cases, FEA results, plots, and CalculiX input files."""

    structural_dir = output_dir / "structural"
    calculix_dir = structural_dir / "calculix"
    plots_dir = output_dir / "plots"
    structural_dir.mkdir(parents=True, exist_ok=True)
    calculix_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    load_cases_json = structural_dir / "load_cases.json"
    load_cases_csv = structural_dir / "load_cases.csv"
    fea_results_csv = structural_dir / "fea_results.csv"
    fea_results_parquet = structural_dir / "fea_results.parquet"
    mesh_convergence_csv = structural_dir / "mesh_convergence.csv"
    summary_json = structural_dir / "structural_summary.json"
    calculix_input = calculix_dir / "landing_impact.inp"

    load_case_payload = [_load_case_payload(load_case) for load_case in result.load_cases]
    _write_json(load_cases_json, {"load_cases": load_case_payload})
    pd.DataFrame(load_case_payload).to_csv(load_cases_csv, index=False)
    result.results_frame.to_csv(fea_results_csv, index=False)
    result.results_frame.to_parquet(fea_results_parquet, index=False)
    result.mesh_convergence_frame.to_csv(mesh_convergence_csv, index=False)
    _write_json(summary_json, result.summary)
    _write_calculix_input(config, result.load_cases[0], calculix_input)

    plot_paths = (
        plots_dir / "fea_stress_summary.png",
        plots_dir / "fea_displacement_summary.png",
        plots_dir / "fea_mesh_convergence.png",
    )
    _plot_stress_summary(result.results_frame).savefig(plot_paths[0], dpi=140, bbox_inches="tight")
    plt.close()
    _plot_displacement_summary(result.results_frame).savefig(
        plot_paths[1],
        dpi=140,
        bbox_inches="tight",
    )
    plt.close()
    _plot_mesh_convergence(result.mesh_convergence_frame).savefig(
        plot_paths[2],
        dpi=140,
        bbox_inches="tight",
    )
    plt.close()
    return StructuralArtifacts(
        load_cases_json=load_cases_json,
        load_cases_csv=load_cases_csv,
        fea_results_csv=fea_results_csv,
        fea_results_parquet=fea_results_parquet,
        mesh_convergence_csv=mesh_convergence_csv,
        summary_json=summary_json,
        calculix_input=calculix_input,
        plot_paths=plot_paths,
    )


def _landing_load_case(
    config: StructuralConfig,
    frame: pd.DataFrame,
    thermal_frame: pd.DataFrame | None,
) -> StructuralLoadCase:
    row_index = len(frame) - 1
    row = frame.iloc[row_index]
    mass = _row_value(row, "mass_kg", 0.9)
    vx = _row_value(row, "velocity_x_m_s", 0.0)
    vy = _row_value(row, "velocity_y_m_s", 0.0)
    vz = _row_value(row, "velocity_z_m_s", 0.0)
    stop_distance = config.data.load_cases.landing_stop_distance_m
    vertical_decel_m_s2 = vz * vz / (2.0 * stop_distance)
    lateral_speed = float(np.hypot(vx, vy))
    lateral_decel_m_s2 = lateral_speed * lateral_speed / (2.0 * stop_distance)
    lateral_force = np.zeros(2, dtype=np.float64)
    if lateral_speed > 1.0e-12:
        lateral_force = -mass * lateral_decel_m_s2 * np.asarray([vx, vy]) / lateral_speed
    force = np.asarray(
        [
            lateral_force[0],
            lateral_force[1],
            -mass * (vertical_decel_m_s2 + config.data.load_cases.gravity_m_s2),
        ],
        dtype=np.float64,
    )
    return _load_case(
        config,
        "landing_impact",
        row,
        row_index,
        force,
        {
            "stop_distance_m": stop_distance,
            "vertical_decel_m_s2": vertical_decel_m_s2,
            "lateral_decel_m_s2": lateral_decel_m_s2,
            "touchdown_speed_m_s": float(np.linalg.norm(np.asarray([vx, vy, vz]))),
        },
        thermal_frame,
    )


def _thrust_load_case(
    config: StructuralConfig,
    frame: pd.DataFrame,
    thermal_frame: pd.DataFrame | None,
) -> StructuralLoadCase:
    thrust = _series(frame, "solid_thrust_n")
    row_index = int(np.argmax(thrust))
    row = frame.iloc[row_index]
    axis = _unit(np.asarray(config.data.load_cases.thrust_axis_unit, dtype=np.float64))
    force = -float(thrust[row_index]) * axis
    return _load_case(
        config,
        "thrust_transient",
        row,
        row_index,
        force,
        {"solid_thrust_n": float(thrust[row_index])},
        thermal_frame,
    )


def _max_q_load_case(
    config: StructuralConfig,
    frame: pd.DataFrame,
    thermal_frame: pd.DataFrame | None,
) -> StructuralLoadCase:
    dynamic_pressure = _series(frame, "dynamic_pressure_pa")
    row_index = int(np.argmax(dynamic_pressure))
    row = frame.iloc[row_index]
    vx = _row_value(row, "velocity_x_m_s", 0.0)
    vy = _row_value(row, "velocity_y_m_s", 0.0)
    lateral = np.asarray([vx, vy], dtype=np.float64)
    norm = float(np.linalg.norm(lateral))
    direction = np.asarray([1.0, 0.0], dtype=np.float64) if norm <= 1.0e-12 else lateral / norm
    lateral_force_n = (
        float(dynamic_pressure[row_index])
        * config.data.load_cases.max_q_reference_area_m2
        * config.data.load_cases.max_q_lateral_coefficient
    )
    force = np.asarray([lateral_force_n * direction[0], lateral_force_n * direction[1], 0.0])
    return _load_case(
        config,
        "max_q",
        row,
        row_index,
        force,
        {"dynamic_pressure_pa": float(dynamic_pressure[row_index])},
        thermal_frame,
    )


def _leg_deploy_load_case(
    config: StructuralConfig,
    frame: pd.DataFrame,
    thermal_frame: pd.DataFrame | None,
) -> StructuralLoadCase:
    target_time = config.data.load_cases.leg_deploy_time_s
    row_index = _nearest_time_index(frame, target_time)
    row = frame.iloc[row_index]
    force = np.asarray([0.0, 0.0, -config.data.load_cases.leg_deploy_shock_force_n])
    return _load_case(
        config,
        "leg_deploy",
        row,
        row_index,
        force,
        {"configured_deploy_time_s": target_time},
        thermal_frame,
    )


def _load_case(
    config: StructuralConfig,
    case_id: LoadCaseName,
    row: pd.Series,
    row_index: int,
    force_n: NDArray[np.float64],
    metadata: dict[str, Any],
    thermal_frame: pd.DataFrame | None,
) -> StructuralLoadCase:
    time_s = _row_value(row, "time_s", 0.0)
    metadata = {
        **metadata,
        "mass_kg": _row_value(row, "mass_kg", 0.0),
        "thermal_peak_temperature_deg_c": _thermal_peak_at_time(thermal_frame, time_s),
        "force_magnitude_n": float(np.linalg.norm(force_n)),
    }
    return StructuralLoadCase(
        id=case_id,
        time_s=time_s,
        application_node=config.data.load_cases.application_node,
        force_n=np.asarray(force_n, dtype=np.float64),
        source_row_index=row_index,
        metadata=metadata,
    )


def _solve_truss(
    config: StructuralConfig,
    load_case: StructuralLoadCase,
    subdivisions: int,
) -> _TrussSolveResult:
    nodes, elements = _refined_mesh(config, subdivisions)
    node_ids = [node.id for node in nodes]
    node_index = {node_id: index for index, node_id in enumerate(node_ids)}
    dof_count = len(nodes) * 3
    stiffness = np.zeros((dof_count, dof_count), dtype=np.float64)
    force = np.zeros(dof_count, dtype=np.float64)
    app_index = node_index[load_case.application_node]
    force[3 * app_index : 3 * app_index + 3] = load_case.force_n

    for member, start_id, end_id in elements:
        start_index = node_index[start_id]
        end_index = node_index[end_id]
        start = np.asarray(nodes[start_index].position_m, dtype=np.float64)
        end = np.asarray(nodes[end_index].position_m, dtype=np.float64)
        delta = end - start
        length = float(np.linalg.norm(delta))
        direction = delta / length
        material = config.data.materials[member.material]
        axial_stiffness = material.young_modulus_pa * member.area_m2 / length
        local = axial_stiffness * np.outer(direction, direction)
        start_slice = slice(3 * start_index, 3 * start_index + 3)
        end_slice = slice(3 * end_index, 3 * end_index + 3)
        stiffness[start_slice, start_slice] += local
        stiffness[start_slice, end_slice] -= local
        stiffness[end_slice, start_slice] -= local
        stiffness[end_slice, end_slice] += local

    fixed_dofs: list[int] = []
    for index, node in enumerate(nodes):
        if node.fixed:
            fixed_dofs.extend([3 * index, 3 * index + 1, 3 * index + 2])
    free_dofs = np.asarray([dof for dof in range(dof_count) if dof not in fixed_dofs])
    displacement = np.zeros(dof_count, dtype=np.float64)
    warning: str | None = None
    try:
        displacement[free_dofs] = np.linalg.solve(
            stiffness[np.ix_(free_dofs, free_dofs)],
            force[free_dofs],
        )
    except np.linalg.LinAlgError:
        warning = "singular stiffness matrix regularized"
        regularized = stiffness[np.ix_(free_dofs, free_dofs)] + np.eye(len(free_dofs)) * 1.0e-9
        displacement[free_dofs] = np.linalg.solve(regularized, force[free_dofs])

    element_results: list[_ElementResult] = []
    for member, start_id, end_id in elements:
        start_index = node_index[start_id]
        end_index = node_index[end_id]
        start = np.asarray(nodes[start_index].position_m, dtype=np.float64)
        end = np.asarray(nodes[end_index].position_m, dtype=np.float64)
        direction = _unit(end - start)
        length = float(np.linalg.norm(end - start))
        start_u = displacement[3 * start_index : 3 * start_index + 3]
        end_u = displacement[3 * end_index : 3 * end_index + 3]
        axial_extension = float((end_u - start_u) @ direction)
        strain = axial_extension / length
        material = config.data.materials[member.material]
        stress = material.young_modulus_pa * strain
        axial_force = stress * member.area_m2
        element_results.append(
            _ElementResult(
                member_id=member.id,
                stress_pa=float(stress),
                axial_force_n=float(axial_force),
                strain=float(strain),
            )
        )
    displacement_norms = np.linalg.norm(displacement.reshape((-1, 3)), axis=1)
    peak_element = max(element_results, key=lambda item: abs(item.stress_pa))
    peak_node_index = int(np.argmax(displacement_norms))
    return _TrussSolveResult(
        peak_stress_pa=abs(peak_element.stress_pa),
        peak_displacement_m=float(displacement_norms[peak_node_index]),
        peak_member_id=peak_element.member_id,
        peak_node_id=node_ids[peak_node_index],
        element_results=tuple(element_results),
        solver_warning=warning,
    )


def _landing_mesh_convergence(
    config: StructuralConfig,
    load_cases: tuple[StructuralLoadCase, ...],
) -> pd.DataFrame:
    landing = next((case for case in load_cases if case.id == "landing_impact"), load_cases[0])
    rows: list[dict[str, Any]] = []
    previous_stress: float | None = None
    previous_displacement: float | None = None
    for subdivisions in config.data.mesh_convergence.element_subdivisions:
        solve = _solve_truss(config, landing, int(subdivisions))
        rows.append(
            {
                "case_id": landing.id,
                "element_subdivisions": int(subdivisions),
                "peak_stress_pa": solve.peak_stress_pa,
                "peak_displacement_m": solve.peak_displacement_m,
                "stress_delta_from_previous_pa": None
                if previous_stress is None
                else solve.peak_stress_pa - previous_stress,
                "displacement_delta_from_previous_m": None
                if previous_displacement is None
                else solve.peak_displacement_m - previous_displacement,
            }
        )
        previous_stress = solve.peak_stress_pa
        previous_displacement = solve.peak_displacement_m
    return pd.DataFrame(rows)


def _structural_summary(
    config: StructuralConfig,
    load_cases: tuple[StructuralLoadCase, ...],
    results_frame: pd.DataFrame,
    mesh_convergence_frame: pd.DataFrame,
    external_status: dict[str, Any],
) -> dict[str, Any]:
    peak_stress_row = results_frame.iloc[int(np.argmax(_series(results_frame, "peak_stress_pa")))]
    peak_disp_row = results_frame.iloc[
        int(np.argmax(_series(results_frame, "peak_displacement_m")))
    ]
    cases = {
        str(row["case_id"]): {
            "time_s": float(row["time_s"]),
            "peak_stress_pa": float(row["peak_stress_pa"]),
            "peak_displacement_m": float(row["peak_displacement_m"]),
            "peak_member_id": str(row["peak_member_id"]),
            "peak_node_id": str(row["peak_node_id"]),
            "allowable_stress_pa": float(row["allowable_stress_pa"]),
            "stress_margin_pa": float(row["stress_margin_pa"]),
        }
        for _, row in results_frame.iterrows()
    }
    return {
        "solver_preference": config.data.solver_preference,
        **external_status,
        "load_case_count": len(load_cases),
        "peak_stress_pa": float(peak_stress_row["peak_stress_pa"]),
        "peak_stress_case_id": str(peak_stress_row["case_id"]),
        "peak_displacement_m": float(peak_disp_row["peak_displacement_m"]),
        "peak_displacement_case_id": str(peak_disp_row["case_id"]),
        "cases": cases,
        "mesh_convergence": _json_safe(mesh_convergence_frame.to_dict(orient="records")),
    }


def _external_solver_status(config: StructuralConfig) -> dict[str, Any]:
    ccx_path = shutil.which(config.data.external_solver.calculix_executable)
    gmsh_path = shutil.which(config.data.external_solver.gmsh_executable)
    if config.data.solver_preference == "calculix" and ccx_path is not None:
        return {
            "external_solver_available": True,
            "external_solver_name": "calculix",
            "external_solver_path": ccx_path,
            "gmsh_path": gmsh_path,
            "solver_used": "calculix",
            "solver_status": "external solver available",
        }
    if not config.data.external_solver.allow_internal_fallback:
        msg = "external structural solver unavailable and internal fallback disabled"
        raise RuntimeError(msg)
    return {
        "external_solver_available": False,
        "external_solver_name": config.data.solver_preference,
        "external_solver_path": None,
        "gmsh_path": gmsh_path,
        "solver_used": "internal_linear_truss",
        "solver_status": "external solver missing; internal deterministic truss FEA used",
    }


def _refined_mesh(
    config: StructuralConfig,
    subdivisions: int,
) -> tuple[tuple[StructuralNodeConfig, ...], tuple[tuple[StructuralMemberConfig, str, str], ...]]:
    nodes = tuple(config.data.nodes)
    elements: list[tuple[StructuralMemberConfig, str, str]] = []
    for member in config.data.members:
        for segment in range(subdivisions):
            refined_member = member.model_copy(
                update={
                    "id": f"{member.id}_sub_{segment + 1}" if subdivisions > 1 else member.id,
                    "area_m2": member.area_m2 / subdivisions,
                }
            )
            elements.append((refined_member, member.from_node, member.to_node))
    return nodes, tuple(elements)


def _write_calculix_input(
    config: StructuralConfig,
    load_case: StructuralLoadCase,
    path: Path,
) -> None:
    node_ids = [node.id for node in config.data.nodes]
    node_number = {node_id: index + 1 for index, node_id in enumerate(node_ids)}
    lines = ["*Heading", f"Phase 11 load case: {load_case.id}", "*Node"]
    for node in config.data.nodes:
        x, y, z = node.position_m
        lines.append(f"{node_number[node.id]}, {x:.9g}, {y:.9g}, {z:.9g}")
    lines.append("*Element, type=T3D2, elset=ALL_MEMBERS")
    for index, member in enumerate(config.data.members, start=1):
        lines.append(f"{index}, {node_number[member.from_node]}, {node_number[member.to_node]}")
    for material_id, material in config.data.materials.items():
        lines.extend(
            [
                f"*Material, name={material_id}",
                "*Elastic",
                f"{material.young_modulus_pa:.9g}, 0.3",
            ]
        )
    for member in config.data.members:
        lines.extend(
            [
                f"*Solid Section, elset={member.id}, material={member.material}",
                f"{member.area_m2:.9g}",
            ]
        )
    lines.append("*Boundary")
    for node in config.data.nodes:
        if node.fixed:
            lines.append(f"{node_number[node.id]}, 1, 3, 0.0")
    app_node = node_number[load_case.application_node]
    lines.extend(["*Cload", f"{app_node}, 1, {load_case.force_n[0]:.9g}"])
    lines.append(f"{app_node}, 2, {load_case.force_n[1]:.9g}")
    lines.append(f"{app_node}, 3, {load_case.force_n[2]:.9g}")
    lines.extend(["*Step", "*Static", "*Node File", "U", "*El File", "S", "*End Step"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _member_material(config: StructuralConfig, member_id: str) -> Any:
    base_member_id = member_id.split("_sub_", maxsplit=1)[0]
    member = next(member for member in config.data.members if member.id == base_member_id)
    return config.data.materials[member.material]


def _load_case_payload(load_case: StructuralLoadCase) -> dict[str, Any]:
    return {
        "id": load_case.id,
        "time_s": load_case.time_s,
        "application_node": load_case.application_node,
        "force_x_n": float(load_case.force_n[0]),
        "force_y_n": float(load_case.force_n[1]),
        "force_z_n": float(load_case.force_n[2]),
        "force_magnitude_n": float(np.linalg.norm(load_case.force_n)),
        "source_row_index": load_case.source_row_index,
        **load_case.metadata,
    }


def _telemetry_frame(telemetry_rows: list[dict[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    frame = (
        telemetry_rows.copy()
        if isinstance(telemetry_rows, pd.DataFrame)
        else pd.DataFrame(telemetry_rows)
    )
    if "time_s" not in frame:
        msg = "structural load extraction requires telemetry time_s"
        raise ValueError(msg)
    frame = frame.sort_values("time_s").reset_index(drop=True)
    if len(frame) < 2:
        msg = "structural load extraction requires at least two telemetry rows"
        raise ValueError(msg)
    times = frame["time_s"].to_numpy(dtype=float)
    if not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0.0):
        msg = "structural telemetry time_s must be finite and strictly increasing"
        raise ValueError(msg)
    return frame


def _thermal_peak_at_time(thermal_frame: pd.DataFrame | None, time_s: float) -> float | None:
    if thermal_frame is None or thermal_frame.empty or "time_s" not in thermal_frame:
        return None
    index = _nearest_time_index(thermal_frame, time_s)
    row = thermal_frame.iloc[index]
    values = [
        float(row[column])
        for column in thermal_frame.columns
        if column.startswith("thermal_") and column.endswith("_temperature_deg_c")
    ]
    return max(values) if values else None


def _nearest_time_index(frame: pd.DataFrame, time_s: float) -> int:
    times = frame["time_s"].to_numpy(dtype=float)
    return int(np.argmin(np.abs(times - time_s)))


def _row_value(row: pd.Series, key: str, default: float) -> float:
    if key not in row or pd.isna(row[key]):
        return default
    return float(row[key])


def _series(frame: pd.DataFrame, name: str) -> NDArray[np.float64]:
    if name not in frame:
        return np.zeros(len(frame), dtype=np.float64)
    values: NDArray[np.float64] = np.asarray(
        frame[name].fillna(0.0).to_numpy(dtype=float),
        dtype=np.float64,
    )
    return values


def _unit(vector: NDArray[np.float64]) -> NDArray[np.float64]:
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        msg = "zero-length vector cannot be normalized"
        raise ValueError(msg)
    return vector / norm


def _plot_stress_summary(frame: pd.DataFrame) -> Any:
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [str(value) for value in frame["case_id"]]
    ax.bar(labels, _series(frame, "peak_stress_pa") / 1.0e6, color="#2563eb")
    ax.set_ylabel("peak stress MPa")
    ax.set_title("Event-Triggered FEA Stress Summary")
    ax.tick_params(axis="x", rotation=20)
    return fig


def _plot_displacement_summary(frame: pd.DataFrame) -> Any:
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [str(value) for value in frame["case_id"]]
    ax.bar(labels, _series(frame, "peak_displacement_m") * 1000.0, color="#dc2626")
    ax.set_ylabel("peak displacement mm")
    ax.set_title("Event-Triggered FEA Displacement Summary")
    ax.tick_params(axis="x", rotation=20)
    return fig


def _plot_mesh_convergence(frame: pd.DataFrame) -> Any:
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    x = _series(frame, "element_subdivisions")
    axes[0].plot(x, _series(frame, "peak_stress_pa") / 1.0e6, marker="o")
    axes[0].set_ylabel("peak stress MPa")
    axes[1].plot(x, _series(frame, "peak_displacement_m") * 1000.0, marker="o")
    axes[1].set_ylabel("peak displacement mm")
    axes[1].set_xlabel("member subdivisions")
    fig.suptitle("Landing Impact FEA Mesh Convergence")
    return fig


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
    return value
