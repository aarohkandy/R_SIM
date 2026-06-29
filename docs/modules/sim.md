# Simulation Notes

- The master seed must flow through all stochastic subsystems.
- Parallel Monte Carlo must use deterministic child streams such as `SeedSequence.spawn`.
- Conservation, convergence, cross-validation, Monte Carlo, sensitivity, and soak work are
  first-class phases, not optional extras.
