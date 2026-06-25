# Simulation Model

## Current Local Model

The local model estimates thrust, mass, drag, velocity, altitude, lateral drift, pitch/yaw/roll state, angular rates, forces, moments, dynamic pressure, pneumatic pressure, actuator stroke, and active airbrake deployment. It is deterministic with a seed and is intended for design iteration before heavier CFD/table calibration.

This local model is not CFD and is not flight certification. Its output is marked with `source: active_pneumatic_local_dynamics` and `is_placeholder: false`.

## Current Fidelity Hooks

- The local motor catalog is exposed through `/api/environment/motors` with designation search plus manufacturer, impulse-class, diameter, and TARC filters; returned motors include thrust curves used by simulation and UI inspection.
- The local motor catalog can ingest RASP `.eng` and RockSim `.rse` files through `/api/environment/motors/import`, deriving burn time, total impulse, average thrust, peak thrust, and impulse class from the imported thrust samples.
- Motor components may provide `thrustCurve` points as `{time, thrust}` records or `[time, thrust]` pairs. The local model linearly interpolates thrust, uses the integrated curve area as total impulse, and reports `thrust_profile.source: curve`.
- Simulation config may provide `aerodynamics.baseDragCoefficient` and `aerodynamics.activeDragCoefficientTable` points with deployment-to-`cdIncrement` calibration. Without a table, the model falls back to surface-area drag coupling.
- Output includes `trajectory`, `force_history`, and `moment_history` samples so the UI/export path can inspect net forces, thrust, drag, angular rates, and pitch/yaw/roll moments.
- Output includes `landing_footprint` and recovery history ground-track fields so the UI/export path can inspect touchdown range, bearing, deployment points, descent time, and drift after recovery deployment.
- Output includes `recovery_analysis` with an event sequence and phase summaries for drogue/main/total descent timing, descent rate, and drift.
- Output includes `recovery_safety` with required main drag area, estimated terminal velocity, area margin, opening load in newtons and g, shock-cord harness limit, effective opening-load limit, and safety statuses.
- Output includes `stage_splits` as structural split/stage marker metadata derived from builder boundaries; the current local model does not separate stages in flight.
- Input validation treats fins, motors, rail buttons, tube couplers, bulkheads, motor mount tubes, and centering rings as attached subparts. Missing host references warn, while references to non-airframe hosts block the run.
- Internal mass components are accepted as payload/avionics/battery/ballast/recovery mass inputs. They are validated as attached subparts, included in frontend mass/CG, and ignored by backend external geometry and aerodynamic-center calculations.
- Tube couplers and bulkheads are accepted as attached internal airframe hardware. Motor mount tubes and centering rings are accepted as attached internal propulsion hardware. They are validated for positive fit dimensions and remain internal to external geometry and aerodynamic-center calculations.
- Parachute and streamer components are accepted as attached recovery devices. Shock cords are accepted as attached recovery hardware. Main and drogue recovery parts are translated into the landing-system config before validation and simulation, while remaining internal to external geometry and aerodynamic-center calculations. Streamer drag area can come from explicit area or strip length multiplied by strip width. Shock-cord rated strength becomes the harness load limit used by recovery safety.

## Target Model Direction

- 6DOF rigid-body dynamics.
- Atmosphere, wind, turbulence, and launch-site conditions.
- Broader motor thrust curve ingestion from additional vendor and certification data formats.
- Aerodynamic coefficient tables with optional CFD calibration.
- Sensor and actuator noise with deterministic seeds.
- Pneumatic active surfaces coupled into forces, moments, and pressure state.

## Required Future Outputs

- Time history of position, velocity, attitude, angular rates, forces, and moments.
- Apogee, max velocity, flight time, landing/descent summary, recovery footprint, recovery phase analysis, recovery load/safety analysis, and warnings.
- Active-system state: tank pressure, valve commands, actuator stroke, surface deployment, and controller outputs.
