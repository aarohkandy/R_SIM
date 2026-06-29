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
