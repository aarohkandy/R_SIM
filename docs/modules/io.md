# IO Notes

- Data bundles must include telemetry, plots, summaries, manifests, and animation artifacts
  when their phases are implemented.
- Physics outputs are reported as numbers and plots; never encode pass/fail verdicts on
  landing speed, tilt, temperatures, stresses, or CO2 margin.
- Input hashes and seed metadata belong in run manifests for reproducibility.

## Phase 9 Implementation Notes

- `write_full_data_bundle` emits the Phase 9 bundle under the run output directory:
  `telemetry.csv`, `telemetry.parquet`, `landing_summary.json`, `landing_summary.csv`,
  `run_manifest.json`, plots, and animation artifacts.
- Current plot set: altitude/velocity/acceleration, attitude/rates, static-margin/aero,
  solid/cold-gas thrust plus CO2 state, valve activity, and sensor/controller overlays.
- The animation is generated from the same telemetry used for analysis. It writes an
  animated GIF plus an interactive HTML canvas view, including nozzle-plume activity from
  the per-valve telemetry.
- MP4 export is intentionally deferred when `ffmpeg` is absent. The manifest records the
  deferred artifact instead of pretending the MP4 exists.
- FEA plot slots remain deferred to Phase 11 and are recorded in the manifest as
  future-phase artifacts.

## Phase 10 Implementation Notes

- End-to-end bundles now include a `thermal` artifact group in `run_manifest.json` with
  thermal timeseries CSV/Parquet, `thermal_summary.json`, and the thermal temperature and
  margin plots.
- The landing summary includes the nested thermal summary plus top-level
  `peak_thermal_temperature_deg_c` and `minimum_thermal_margin_deg_c` fields. These are
  reported values, not pass/fail verdicts.

## Phase 11 Implementation Notes

- End-to-end bundles now include a `structural` artifact group in `run_manifest.json`
  with load cases, FEA result tables, mesh-convergence data, a CalculiX input deck, and
  structural plots.
- `landing_summary.json` includes nested structural results plus top-level
  `peak_structural_stress_pa` and `peak_structural_displacement_m` fields. These are
  reported values, not pass/fail verdicts.
- JSON writers sanitize non-finite numeric values to `null` so browser clients can read
  summaries and manifests with standards-compliant JSON parsing.
