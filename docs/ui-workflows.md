# UI Workflows

## UI Expectations

- The frontend must build and lint.
- The local API base should be documented.
- The app must not require cloud credentials for local smoke testing.
- Keep the main setup uncluttered with advanced active-system sections collapsed.
- Put rocket geometry, motor, environment, controller, and results in clear steps.
- Let users save, restore, duplicate, and run named simulation setups from the current rocket.
- Let users set axial placement for fins, motors, rail buttons, motor mount tubes, and centering rings, and reflect those positions in drawing, mass, and CP analysis.
- Let users choose the airframe host for fins, motors, and rail buttons, and show that attachment in the component table.
- Show fins, motors, rail buttons, motor mount tubes, centering rings, internal masses, parachutes, streamers, and shock cords nested under their selected host in the design tree, with unattached subparts separated for repair.
- Let users add payload, avionics, battery, ballast, recovery-hardware mass components, motor mount tubes, and centering rings with editable station, host, dimensions, material, and mass.
- Let users add main/drogue parachutes, streamers, and shock cords as attached recovery components, then edit deployment event, altitude, drag area, Cd, opening-load limits, streamer strip geometry, and harness strength from the component inspector.
- Let users add and remove split markers only between structural parts, with red markers in both the design tree and rocket side view.
- Let users set the active airbrake force station and see its moment arm against CG before and after simulation.
- Provide a built-in active demo rocket and accept full scenario JSON files with both `rocketData` and `simulationConfig`.
- Let users import OpenRocket `.ork` designs from the builder view and continue editing/simulating the imported components.
- Search and add motors from the local backend motor database, including designation-only search, impulse/manufacturer/diameter/TARC filters, and thrust-curve metadata used by the simulator.
- Import RASP `.eng` and RockSim `.rse` motor files from the Motors tab, add them to the local catalog, and immediately use their thrust curves in the rocket.
- Show selected motor thrust curves with impulse, burn-time, peak-thrust, and editable sampled points.
- Surface warnings next to the inputs that caused them.
- Show trajectory, force, pressure, drag, and active-system plots backed by the local simulation histories.
- Show landing footprint results with touchdown range, bearing, crossrange, descent time, and recovery drift.
- Show recovery sequence and phase rows with event timing, deployment velocity, phase duration, average descent rate, and drift.
- Show recovery safety with terminal velocity, required area, area margin, opening load, device/harness load limit, and overall status.
- Support exporting trajectory CSV, force/moment CSV, active-system CSV, recovery CSV, recovery-summary CSV, and the full JSON report.
