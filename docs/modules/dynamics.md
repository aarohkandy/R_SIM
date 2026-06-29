# Dynamics Notes

- Controlled flight uses fixed-step RK4 with zero-order-hold on valve states; do not use
  adaptive `solve_ivp`.
- Quaternion attitude is required.
- Conservation, no-thrust ballistic checks, torque-free rotation checks, and deterministic
  telemetry hashes are engineering pass/fail tests.

## Phase 6 Implementation Notes

- `rocketsim.dynamics` uses a fixed-step RK4 integrator over position, velocity,
  attitude quaternion, and body angular velocity.
- Valve commands and CO2 tank state are captured at the start of `DynamicsPlant.step`, so
  cold-gas actuation is zero-order-held across all RK4 substeps. Substep force evaluation
  still recomputes gravity, wind-relative aero, solid thrust, mass properties, and
  time-varying inertia at the substep state/time.
- The derivative uses Euler rigid-body dynamics in the body frame:
  `I * omega_dot = moment - omega x (I * omega)`. The quaternion is renormalized at each
  RK4 stage boundary to keep attitude unit-norm without switching to an adaptive solver.
- The ballistic and torque-free tests are conservation/sanity tests only. Flight outcomes
  remain logged data, never pass/fail verdicts.
