# R_SIM Active Rocket Goal Prep

This repository is being prepared for a later long-running `/goal` session. The prep work is complete when the app can be installed, checked, and smoke-tested locally without relying on fake cloud output or missing environment assumptions.

## Future `/goal` Command

Use this only after `docs/validation.md` passes:

```text
/goal Make this repo a ready-to-use active rocket simulator per ./GOAL.md. The goal is complete only when a user can define a rocket, pneumatic active air system, controller code, noise/environment settings, run a simulation, and view/export realistic flight results that pass ./docs/validation.md.
```

## Linked Specs

- [Requirements](docs/requirements.md)
- [Simulation model](docs/simulation-model.md)
- [Pneumatics](docs/pneumatics.md)
- [Control API](docs/control-api.md)
- [UI workflows](docs/ui-workflows.md)
- [Validation](docs/validation.md)
- [Progress log](docs/progress-log.md)

## Prep Definition Of Done

- The workspace is based on `aarohkandy/R_SIM`.
- The frontend installs, builds, and lints from a clean checkout.
- The backend installs in a clean Python environment and passes smoke tests.
- A sample rocket with a motor, body, fins, and controller code can run through the main local simulation API.
- Simulation output is structured and deterministic, with local smoke output clearly labeled instead of presented as CFD.
- Known cloud/GCP paths are documented as future integrations, not required for pre-goal readiness.

