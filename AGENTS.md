# Repository Instructions

This repository is governed by `SPEC.md`. Before writing code, read `SPEC.md` in full and
treat it as the source of truth for scope, architecture, verification, and guardrails.

## Operating Rules

- Non-negotiable invariants apply on every phase, regardless of which file is open:
  real-gas CO2 via CoolProp, live aero CP/Cd, fixed-step RK4 with zero-order-hold valve
  states, bang-bang fixed nozzles, event-triggered FEA only, swappable `ControllerBackend`,
  rigorous tests over speed, sacred determinism, physics outputs as data only, no silent
  stubs, and no gold-plating early phases.
- Keep the project ambitious: Renode ESP32 + Teensy HIL, Backend A/B cross-checks, and
  offline CFD validation/refinement are expected major capabilities as the phases mature.
  Do not shrink the final simulation into a small toy because early phases are simpler.
- Work phases in `SPEC.md` section 4, in order.
- Before building each phase, read `SPEC.md` and the relevant `docs/modules/*.md`.
- Do not start a later phase until the prior phase gate is green, or a specific blocker
  has been documented in `PROGRESS.md` and the stub is documented in `ASSUMPTIONS.md`.
- Once Phase 8 produces a green end-to-end SIL flight, keep it green. Run the full test
  suite before every commit.
- For parallel Monte Carlo, derive streams from the master seed with `SeedSequence.spawn`;
  same seed must imply an identical telemetry hash.
- Never assert pass/fail on physics outcomes such as landing speed, tilt, CO2 remaining,
  temperatures, or stresses. Emit those values as data and plots.
- Keep physical and scenario parameters in YAML configuration, not hardcoded in code.
- Every placeholder or stub must be visible in `ASSUMPTIONS.md` and `PROGRESS.md`.
- Use the local `.venv` once created. Preferred commands are exposed in `Makefile`.
- Commit and push to `main` after every green phase gate or setup milestone.

## Phase-0 Commands

```bash
make lint
make typecheck
make test
```

The long `/goal` run should use `GOAL_PROMPT.md` and continue from this scaffold.
