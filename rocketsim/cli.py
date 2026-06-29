"""Command placeholders exposed by the Phase-0 Makefile."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

PHASE_COMMANDS = {
    "e2e": "Phase 8",
    "converge": "Phase 13",
    "montecarlo": "Phase 14",
    "sensitivity": "Phase 15",
    "soak": "Phase 17",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rocketsim")
    parser.add_argument("command", choices=sorted(PHASE_COMMANDS))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    phase = PHASE_COMMANDS[args.command]
    parser.exit(
        status=2,
        message=(
            f"`{args.command}` is intentionally stubbed in Phase 0 and belongs to "
            f"{phase}. See SPEC.md and ASSUMPTIONS.md.\n"
        ),
    )
    raise AssertionError("argparse exit should have terminated")
