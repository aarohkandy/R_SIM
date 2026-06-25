#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv-pre-goal}"

"$PYTHON_BIN" - <<'PY'
import sys
major, minor = sys.version_info[:2]
if major != 3 or minor < 8 or minor >= 12:
    raise SystemExit("Current backend pins require Python >=3.8 and <3.12 for pre-goal setup.")
PY

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -r "$ROOT/backend/requirements.txt"

echo "Backend environment ready: $VENV_DIR"

