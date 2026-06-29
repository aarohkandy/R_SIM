"""OpenRocket anchor ingestion and comparison.

OpenRocket data is a validation anchor only; runtime aero is computed by `AeroModel`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from rocketsim.aero.model import AeroConfigurationState, AeroModel


@dataclass(frozen=True)
class OpenRocketAnchor:
    """One frozen-configuration CP/Cd export row."""

    mach: float
    leg_angle_deg: float
    propellant_remaining_fraction: float
    co2_remaining_fraction: float
    cg_axial_m: float
    cp_axial_m: float
    cd: float

    def to_state(self) -> AeroConfigurationState:
        return AeroConfigurationState(
            mach=self.mach,
            leg_deploy_angle_deg=self.leg_angle_deg,
            cg_axial_m=self.cg_axial_m,
            propellant_remaining_fraction=self.propellant_remaining_fraction,
            co2_remaining_fraction=self.co2_remaining_fraction,
        )


@dataclass(frozen=True)
class AeroComparisonRow:
    """Ours-vs-OpenRocket delta for one anchor."""

    anchor: OpenRocketAnchor
    cp_delta_m: float
    cd_delta: float
    cp_within_tolerance: bool
    cd_within_tolerance: bool


@dataclass(frozen=True)
class AeroComparisonReport:
    """Comparison report across all anchors."""

    rows: tuple[AeroComparisonRow, ...]

    @property
    def all_within_tolerance(self) -> bool:
        return all(row.cp_within_tolerance and row.cd_within_tolerance for row in self.rows)


def load_openrocket_anchors(path: Path | str) -> tuple[OpenRocketAnchor, ...]:
    """Load OpenRocket-style frozen CP/Cd CSV anchors."""

    anchor_path = Path(path)
    with anchor_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "mach",
            "leg_angle_deg",
            "propellant_remaining_fraction",
            "co2_remaining_fraction",
            "cg_axial_m",
            "cp_axial_m",
            "cd",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            msg = f"{anchor_path} is missing required OpenRocket anchor columns"
            raise ValueError(msg)
        return tuple(
            OpenRocketAnchor(
                mach=float(row["mach"]),
                leg_angle_deg=float(row["leg_angle_deg"]),
                propellant_remaining_fraction=float(row["propellant_remaining_fraction"]),
                co2_remaining_fraction=float(row["co2_remaining_fraction"]),
                cg_axial_m=float(row["cg_axial_m"]),
                cp_axial_m=float(row["cp_axial_m"]),
                cd=float(row["cd"]),
            )
            for row in reader
        )


def compare_to_openrocket(
    model: AeroModel,
    anchors: tuple[OpenRocketAnchor, ...],
) -> AeroComparisonReport:
    """Compare live model output to frozen OpenRocket anchors."""

    comparison = model.definition.data.comparison
    rows: list[AeroComparisonRow] = []
    for anchor in anchors:
        result = model.evaluate(anchor.to_state())
        cp_delta = result.cp_axial_m - anchor.cp_axial_m
        cd_delta = result.cd - anchor.cd
        rows.append(
            AeroComparisonRow(
                anchor=anchor,
                cp_delta_m=cp_delta,
                cd_delta=cd_delta,
                cp_within_tolerance=abs(cp_delta) <= comparison.cp_tolerance_m,
                cd_within_tolerance=abs(cd_delta) <= comparison.cd_tolerance,
            )
        )
    return AeroComparisonReport(rows=tuple(rows))
