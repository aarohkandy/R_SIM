# Progress

## 2026-06-29 — Phase 0 setup scaffold

- Added the revised `SPEC.md` contract and `GOAL_PROMPT.md`.
- Added repository instructions, package metadata, task runner, Phase-0 helper code,
  placeholder configs, and placeholder inputs.
- Phase-0 setup verification passed: `make lint`, `make typecheck`, and `make test`.
- Stubs/placeholders are documented in `ASSUMPTIONS.md`.
- Next: start the long `/goal` run using `GOAL_PROMPT.md`; do not implement later
  phases outside the goal contract.

## 2026-06-29 — Invariant update

- Added non-negotiable invariants to `SPEC.md`, `AGENTS.md`, and `GOAL_PROMPT.md`.
- Added `docs/modules/` notes as required reading before phase work.

## 2026-06-29 — Phase 1 mass properties

- Implemented config-driven vehicle mass properties: parts-to-CG, full inertia tensor
  about the instantaneous CG, propellant/CO2 depletion profiles, propellant position
  profiles, and continuous deployable-leg kinematics.
- Added unit, property-based, regression/golden, and integration tests for Phase 1.
- Verification passed: `make lint`, `make typecheck`, and `make test` (`30 passed`).
- Placeholder BOM values remain assumptions; replace them with measured vehicle data
  before treating outputs as engineering evidence.
- Next: Phase 2 environment model.

## 2026-06-29 — Phase 2 environment

- Implemented data-driven ISA atmosphere, deterministic wind with altitude shear and
  1-cosine gusts, and launch rail constraint/exit-speed reporting.
- Added unit, property-based, regression/golden, and integration tests for Phase 2.
- Verification passed: `make lint`, `make typecheck`, and `make test` (`39 passed`).
- Next: Phase 3 aerodynamics.

## 2026-06-29 — Phase 3 aerodynamics

- Implemented live component build-up aero: CP, Cd, normal-force slope, static margin,
  leg-angle dependence, Mach dependence, depletion-state drag term, and a swing-test
  restoring metric.
- Added OpenRocket CSV anchor ingestion and comparison reporting; anchors remain
  validation inputs only, never the runtime aero source.
- Added unit, property-based, regression/golden, and vehicle-integration tests for Phase 3.
- Verification passed: `make lint`, `make typecheck`, and `make test` (`52 passed`).
- Next: Phase 4 solid motor parsing and mass-flow coupling.

## 2026-06-29 — Ambition note

- Added durable module notes for future CFD validation/refinement and reiterated that
  Renode HIL/emulator work remains a core deliverable, not optional polish.

## 2026-06-29 — Phase 4 solid motor

- Implemented RASP `.eng` and minimal RockSim `.rse` parsing, thrust interpolation,
  trapezoidal total impulse integration, propellant mass-flow, cumulative propellant
  depletion, body-axis thrust vector output, and a vehicle-compatible depletion profile.
- Corrected the placeholder motor header so total mass exceeds propellant mass.
- Added unit, property-based, regression/golden, RSE parsing, and vehicle-coupling tests.
- Verification passed: `make lint`, `make typecheck`, and `make test` (`65 passed`).
- Next: Phase 5 CO2 cold-gas propulsion with CoolProp real-gas/two-phase behavior.

## 2026-06-29 — Phase 5 cold-gas propulsion

- Implemented CoolProp-backed CO2 cold-gas propulsion: saturated liquid/vapor tank state,
  regulator output and sag, choked/subcritical fixed-nozzle flow, evaporative cooling,
  per-nozzle forces/torques, and step-level mass/energy balance reporting.
- Added unit, property-based, regression/golden, and vehicle-coupling tests for Phase 5.
- Verification passed: `make test` (`76 passed`). Final lint/typecheck/full-suite
  verification will be rerun before the Phase 5 commit.
- Cold-gas hardware values remain placeholders; replace them with measured cartridge,
  regulator, and nozzle bench data before treating thrust/temperature outputs as
  engineering evidence.
- Next: Phase 6 fixed-step 6-DOF rigid-body dynamics.

## 2026-06-29 — Phase 6 6-DOF dynamics

- Implemented fixed-step RK4 rigid-body dynamics over inertial position/velocity,
  body-to-inertial quaternion attitude, and body angular rates.
- Added gravity, live wind-relative aero forces/moments, solid-motor thrust, cold-gas
  bang-bang nozzle forces/torques with zero-order-held valve inputs, time-varying
  mass/CG/inertia coupling, mechanical-energy reporting, and deterministic trajectory
  hashing.
- Added strict `config/sim.yaml` validation for dynamics settings and documented the
  RK4/ZOH integration scheme in `docs/modules/dynamics.md`.
- Added unit, property-based, regression/golden, conservation, determinism, and
  integration tests for Phase 6.
- Verification passed: `make lint`, `make typecheck`, and `make test` (`84 passed`).
- Dynamics geometry/settings remain placeholders; replace them with measured thrust-line,
  damping, and application-point data before treating trajectory outputs as engineering
  evidence.
- Next: Phase 7 sensor models with noise on from the start.

## 2026-06-29 — Phase 7 sensors

- Implemented deterministic IMU and barometer sensor models with strict `config/sensors.yaml`
  validation, explicit sample clocks, seeded noise streams, truth-vs-measurement telemetry,
  and disabled ToF/pressure-transducer stubs behind the packet interface.
- IMU model now includes white noise density, fixed bias, bias random walk, per-axis scale
  factors, 3x3 misalignment, saturation, and body-frame specific-force truth from dynamics.
- Barometer model now includes white pressure noise density, pressure bias, bias random
  walk, first-order lag, pressure clamping, and pressure-to-altitude conversion using the
  configured ISA atmosphere.
- Added unit, property-based, regression/golden, noise-statistics, determinism, scheduler,
  and Phase-6 dynamics integration tests for Phase 7.
- Verification passed: `make lint`, `make typecheck`, and `make test` (`98 passed`).
- Sensor calibration/noise values remain placeholders; replace them with device datasheets,
  Allan-variance logs, and bench calibration before treating controller-facing measurements
  as engineering evidence.
- Next: Phase 8 controller interface and native SIL backend, with the first rail-to-touchdown
  end-to-end flight as the keystone.

## 2026-06-29 — Phase 8 controller interface + native SIL

- Implemented the stable `ControllerBackend` seam plus `NativeSILBackend` for Backend A.
  The plant remains decoupled from controller internals.
- Added strict control and actuation config schemas, bang-bang control allocation across
  the three fixed nozzles, sigma-delta duty accumulation, solenoid open/close latency,
  minimum reliable pulse enforcement, and explicit valve fault hooks.
- Implemented `run_native_sil_e2e` and enabled `make e2e`: the runner loads the current
  plant, sensors, controller, motor, cold-gas system, and environment; constrains the
  launch rail until exit; runs fixed-step SIL to touchdown; and emits a partial bundle
  with `telemetry.csv`, `landing_summary.json`, and `run_manifest.json`.
- Gate evidence: `make e2e` reached touchdown and wrote
  `outputs/phase8_sil_seed20260629` (`telemetry_rows=9311`,
  `touchdown_time_s=9.311000000000279`, `max_altitude_m=75.68170089676178`,
  `touchdown_speed_m_s=18.33037340639612`, all reported as DATA).
- Added unit, integration, latency/pulse-floor, CLI dispatch, and end-to-end bundle tests.
- Verification passed: `make lint`, `make typecheck`, `make test` (`105 passed`), and
  `make e2e`.
- SIL control gains, actuation timing, and placeholder vehicle data remain assumptions;
  tune and re-baseline with measured hardware data before treating landing metrics as
  engineering evidence.
- Keystone note: the Phase-8 native-SIL end-to-end flight is now green and must stay green
  before every later commit.
- Next: Phase 9 full telemetry bundle, plots, and 3D animation with nozzle-plume activity.

## 2026-06-29 — Phase 9 data bundle and animation

- Implemented the full Phase 9 data bundle writer. End-to-end SIL runs now emit
  `telemetry.csv`, `telemetry.parquet`, `landing_summary.json`, `landing_summary.csv`,
  `run_manifest.json`, six plot artifacts, `flight_animation.gif`, and
  `flight_animation.html`.
- Expanded telemetry to include acceleration, Euler attitude, AoA, mass properties,
  static margin, dynamic pressure, CG/inertia, per-nozzle thrust and mass flow, CO2
  liquid/vapor mass, tank pressure, cartridge temperature, valve states, controller
  internals, and sensor truth-vs-measurement channels.
- The animation uses the logged trajectory, attitude, and valve telemetry to show vehicle
  motion and nozzle-plume activity. Artifact sanity checks confirmed nonblank plots and an
  89-frame GIF.
- Gate evidence: `make e2e` reached touchdown and wrote
  `outputs/phase8_sil_seed20260629` (`telemetry_rows=9311`,
  `touchdown_time_s=9.311000000000279`, `max_altitude_m=75.68170089676178`,
  `touchdown_speed_m_s=18.33037340639612`, `co2_remaining_kg=0.08082796322160615`,
  all reported as DATA).
- Verification passed: `make lint`, `make typecheck`, `make test` (`107 passed`), and
  `make e2e`.
- MP4 export is deferred because `ffmpeg` is not installed locally; the run manifest and
  `ASSUMPTIONS.md` record this explicitly. Thermal plots and FEA summaries remain deferred
  to Phases 10 and 11.
- Next: Phase 10 lumped-node thermal network on the logged flight.

## 2026-06-29 — Phase 10 thermal network

- Implemented a strict YAML-configured lumped-node thermal network with motor casing,
  foil shield, printed body, carbon frame, solenoids, and electronics bay nodes.
- The post-flight thermal runner consumes logged SIL telemetry, integrates a fixed-step
  transient network, and models configured conduction, motor-to-shield radiation,
  speed-dependent convection, motor thrust-scaled heat, valve-driven solenoid heat, and
  electronics self-heating.
- End-to-end bundles now include `thermal/thermal_timeseries.csv`,
  `thermal/thermal_timeseries.parquet`, `thermal/thermal_summary.json`,
  `plots/thermal_node_temperatures.png`, and
  `plots/thermal_margin_to_limits.png`. The manifest now records thermal artifacts rather
  than deferring them.
- Gate evidence: `make e2e` reached touchdown and wrote
  `outputs/phase8_sil_seed20260629`; the placeholder thermal run reported
  `peak_temperature_deg_c=24.798655538535186`,
  `minimum_margin_deg_c=57.987206409511515`, and no material-limit crossing times
  (all reported as DATA).
- Added unit, property-based, regression/golden, artifact, strict-validation, and e2e
  integration tests for Phase 10.
- Verification passed: `make e2e`, `make lint`, `make typecheck`,
  `tests/test_thermal.py` (`7 passed`), and `make test` (`114 passed`).
- Thermal hardware values remain placeholders; replace them with measured motor,
  structure, material, solenoid, and electronics thermal data before treating temperature
  margins as engineering evidence.
- Next: Phase 11 event-triggered structural load-case extraction and FEA driver.

## 2026-06-29 — Localhost GUI workbench

- Added `rocketsim.gui` plus `make gui` / `rocketsim gui`, serving a localhost workbench
  at `http://127.0.0.1:8765` by default.
- The GUI opens directly into an OpenRocket-style inspection workspace: run tree,
  pipeline tree, metrics, animation, manifest preview, plot tabs, thermal and structural
  summaries, emulator status, right-side inspector, and telemetry preview table.
- The GUI reads the same run bundles and manifests as the CLI; it does not maintain a
  separate truth source. Artifact serving is path-confined to the selected run directory.
- Browser verification passed on localhost: overview, thermal, structural, and emulator
  tabs rendered without horizontal overflow; structural rendered three FEA plots after the
  refreshed e2e bundle.
- Added GUI API and CLI dispatch tests.
- Next GUI work: keep extending the emulator tab during Phase 12 and add run/config
  editing controls only after the underlying config mutation path is tested.

## 2026-06-29 — Phase 11 structural load cases + FEA fallback

- Implemented strict structural config validation, event-triggered load-case extraction,
  and structural artifact writing for landing impact, thrust transient, max-Q, and leg
  deployment cases.
- Added an internal deterministic 3D linear-truss FEA fallback behind the structural
  interface. Because CalculiX/Gmsh/FEniCS are absent locally, the fallback is used and the
  solver status is reported explicitly.
- End-to-end bundles now include `structural/load_cases.json`, `load_cases.csv`,
  `fea_results.csv`, `fea_results.parquet`, `mesh_convergence.csv`,
  `structural_summary.json`, `structural/calculix/landing_impact.inp`, and three FEA
  plots.
- Gate evidence: `make e2e` reached touchdown and wrote
  `outputs/phase8_sil_seed20260629`; the placeholder structural run reported
  `peak_stress_pa=7564674.305064796`,
  `peak_displacement_m=3.287030829274456e-05`, and peak case `landing_impact`
  (all reported as DATA).
- Added unit, property-based, regression/golden, artifact, strict-validation, and e2e
  integration tests for Phase 11.
- Verification passed: `make e2e`, `make lint`, `make typecheck`,
  `tests/test_structural.py` and `tests/test_gui.py` (`10 passed`), the e2e artifact
  test, and `make test` (`124 passed`).
- Structural hardware/solver values remain placeholders; install an external FEA solver
  and replace geometry/material/load assumptions before treating stresses or displacements
  as engineering evidence.
- Next: Phase 12 Renode HIL emulator bring-up, with the GUI emulator tab becoming the
  status surface.

## 2026-06-29 — Localhost GUI definition editor refinement

- Reworked the localhost GUI so the first screen is now a usable Design workspace rather
  than only a run-inspection report. The browser opens directly on the BOM/parts editor,
  which is where the current rocket masses, positions, propellant depletion, CO2 part,
  and deployable-leg kinematics are defined.
- Added a safe workbench API for whitelisted repo files: config YAMLs, the BOM/materials
  inputs, the placeholder motor curve, and the OpenRocket anchor CSV. Saves validate
  through the same pydantic schemas/parsers the sim uses before writing to disk.
- Added a definition-file picker above the editor so the user can switch between BOM,
  vehicle geometry, cold gas, control, sensors, motor, aero, environment, thermal, and
  structural inputs even when the sidebar collapses in the in-app browser.
- Added GUI-triggered native SIL runs via `/api/run/e2e`, keeping the existing output
  bundle as the source of truth for plots, animation, telemetry, thermal, and structural
  data.
- Browser verification on `http://127.0.0.1:8765/` passed: Design opened by default,
  the BOM editor was visible in the current in-app-browser viewport, the definition
  picker switched to `config/coldgas.yaml`, and no horizontal overflow was detected.
- Verification passed: `make lint`, `make typecheck`, `make e2e`, and `make test`
  (`126 passed`).
- Next: resume Phase 12 Renode HIL emulator bring-up, with GUI emulator status becoming
  backed by real bring-up reports.

## 2026-06-29 — Phase 12 Renode HIL bring-up scaffold

- Added strict `config/control.yaml:data.renode` settings for Backend B: Renode executable,
  Python bridge module, ESP32 and Teensy firmware ELFs, `.repl` platform files,
  dual-machine `.resc` script, sensor-injection channels, solenoid GPIO lines,
  Teensy↔ESP32 UART link, sync timeout, and loop-overrun margin.
- Implemented `rocketsim.control.backend_renode`: the swappable `ControllerBackend`
  implementation for Backend B, a HIL preflight/status report, plant sensor-packet
  serialization for Renode injection, and GPIO/PWM actuator-line conversion back to
  bang-bang valve commands. The backend refuses to step when blockers are present rather
  than faking a firmware flight.
- Added `make hil` / `rocketsim hil`, which writes
  `outputs/phase12_renode_hil_status/renode_hil_status.json` and `.md`.
- Added Renode scaffolding under `renode/`: a dual-MCU `.resc` script plus placeholder
  ESP32 and Teensy/i.MX RT1062 `.repl` files. These platform files are intentionally
  marked unverified in config until real board/peripheral bring-up is complete.
- Extended localhost GUI emulator status to read the HIL status report and show Backend-B
  readiness, blockers, components, time-sync values, and next steps.
- Gate evidence: `make hil` generated a blocked status with six exact blockers:
  `renode_executable_missing`, `python_bridge_module_missing`,
  `esp32_firmware_elf_missing`, `esp32_platform_repl_unverified`,
  `teensy_firmware_elf_missing`, and `teensy_platform_repl_unverified`.
- This satisfies the Phase-12 allowed blocker path; no real firmware flight is claimed.
  Required remaining work is to install Renode/pyrenode3, provide real ESP32 and Teensy
  ELFs, replace/verify the board `.repl` models, and then run a real lockstep co-sim.
- Added unit/integration tests for preflight blockers, synthetic ready status, status
  artifact writing, backend-seam refusal, sensor/actuator exchange, CLI dispatch, and GUI
  HIL status API.
- Verification passed: `make hil`, `make e2e`, `make lint`, `make typecheck`, and
  `make test` (`132 passed`).
- Next: commit/push, then proceed to Phase 13 convergence and cross-validation while
  keeping the Backend-B blocker report visible.

## 2026-06-29 — Phase 13 convergence + cross-validation

- Added strict Phase-13 settings to `config/sim.yaml`: integrator timestep ladder,
  matching Renode sync quantum ladder, output directory, landing-metric tolerances,
  ballistic validation duration, and RocketPy requirement flag.
- Added `rocketsim.validation.phase13` and wired `make converge` / `rocketsim converge`.
  The runner reuses the native-SIL plant with explicit timing overrides, writes a
  convergence table, convergence plot, OpenRocket comparison CSV, cross-validation JSON,
  and Phase-13 manifest under `outputs/phase13_convergence/`.
- Gate evidence: `make converge` ran three full SIL flights at dt/quantum
  `0.002`, `0.001`, and `0.0005` seconds. Against the finest run, the largest reported
  touchdown-speed delta was `0.0037717697974422038 m/s`; the largest touchdown-time delta
  was `0.0010000000003920206 s`. These are convergence DATA, not physics verdicts.
- Cross-validation evidence: analytic no-thrust ballistic position error norm was
  `7.835405111758318e-13 m`, velocity error norm was
  `1.5845103007450234e-12 m/s`, and the configured OpenRocket frozen anchors were all
  within tolerance.
- RocketPy is not installed locally, so RocketPy passive-ascent comparison is documented
  as `unavailable_documented` in `cross_validation.json` and `ASSUMPTIONS.md`; no
  RocketPy match is claimed.
- Added unit/integration tests for Phase-13 config, convergence delta reporting,
  artifact writing, ballistic cross-validation, and CLI dispatch.
- Verification passed: `make converge`, `make lint`, `make typecheck`, and `make test`
  (`138 passed`).
- Next: commit/push, then proceed to Phase 14 Monte Carlo at scale.

## 2026-06-29 — Phase 14 Monte Carlo framework + native-SIL smoke

- Added strict Phase-14 settings under `config/sim.yaml:data.phase14`, including the
  production `target_runs: 1000`, 100-run batch size, percentile stability tolerance,
  retained-bundle stride, histogram bins, and dispersions over wind, mass scale, CG shift,
  nozzle cant, valve latency, and sensor seed.
- Added `rocketsim.validation.phase14` and wired `make montecarlo` / `rocketsim
  montecarlo`. The runner uses `numpy.random.SeedSequence.spawn` from the master seed,
  copies config/input YAML into a per-scenario temp repo, applies the dispersions there,
  then calls the same native-SIL flight runner used by the Phase-8 keystone.
- Extended the native-SIL landing summary with touchdown x/y, lateral error, and tilt so
  Monte Carlo distributions can be computed from real flight summaries rather than a
  separate reporting path.
- Added Phase-14 artifacts: `montecarlo_samples.csv`, `montecarlo_samples.parquet`,
  metric histograms, `stability_table.csv`, `montecarlo_summary.json`, and
  `phase14_manifest.json` under `outputs/phase14_montecarlo/`.
- Smoke evidence: `ROCKETSIM_MC_RUNS=4 make montecarlo` ran four real native-SIL flights,
  retained one full bundle, and wrote the Phase-14 manifest. The summary correctly reports
  `gate_complete: false` and `stability.status: insufficient_batches`; this is a pilot
  verification, not the full 1000-run Phase-14 gate.
- Smoke distributions, reported as data only: landing-speed mean
  `16.627659924215486 m/s`, touchdown-tilt mean `124.39096051083646 deg`,
  lateral-error mean `35.3073011297847 m`, and CO2-remaining mean
  `0.08333835746783905 kg`.
- Added unit/integration tests for Phase-14 config, deterministic spawned scenarios,
  YAML dispersion application, distribution summaries, artifact writing, and CLI dispatch.
- Verification passed: `make lint`, `make typecheck`, and `make test` (`144 passed`).
- Next: run the full un-overridden `make montecarlo` large-N study to the configured
  target and stability criteria, then commit a gate-complete progress entry only if it
  actually stabilizes.

## 2026-06-29 — Phase 14 Monte Carlo artifact scaling

- Split the native-SIL runner into a shared `_simulate_native_sil` physics core plus two
  artifact writers: the existing full Phase-9/10/11 bundle path and a new metrics-only
  summary path for non-retained Monte Carlo scenarios.
- Updated Phase 14 so retained scenarios still write complete bundles, while non-retained
  scenarios write only `landing_summary.json`, `landing_summary.csv`, and a manifest that
  explicitly marks telemetry, plots, animation, thermal, and structural artifacts as
  deferred by metrics-only mode.
- Smoke evidence: `ROCKETSIM_MC_RUNS=4 make montecarlo` ran four native-SIL flights with
  one retained full bundle and three metrics-only scenarios. The sample table reports
  `artifact_mode` as `full_bundle, metrics_only, metrics_only, metrics_only`; the summary
  still correctly reports `gate_complete: false` and `stability.status:
  insufficient_batches`.
- The Phase-14 distribution values for the 4-run smoke were unchanged from the prior smoke
  because the physics path is shared; only artifact writing changed.
- Verification passed: focused Phase-8/Phase-14 tests, `make lint`, `make typecheck`, and
  `make test` (`146 passed`).
- Next: run a larger pilot batch and then the full un-overridden 1000-run Monte Carlo
  study when ready; do not claim the Phase-14 gate until target count and percentile
  stability criteria both hold.

## 2026-06-29 — Phase 14 Monte Carlo resume + checkpoints

- Added strict Phase-14 resume/checkpoint settings: `resume_enabled: true` and
  `checkpoint_interval_runs: 25`.
- Added a deterministic resume signature based on master seed, nozzle count,
  retained-bundle stride, and dispersion settings. Existing `montecarlo_samples.csv`
  rows are reused only when the signature matches, so stale rows from older settings do
  not silently contaminate a study.
- The Phase-14 runner now writes complete sample/parquet/summary/stability/manifest and
  histogram artifacts at checkpoints as well as at the final requested count. This makes a
  long 1000-run study recoverable after interruption.
- Added `ROCKETSIM_MC_RESUME=0` as a clean-rerun override for smoke tests or deliberate
  restarts without changing the production YAML.
- Smoke evidence: `ROCKETSIM_MC_RUNS=2 ROCKETSIM_MC_RESUME=0 make montecarlo` produced two
  fresh runs, then `ROCKETSIM_MC_RUNS=3 make montecarlo` resumed those rows and added only
  the missing third run. The summary recorded `runs_completed: 3`, `requested_runs: 3`,
  `resumed_rows: 2`, `resume_enabled: true`, and a 64-character `phase14_signature`.
- The resumed smoke sample table reported artifact modes
  `full_bundle, metrics_only, metrics_only`; the Phase-14 gate remained correctly
  incomplete with `stability.status: insufficient_batches`.
- Added tests for config fields, resume-signature propagation, resume skipping of
  completed indices, and Parquet-safe sample column normalization.
- Verification passed: focused Phase-14 tests, `make lint`, `make typecheck`, and
  `make test` (`147 passed`).
- Next: use the checkpointed runner for a larger pilot batch, then allow the un-overridden
  1000-run study to accumulate to stability.

## 2026-06-29 — Phase 14 bounded batch accumulation

- Added `max_new_runs_per_invocation` to the strict Phase-14 config, defaulting to `0`
  for unlimited production runs.
- Added `ROCKETSIM_MC_MAX_NEW_RUNS=<N>` so the requested total study size can remain large
  while a single invocation adds only the next N missing deterministic scenarios, writes
  checkpoint artifacts, and exits cleanly.
- The Phase-14 summary now records `new_rows_completed`, `max_new_runs_per_invocation`,
  and `invocation_limited`, making partial accumulation explicit in the manifest and
  summary JSON.
- Real command smoke evidence: with an existing 3-row resumed study,
  `ROCKETSIM_MC_RUNS=5 ROCKETSIM_MC_MAX_NEW_RUNS=1 make montecarlo` added one new native-SIL
  metrics-only scenario and stopped at `runs_completed: 4`, `requested_runs: 5`,
  `resumed_rows: 3`, `new_rows_completed: 1`, and `invocation_limited: true`.
- Added tests for the config field and for bounded invocation behavior with a fake runner.
- Stabilized the thermal property test by disabling Hypothesis' wall-clock deadline for
  the no-source ambient-invariance property; the physical assertion remains unchanged.
- Verification passed: focused Phase-14/thermal tests, `make lint`, `make typecheck`, and
  `make test` (`148 passed`).
- Next: run bounded batches toward the full Phase-14 large-N target, then only mark the
  gate complete once target count and percentile stability criteria are both satisfied.

## 2026-06-29 — Localhost Monte Carlo workbench controls

- Added `/api/montecarlo-status`, `/api/run/montecarlo`, and safe
  `/montecarlo-artifacts/<histogram>` routes to the localhost GUI server.
- The new GUI Monte Carlo tab shows accumulated rows vs target, requested rows, rows added
  in the last invocation, resumed rows, stability status, gate status, retained bundles,
  signature, key percentiles, and histogram plots.
- Added bounded-batch controls in the GUI: requested total rows, max new rows for this
  click, and resume toggle. The POST route passes explicit overrides into the Phase-14
  runner, avoiding global environment mutation.
- Browser verification on `http://127.0.0.1:8765/` passed after restarting the local GUI:
  the Monte Carlo tab rendered, showed `4 / 1000` rows, `requested: 5`, `added last run:
  1`, `resumed rows: 3`, four histogram images, and no horizontal page overflow.
- Added GUI API tests for Monte Carlo status/artifact routes and bounded-run POST
  overrides.
- Verification passed: focused GUI/Phase-14 tests, `make lint`, `make typecheck`, and
  `make test` (`150 passed`).
- Next: use the GUI/CLI bounded batch path to accumulate more real Phase-14 runs toward
  the 1000-run target, then only claim the gate when target count and stability criteria
  both hold.

## 2026-06-29 — Phase 14 bounded batch accumulation to 6 rows

- Ran a real bounded Phase-14 native-SIL Monte Carlo accumulation:
  `ROCKETSIM_MC_RUNS=6 ROCKETSIM_MC_MAX_NEW_RUNS=2 make montecarlo`.
- The runner resumed the existing four rows, added two new metrics-only native-SIL
  scenarios, and rewrote the Phase-14 samples, parquet, summary, stability table,
  manifest, and histogram artifacts.
- Updated evidence from `outputs/phase14_montecarlo/montecarlo_summary.json`:
  `runs_completed: 6`, `requested_runs: 6`, `resumed_rows: 4`,
  `new_rows_completed: 2`, `invocation_limited: true`, and
  `stability.status: insufficient_batches`.
- Sample rows now cover run indices `[0, 1, 2, 3, 4, 5]` with one retained full bundle
  and five metrics-only runs. The Phase-14 gate remains open; this is accumulation
  progress, not statistical completion.
- Current six-row distributions, reported as data only: landing-speed mean
  `17.53958816775415 m/s` with p95 `24.248842529308494 m/s`; touchdown-tilt mean
  `123.12274892226674 deg` with p95 `171.42516690940585 deg`; lateral-error mean
  `42.57381344081731 m` with p95 `89.84600830800028 m`; CO2-remaining mean
  `0.08301231697852536 kg` with p5 `0.07975106459927324 kg`.
- No code changed in this batch; the previous green suite remains the code verification
  baseline for this progress-only checkpoint.
- Next: continue bounded batches toward the first full 100-run batch, then toward the
  configured 1000-run target and percentile-stability criteria.

## 2026-06-29 — Phase 14 bounded batch accumulation to 8 rows

- Ran another real bounded Phase-14 native-SIL Monte Carlo accumulation:
  `ROCKETSIM_MC_RUNS=8 ROCKETSIM_MC_MAX_NEW_RUNS=2 make montecarlo`.
- The runner resumed the existing six rows, added two new metrics-only native-SIL
  scenarios, and rewrote the Phase-14 samples, parquet, summary, stability table,
  manifest, and histogram artifacts.
- Updated evidence from `outputs/phase14_montecarlo/montecarlo_summary.json`:
  `runs_completed: 8`, `requested_runs: 8`, `resumed_rows: 6`,
  `new_rows_completed: 2`, `invocation_limited: true`, and
  `stability.status: insufficient_batches`.
- Sample rows now cover run indices `[0, 1, 2, 3, 4, 5, 6, 7]` with one retained full
  bundle and seven metrics-only runs. The Phase-14 gate remains open; this is accumulation
  progress, not statistical completion.
- Current eight-row distributions, reported as data only: landing-speed mean
  `17.846358797613256 m/s` with p95 `24.21107436731584 m/s`; touchdown-tilt mean
  `121.96721084393185 deg` with p95 `170.10789458727413 deg`; lateral-error mean
  `46.08744820281885 m` with p95 `94.49141809216196 m`; CO2-remaining mean
  `0.08298488862109477 kg` with p5 `0.07985653296539368 kg`.
- No code changed in this batch; this is a progress-only compute checkpoint.
- Next: continue bounded batches toward the first full 100-run batch, then toward the
  configured 1000-run target and percentile-stability criteria.

## 2026-06-29 — Localhost rocket definition UX repair

- Reworked the localhost Design view so the first screen is explicitly centered on
  `Rocket Definition`, with a top-level `Define Rocket` action and visible source cards
  for BOM/parts, body geometry, CO2/nozzles, motor curve, aero, controller, sensors, and
  runtime settings.
- Added direct editing affordances for the real whitelisted source files: `Paste Into
  Editor` scrolls to and selects the current YAML/CSV/ENG text area, `Import File` loads a
  local text file into the editor, and `Copy Path` exposes the repo path for the selected
  definition file.
- Cleaned up the OpenRocket-style workbench layout: Design hides the telemetry pane while
  editing, the page uses a real header/workspace grid instead of fixed height guesses, the
  source cards stay compact at laptop width, and the editor now uses a light engineering
  surface instead of a code-demo dark block.
- Browser verification on `http://127.0.0.1:8765/` passed at an 817 px-wide viewport:
  Design opened by default, no horizontal overflow was detected, telemetry was hidden in
  Design, `Paste Into Editor` focused and selected the BOM editor, and `Define Rocket`
  returned from Monte Carlo to the BOM editor.
- Verification passed: `tests/test_gui.py` (`7 passed`), `make lint`, `make typecheck`,
  and `make test` (`150 passed`).
- Next: keep using the GUI as the operator-facing surface while Phase-14 accumulation
  continues and while later Renode/emulator status grows into real firmware bring-up.

## 2026-06-29 — Phase 14 per-row checkpointing and 9-row accumulation

- Changed `config/sim.yaml:data.phase14.checkpoint_interval_runs` from `25` to `1`, so
  every newly completed Monte Carlo scenario writes resumable samples, parquet, summary,
  stability, manifest, and histogram artifacts before the next scenario starts.
- Updated the Phase-14 config contract test and `docs/modules/sim.md` to make per-row
  checkpointing the documented production behavior for the long 1000-run study.
- Ran a real bounded Phase-14 native-SIL Monte Carlo accumulation:
  `ROCKETSIM_MC_RUNS=9 ROCKETSIM_MC_MAX_NEW_RUNS=1 make montecarlo`.
- The runner resumed the existing eight rows, added one new metrics-only native-SIL
  scenario, and rewrote the Phase-14 samples, parquet, summary, stability table,
  manifest, and histogram artifacts.
- Updated evidence from `outputs/phase14_montecarlo/montecarlo_summary.json`:
  `runs_completed: 9`, `requested_runs: 9`, `resumed_rows: 8`,
  `new_rows_completed: 1`, `invocation_limited: true`,
  `checkpoint_interval_runs: 1`, and `stability.status: insufficient_batches`.
- Sample rows now cover run indices `[0, 1, 2, 3, 4, 5, 6, 7, 8]` with one retained full
  bundle and eight metrics-only runs. The Phase-14 gate remains open; this is
  accumulation progress, not statistical completion.
- Current nine-row distributions, reported as data only: landing-speed mean
  `17.693453498367074 m/s` with p95 `24.192190286319516 m/s`; touchdown-tilt mean
  `125.59823134397831 deg` with p95 `169.4492584262083 deg`; lateral-error mean
  `44.0379305701193 m` with p95 `94.35740468483398 m`; CO2-remaining mean
  `0.08311738852140595 kg` with p5 `0.07990926714845391 kg`.
- Verification passed: `tests/test_phase14_validation.py` (`9 passed`), `make lint`,
  `make typecheck`, and `make test` (`150 passed`).
- Next: continue bounded batches toward the first full 100-run batch, then toward the
  configured 1000-run target and percentile-stability criteria.

## 2026-06-29 — Phase 14 bounded batch accumulation to 15 rows

- Ran another real bounded Phase-14 native-SIL Monte Carlo accumulation:
  `ROCKETSIM_MC_RUNS=15 ROCKETSIM_MC_MAX_NEW_RUNS=6 make montecarlo`.
- The runner resumed the existing nine rows, added six new metrics-only native-SIL
  scenarios, and rewrote the Phase-14 samples, parquet, summary, stability table,
  manifest, and histogram artifacts. Per-row checkpointing remained active throughout
  with `checkpoint_interval_runs: 1`.
- Updated evidence from `outputs/phase14_montecarlo/montecarlo_summary.json`:
  `runs_completed: 15`, `requested_runs: 15`, `resumed_rows: 9`,
  `new_rows_completed: 6`, `invocation_limited: true`, `gate_complete: false`, and
  `stability.status: insufficient_batches`.
- Sample rows now cover run indices
  `[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]` with one retained full bundle
  and fourteen metrics-only runs. The Phase-14 gate remains open; this is accumulation
  progress, not statistical completion.
- Current fifteen-row distributions, reported as data only: landing-speed mean
  `17.595179628101718 m/s`, p50 `15.011606715590931 m/s`, p95
  `24.55587761745139 m/s`; touchdown-tilt mean `121.50542272263526 deg`, p50
  `145.36404120952346 deg`, p95 `170.75457169559948 deg`; lateral-error mean
  `41.500352864709285 m`, p50 `24.347057839815754 m`, p95
  `93.55332424086605 m`; CO2-remaining mean `0.08347049361771289 kg`, p5
  `0.08022567224681525 kg`, p50 `0.0844123227374394 kg`.
- Verification passed: `tests/test_phase14_validation.py` (`9 passed`). No source code
  changed in this batch beyond this progress log.
- Next: continue smaller bounded batches with frequent GitHub saves toward the first
  full 100-run batch, then toward the configured 1000-run target and stability criteria.

## 2026-06-29 — Phase 14 bounded batch accumulation to 20 rows

- Ran another real bounded Phase-14 native-SIL Monte Carlo accumulation:
  `ROCKETSIM_MC_RUNS=20 ROCKETSIM_MC_MAX_NEW_RUNS=5 make montecarlo`.
- The runner resumed the existing fifteen rows, added five new metrics-only native-SIL
  scenarios, and rewrote the Phase-14 samples, parquet, summary, stability table,
  manifest, and histogram artifacts with per-row checkpointing still active.
- Updated evidence from `outputs/phase14_montecarlo/montecarlo_summary.json`:
  `runs_completed: 20`, `requested_runs: 20`, `resumed_rows: 15`,
  `new_rows_completed: 5`, `invocation_limited: true`, `gate_complete: false`, and
  `stability.status: insufficient_batches`.
- Sample rows now cover run indices `0..19` with one retained full bundle and nineteen
  metrics-only runs. The Phase-14 gate remains open; this is accumulation progress, not
  statistical completion.
- Current twenty-row distributions, reported as data only: landing-speed mean
  `17.177205280216533 m/s`, p50 `15.01215658818257 m/s`, p95
  `24.378698714817002 m/s`; touchdown-tilt mean `122.6649915590662 deg`, p50
  `133.37194765596308 deg`, p95 `169.33893740305103 deg`; lateral-error mean
  `38.37748361331272 m`, p50 `24.27852344951543 m`, p95 `92.8832572042261 m`;
  CO2-remaining mean `0.08378231546585926 kg`, p5 `0.08048934316211638 kg`, p50
  `0.08454346625175185 kg`.
- Verification passed: `tests/test_phase14_validation.py` (`9 passed`). No source code
  changed in this batch beyond this progress log.
- Next: keep adding small bounded batches with frequent GitHub saves; the next retained
  full bundle appears at run index 25, and the Phase-14 gate still requires the configured
  1000-run target plus percentile-stability criteria.

## 2026-06-29 — Phase 14 retained-bundle milestone and status metadata

- Added retained-bundle progress metadata to Phase-14 summaries/manifests:
  `next_retained_bundle_index` and `rows_until_next_retained_bundle`, alongside the
  existing `retained_bundles` and stride fields.
- Updated the localhost Monte Carlo tab to show the next full retained bundle and rows
  until that full-bundle artifact, so long operator runs expose when the next expensive
  full bundle will be produced.
- Added tests for Phase-14 status metadata and updated the GUI Monte Carlo fixture/docs.
- Ran a real bounded Phase-14 native-SIL Monte Carlo accumulation:
  `ROCKETSIM_MC_RUNS=26 ROCKETSIM_MC_MAX_NEW_RUNS=6 make montecarlo`.
- The runner resumed the existing twenty rows, added six new scenarios, and retained a
  new full Phase-9/10/11 bundle at run index `25`:
  `phase14_mc0025_seed3576018127`.
- Updated evidence from `outputs/phase14_montecarlo/montecarlo_summary.json`:
  `runs_completed: 26`, `requested_runs: 26`, `resumed_rows: 20`,
  `new_rows_completed: 6`, `retained_bundles: 2`, `gate_complete: false`,
  `stability.status: insufficient_batches`, `next_retained_bundle_index: 50`, and
  `rows_until_next_retained_bundle: 25`.
- Sample rows now cover run indices `0..25`, with retained full bundles at indices `0`
  and `25`, and twenty-four metrics-only rows. The Phase-14 gate remains open; this is
  accumulation progress, not statistical completion.
- Current twenty-six-row distributions, reported as data only: landing-speed mean
  `16.83534882468199 m/s`, p50 `14.60459400833898 m/s`, p95
  `24.87479964219329 m/s`; touchdown-tilt mean `122.29191170604979 deg`, p50
  `133.37194765596308 deg`, p95 `168.80028931119534 deg`; lateral-error mean
  `36.18417575511597 m`, p50 `22.30350360439987 m`, p95 `90.25415403648407 m`;
  CO2-remaining mean `0.08386619526093891 kg`, p5 `0.08059663770486868 kg`, p50
  `0.08458005942216165 kg`.
- Verification passed: focused Phase-14/GUI tests (`17 passed`), `make lint`,
  `make typecheck`, and `make test` (`151 passed`).
- Next: continue bounded accumulation toward retained bundle index `50`, then toward the
  configured 1000-run target and percentile-stability criteria.
