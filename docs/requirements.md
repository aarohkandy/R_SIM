# Requirements

## User Workflow

- Define a rocket with structural parts, fins, motor data, mass, CG, and launch conditions.
- Mark structural split/stage boundaries between rocket parts while keeping fins, motors, and rail buttons as non-splittable subparts.
- Attach fins, motors, and rail buttons to valid airframe hosts so subparts behave like an OpenRocket-style component hierarchy.
- Import an existing OpenRocket `.ork` design when available, preserving common body, nose, fin, motor, mass, and CG data.
- Define an active air system with pressure source, valves, actuator geometry, deployment location, and surface limits.
- Write controller code that receives simulated sensor data and commands the active system.
- Add deterministic or seeded noise for sensors, atmosphere, actuator response, and pressure behavior.
- Run a simulation and inspect trajectory, stability, controller, actuator, pressure, active-drag, moment, and landing outputs.
- Inspect recovery footprint output with touchdown range, bearing, deployment positions, descent time, and drift after landing-system deployment.
- Inspect recovery event sequence and descent phases with deployment velocities, phase durations, average descent rates, and drift.
- Inspect recovery safety with terminal speed, required main area, area margin, opening load, load limit, and touchdown status.

## Current Requirements

- Setup instructions must work locally on this machine.
- Validation must fail loudly when a dependency, endpoint, or result shape is wrong.
- Local simulation must be deterministic and labeled as active pneumatic local dynamics.
- Fake/random placeholder output must not be accepted as a passing main workflow result.
- The frontend must default to the local simulation API, not a hardcoded cloud/GCP service.
- Motor thrust curves and optional aerodynamic coefficient tables must affect local simulation output when supplied.
- Supplied motor thrust curves must be inspectable/editable in the UI and must own simulated impulse when valid.
- OpenRocket `.ork` import must return simulation-ready rocket components and warn when motor/mass/CG data must be inferred.
- Builder split markers must appear in the design tree and side-view drawing, persist through save/export/import, and be reported in simulation output.
- Builder subparts must expose their airframe attachment host in the inspector/table, auto-attach to a valid aft host when added, and reject invalid subpart-to-subpart references during simulation validation.
- Frontend motor search must use the local backend motor database, not hardcoded placeholder motor data, and support designation, impulse class, manufacturer, diameter, and TARC filters.
- C++ controller code must compile before it is used by an active simulation.
- Pneumatic outputs must show pressure use, actuator movement, and surface deployment when active control commands it.
- Active airbrake location must be editable, validated against rocket length, and reflected in moment outputs.
- Landing outputs must include recovery footprint data and a visible touchdown/drift analysis in the results UI.
- Landing outputs must include recovery sequence and phase analysis plus a CSV export for the recovery summary.
- Landing outputs must include recovery safety/load analysis tied to configurable opening-load and touchdown limits.
- Importable scenario files in `examples/scenarios/` must keep passive, active, warning, and invalid-input behavior reproducible.
