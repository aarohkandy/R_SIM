# Simulation Notes

- The master seed must flow through all stochastic subsystems.
- Parallel Monte Carlo must use deterministic child streams such as `SeedSequence.spawn`.
- Conservation, convergence, cross-validation, Monte Carlo, sensitivity, and soak work are
  first-class phases, not optional extras.

## Phase 8 Implementation Notes

- `run_native_sil_e2e` loads the current configs, builds the Phase 6 plant, Phase 7 sensor
  suite, and Phase 8 native-SIL backend, then advances the plant with fixed-step RK4 until
  touchdown or the configured max time.
- The launch rail is explicitly constrained until rail exit. After rail exit, the plant is
  unconstrained and the controller acts through the same cold-gas valve path future Renode
  HIL will drive.
- The Phase 8 bundle is partial: `telemetry.csv`, `landing_summary.json`, and
  `run_manifest.json`. Phase 9 expands this into plots and animation.
