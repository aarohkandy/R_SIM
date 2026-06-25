"""Compatibility launcher for the primary R_SIM Flask backend.

The old top-level app contained a mock simulation path. Pre-goal validation uses
the backend app directly so local smoke output cannot be mistaken for cloud CFD.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("SIMULATION_MODE", "local")

from f_backend import app  # noqa: E402


def main(request):
    """Google Cloud Function compatibility entry point."""
    with app.request_context(request.environ):
        return app.full_dispatch_request()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5011))
    app.run(host="0.0.0.0", port=port, debug=False)
