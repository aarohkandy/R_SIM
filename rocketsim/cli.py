"""Command line entry points for simulation tasks."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from rocketsim.gui import serve_gui
from rocketsim.sim.flight import run_native_sil_e2e

PHASE_COMMANDS = {
    "e2e": "Phase 8",
    "gui": "Local GUI",
    "converge": "Phase 13",
    "montecarlo": "Phase 14",
    "sensitivity": "Phase 15",
    "soak": "Phase 17",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rocketsim")
    parser.add_argument("command", choices=sorted(PHASE_COMMANDS))
    parser.add_argument("--repo-root", default=".", help="Repository root for config/input lookup.")
    parser.add_argument("--output-root", default=None, help="Optional output directory override.")
    parser.add_argument("--host", default="127.0.0.1", help="GUI host for `gui`.")
    parser.add_argument("--port", default=8765, type=int, help="GUI port for `gui`.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "e2e":
        result = run_native_sil_e2e(
            repo_root=Path(args.repo_root),
            output_root=Path(args.output_root) if args.output_root is not None else None,
        )
        print(result.output_dir)
        return 0
    if args.command == "gui":
        serve_gui(repo_root=Path(args.repo_root), host=args.host, port=args.port)
        return 0
    phase = PHASE_COMMANDS[args.command]
    parser.exit(
        status=2,
        message=(
            f"`{args.command}` is intentionally stubbed in Phase 0 and belongs to "
            f"{phase}. See SPEC.md and ASSUMPTIONS.md.\n"
        ),
    )
    raise AssertionError("argparse exit should have terminated")


if __name__ == "__main__":
    raise SystemExit(main())
