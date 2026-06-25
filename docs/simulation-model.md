# Simulation Model

## Current Local Model

The local model estimates thrust, mass, drag, velocity, altitude, lateral drift, pitch/yaw/roll state, angular rates, forces, moments, dynamic pressure, pneumatic pressure, actuator stroke, and active airbrake deployment. It is deterministic with a seed and is intended for design iteration before heavier CFD/table calibration.

This local model is not CFD and is not flight certification. Its output is marked with `source: active_pneumatic_local_dynamics` and `is_placeholder: false`.

## Current Fidelity Hooks

- Motor components may provide `thrustCurve` points as `{time, thrust}` records or `[time, thrust]` pairs. The local model linearly interpolates thrust, uses the integrated curve area as total impulse, and reports `thrust_profile.source: curve`.
- Simulation config may provide `aerodynamics.baseDragCoefficient` and `aerodynamics.activeDragCoefficientTable` points with deployment-to-`cdIncrement` calibration. Without a table, the model falls back to surface-area drag coupling.
- Output includes `trajectory`, `force_history`, and `moment_history` samples so the UI/export path can inspect net forces, thrust, drag, angular rates, and pitch/yaw/roll moments.
- Output includes `landing_footprint` and recovery history ground-track fields so the UI/export path can inspect touchdown range, bearing, deployment points, descent time, and drift after recovery deployment.
- Output includes `recovery_analysis` with an event sequence and phase summaries for drogue/main/total descent timing, descent rate, and drift.

## Target Model Direction

- 6DOF rigid-body dynamics.
- Atmosphere, wind, turbulence, and launch-site conditions.
- Higher-fidelity motor thrust curve ingestion from common file formats.
- Aerodynamic coefficient tables with optional CFD calibration.
- Sensor and actuator noise with deterministic seeds.
- Pneumatic active surfaces coupled into forces, moments, and pressure state.

## Required Future Outputs

- Time history of position, velocity, attitude, angular rates, forces, and moments.
- Apogee, max velocity, flight time, landing/descent summary, recovery footprint, recovery phase analysis, and warnings.
- Active-system state: tank pressure, valve commands, actuator stroke, surface deployment, and controller outputs.
