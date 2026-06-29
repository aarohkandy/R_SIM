# GUI Notes

- The local GUI is a localhost engineering workbench served by `make gui` or
  `rocketsim gui`.
- It reads the same output bundle artifacts as the CLI: summaries, manifests, plots,
  animation, telemetry previews, thermal outputs, and structural outputs.
- Keep the layout dense and inspection-oriented: run tree, phase tree, central analysis
  panes, right-side inspector, and bottom telemetry table.
- Do not make the GUI a landing page. The first screen should be the usable run
  inspection workspace.
- The emulator tab is reserved for Phase 12 Renode HIL status and should continue to use
  the same `ControllerBackend` terminology as the simulation code.

## Current Implementation Notes

- `rocketsim.gui.server` uses the Python standard library HTTP server, so the GUI has no
  runtime network dependency and no frontend build step.
- Static assets live under `rocketsim/gui/static/`.
- API routes include `/api/runs`, `/api/runs/<run_id>`, `/api/telemetry`, and
  `/artifacts/<run_id>/<relative_path>`.
- Artifact serving is path-confined to the selected run directory to prevent traversal.
