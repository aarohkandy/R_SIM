"""Helpers for visible placeholder and stub logging."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssumptionEntry:
    """A documented placeholder or stub."""

    identifier: str
    area: str
    assumption: str
    replacement_path: str


def format_assumption(entry: AssumptionEntry) -> str:
    """Format an assumption as a markdown table row."""

    return (
        f"| {entry.identifier} | {entry.area} | {entry.assumption} | "
        f"{entry.replacement_path} |"
    )


def append_assumption(path: Path | str, entry: AssumptionEntry) -> bool:
    """Append an assumption row if its identifier is not already present."""

    assumption_path = Path(path)
    text = assumption_path.read_text(encoding="utf-8") if assumption_path.exists() else ""
    marker = f"| {entry.identifier} |"
    if marker in text:
        return False
    if text and not text.endswith("\n"):
        text += "\n"
    text += format_assumption(entry) + "\n"
    assumption_path.write_text(text, encoding="utf-8")
    return True
