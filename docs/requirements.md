# Requirements

## User Workflow

- Define a rocket with structural parts, fins, motor data, mass, CG, and launch conditions.
- Mark structural split/stage boundaries between rocket parts while keeping fins, motors, and rail buttons as non-splittable subparts.
- Attach fins, motors, and rail buttons to valid airframe hosts so subparts behave like an OpenRocket-style component hierarchy.
- Inspect attached subparts nested beneath their host airframe parts in the design tree.
- Place internal payload, avionics, battery, and ballast mass components along the rocket so CG and stability can be tuned without changing exterior geometry.
- Place main/drogue parachute, streamer, and shock-cord recovery components in the rocket tree so recovery area, Cd, deployment event, altitude, harness length, and opening-load limits can be edited as parts.
- Import an existing OpenRocket `.ork` design when available, preserving common body, nose, fin, motor, mass, and CG data.
- Import RASP `.eng` and RockSim `.rse` motor thrust-curve files into the local motor catalog.
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
- Builder design tree must nest attached subparts below their host airframe components and flag unattached subparts separately.
- Internal mass components must expose station, host, role, and mass controls; affect component mass/CG calculations; render in the side view; and remain excluded from external length, diameter, and aerodynamic geometry.
- Parachute, streamer, and shock-cord recovery components must expose host, station, and recovery-specific controls; render in the side view; import from OpenRocket files; and drive the landing/recovery simulation config. Parachutes/streamers must expose main/drogue role, deploy event, deploy altitude, drag area, Cd, and opening-load controls. Streamers must expose strip length/width controls that can compute drag area. Shock cords must expose cord length, diameter, material, and rated strength that limits recovery opening loads.
- Frontend motor search must use the local backend motor database, not hardcoded placeholder motor data, and support designation, impulse class, manufacturer, diameter, and TARC filters.
- Motor imports must accept common `.eng` and `.rse` thrust-curve files, compute impulse/burn/average/peak values from the curve, and make the imported motor selectable from the Motors tab.
- C++ controller code must compile before it is used by an active simulation.
- Pneumatic outputs must show pressure use, actuator movement, and surface deployment when active control commands it.
- Active airbrake location must be editable, validated against rocket length, and reflected in moment outputs.
- Landing outputs must include recovery footprint data and a visible touchdown/drift analysis in the results UI.
- Landing outputs must include recovery sequence and phase analysis plus a CSV export for the recovery summary.
- Landing outputs must include recovery safety/load analysis tied to configurable opening-load, shock-cord harness, and touchdown limits.
- Importable scenario files in `examples/scenarios/` must keep passive, active, warning, and invalid-input behavior reproducible.
