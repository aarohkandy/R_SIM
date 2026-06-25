# UI Workflows

## UI Expectations

- The frontend must build and lint.
- The local API base should be documented.
- The app must not require cloud credentials for local smoke testing.
- Keep the main setup uncluttered with advanced active-system sections collapsed.
- Put rocket geometry, motor, environment, controller, and results in clear steps.
- Let users save, restore, duplicate, and run named simulation setups from the current rocket.
- Let users set axial placement for fins, motors, and rail buttons, and reflect those positions in drawing, mass, and CP analysis.
- Let users set the active airbrake force station and see its moment arm against CG before and after simulation.
- Provide a built-in active demo rocket and accept full scenario JSON files with both `rocketData` and `simulationConfig`.
- Let users import OpenRocket `.ork` designs from the builder view and continue editing/simulating the imported components.
- Search and add motors from the local backend motor database, including thrust-curve metadata used by the simulator.
- Show selected motor thrust curves with impulse, burn-time, peak-thrust, and editable sampled points.
- Surface warnings next to the inputs that caused them.
- Show trajectory, force, pressure, drag, and active-system plots backed by the local simulation histories.
- Show landing footprint results with touchdown range, bearing, crossrange, descent time, and recovery drift.
- Support exporting trajectory CSV, force/moment CSV, active-system CSV, recovery CSV, and the full JSON report.
