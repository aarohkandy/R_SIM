# Thermal Notes

- Thermal analysis runs on logged flight data after trajectory generation.
- Motor heating dominates at these speeds; aerodynamic heating should not be over-modeled
  unless evidence requires it.
- Temperature margins are data outputs, not physics pass/fail asserts.

## Phase 10 Implementation Notes

- `rocketsim.thermal` implements a strict YAML-configured lumped-node transient network
  and a post-flight runner over the logged SIL telemetry. It does not run inside the
  flight dynamics loop.
- Nodes currently model motor casing, foil shield, printed body, carbon frame, solenoids,
  and electronics bay. The config supplies thermal mass, material, initial temperature,
  convection area, and speed-dependent convection coefficients for every node.
- Heat transfer terms include configured conductive links, a configured motor-to-shield
  radiative link, motor thrust-scaled heating, valve-driven solenoid heating, electronics
  self-heating, and convection to the configured ambient temperature using logged flight
  speed.
- Material limits are loaded from `inputs/materials_placeholder.yaml`; margins and first
  crossing times are reported as data. Do not assert on those flight outcomes.
- The e2e bundle writes `thermal/thermal_timeseries.csv`,
  `thermal/thermal_timeseries.parquet`, `thermal/thermal_summary.json`, and two plots:
  `plots/thermal_node_temperatures.png` and `plots/thermal_margin_to_limits.png`.
  Thermal artifacts are now manifest entries rather than deferred artifacts.
