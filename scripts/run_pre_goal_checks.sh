#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$ROOT/scripts/setup_backend.sh"
"$ROOT/.venv-pre-goal/bin/python" -m compileall -q -x '(.venv-pre-goal|node_modules|frontend/dist)' "$ROOT"
"$ROOT/.venv-pre-goal/bin/python" -m unittest discover -s "$ROOT/tests"
"$ROOT/.venv-pre-goal/bin/python" "$ROOT/scripts/pre_goal_check.py"
bash "$ROOT/scripts/setup_frontend.sh"

echo "Pre-goal checks passed."
