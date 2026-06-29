# Dynamics Notes

- Controlled flight uses fixed-step RK4 with zero-order-hold on valve states; do not use
  adaptive `solve_ivp`.
- Quaternion attitude is required.
- Conservation, no-thrust ballistic checks, torque-free rotation checks, and deterministic
  telemetry hashes are engineering pass/fail tests.
