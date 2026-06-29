from __future__ import annotations

from pathlib import Path

from rocketsim.assumptions import AssumptionEntry, append_assumption, format_assumption


def test_format_assumption_table_row() -> None:
    entry = AssumptionEntry(
        identifier="A-TEST",
        area="Inputs",
        assumption="A placeholder exists.",
        replacement_path="Replace it with measured data.",
    )

    assert format_assumption(entry) == (
        "| A-TEST | Inputs | A placeholder exists. | Replace it with measured data. |"
    )


def test_append_assumption_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "ASSUMPTIONS.md"
    entry = AssumptionEntry(
        identifier="A-TEST",
        area="Tooling",
        assumption="A tool is unavailable.",
        replacement_path="Install or document a blocker.",
    )

    assert append_assumption(path, entry)
    assert not append_assumption(path, entry)

    text = path.read_text(encoding="utf-8")
    assert text.count("| A-TEST |") == 1
