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
