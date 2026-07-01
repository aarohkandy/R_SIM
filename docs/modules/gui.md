# GUI Notes

- The local GUI is a localhost engineering workbench served by `make gui` or
  `rocketsim gui`.
- It reads the same output bundle artifacts as the CLI: summaries, manifests, plots,
  animation, telemetry previews, thermal outputs, and structural outputs.
- Keep the layout dense and inspection-oriented: definition file tree, run tree, phase
  tree, central editor/analysis panes, right-side inspector, and bottom telemetry table.
- Do not make the GUI a landing page. The first screen should be the usable run
  definition/editing workspace.
- The emulator tab is reserved for Phase 12 Renode HIL status and should continue to use
  the same `ControllerBackend` terminology as the simulation code.

## Current Implementation Notes

- `rocketsim.gui.server` uses the Python standard library HTTP server, so the GUI has no
  runtime network dependency and no frontend build step.
- Static assets live under `rocketsim/gui/static/`.
- API routes include `/api/runs`, `/api/runs/<run_id>`, `/api/telemetry`, and
  `/artifacts/<run_id>/<relative_path>`.
- Artifact serving is path-confined to the selected run directory to prevent traversal.
- `rocketsim.gui.workbench` exposes only whitelisted repo files for editing. The browser
  can edit the actual rocket definition files such as `inputs/bom_placeholder.yaml`,
  `config/vehicle.yaml`, `config/coldgas.yaml`, `config/control.yaml`, and the placeholder
  motor curve. Every save validates through the matching pydantic schema, CSV parser, or
  motor parser before touching disk.
- The Design tab includes a Rocket Builder form for the most common vehicle values:
  body diameter/length, target wet mass, CO2 mass, regulator pressure, nozzle throat
  area, controller loop rate, landing-burn altitude, master seed, fixed timestep, and
  motor curve path. Saving the form updates the same validated YAML/BOM files used by
  the raw editor and the simulator.
- Definition routes include `/api/configs`, `/api/configs/<name>`,
  `/api/configs/<name>/validate`, `/api/rocket-summary`, `/api/rocket-builder`, and
  `/api/run/e2e`.
- HIL status is exposed through `/api/hil-status`, which reads the latest Phase-12
  Renode report or builds a live preflight report when no status artifact exists.
- The Design tab opens on the BOM/parts editor because that is where rocket masses,
  part positions, propellant depletion, CO2 mass, and deployable leg kinematics are
  currently defined. A definition-file picker remains visible when the sidebar collapses.
