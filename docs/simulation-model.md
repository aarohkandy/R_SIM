# Simulation Model

## Current Local Model

The local model estimates thrust, mass, drag, velocity, altitude, lateral drift, pitch/yaw/roll state, dynamic pressure, pneumatic pressure, actuator stroke, and active airbrake deployment. It is deterministic with a seed and is intended for design iteration before heavier CFD/table calibration.

This local model is not CFD and is not flight certification. Its output is marked with `source: active_pneumatic_local_dynamics` and `is_placeholder: false`.

## Target Model Direction

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
