# Simulation Model

## Current Prep Model

The prep harness uses a deterministic local vertical-flight model for smoke testing. It estimates thrust, mass, drag, velocity, altitude, flight time, and stability fields so the app can prove its API wiring before the full active rocket model exists.

This local model is not CFD and is not flight certification. Its output is marked with `source: local_pre_goal_physics` and `is_placeholder: false`.

## Future Goal Model

- 6DOF rigid-body dynamics.
- Atmosphere, wind, turbulence, and launch-site conditions.
- Motor thrust curve interpolation.
- Aerodynamic coefficient tables with optional CFD calibration.
- Sensor and actuator noise with deterministic seeds.
- Pneumatic active surfaces coupled into forces, moments, and pressure state.

## Required Future Outputs

- Time history of position, velocity, attitude, angular rates, forces, and moments.
- Apogee, max velocity, flight time, landing/descent summary, and warnings.
- Active-system state: tank pressure, valve commands, actuator stroke, surface deployment, and controller outputs.

