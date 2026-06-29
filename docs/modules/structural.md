# Structural Notes

- FEA is event-triggered on logged load cases; never couple FEA into the flight loop.
- Landing impact is the priority structural case.
- Mesh convergence evidence belongs in Phase 11 reporting.

## Phase 11 Implementation Notes

- `rocketsim.structural` extracts event-triggered load cases from logged telemetry:
  landing impact, thrust transient, max-Q, and leg deployment.
- External CalculiX/Gmsh executables are checked through the configured command names.
  When they are absent and fallback is enabled, the module runs a deterministic internal
  3D linear truss FEA fallback and records the solver status explicitly.
- The structural run writes load cases, FEA results, mesh-convergence tables, a CalculiX
  input deck for the landing case, and plots. Results are data, not physics verdicts.
- The fallback mesh-convergence study uses area-preserving member subdivisions for the
  truss model. This avoids artificial hinge mechanisms from inserting free intermediate
  truss nodes.
- Structural analysis remains post-flight only; it consumes logged states and thermal
  context and never feeds forces back into the dynamics loop.
