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
- Phase 9 expands the bundle to include CSV and Parquet telemetry, JSON and CSV landing
  summaries, plot artifacts, animated GIF plus interactive HTML animation, and a manifest
  that records produced and deferred artifacts.
- Phase 10 runs the thermal analysis immediately after the logged SIL flight and before
  the final bundle manifest is written, so the manifest and landing summary include the
  thermal timeseries, plots, peak node temperature, and minimum material-limit margin.
- Phase 11 runs structural load-case extraction and event-triggered FEA after thermal
  post-processing and before the final manifest is written. The flight loop remains
  uncoupled from FEA.
- The localhost GUI command reads the finished bundle from disk; it does not alter the
  simulation or become a second source of truth.
- Phase 13 uses the same native-SIL runner with explicit `SimConfig` timing overrides to
  run a configured timestep/Renode-quantum refinement ladder. It writes convergence
  tables, a convergence plot, analytic ballistic cross-validation, OpenRocket-anchor aero
  cross-validation, and a manifest under `outputs/phase13_convergence/`.
- RocketPy passive-ascent cross-validation is reported as unavailable when RocketPy is
  not installed; the code must not fabricate a comparison.
