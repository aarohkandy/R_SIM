# R_SIM Active Rocket Goal

This repository is being turned into a ready-to-use active rocket simulator. The current local model supports rocket geometry, motor data, launch conditions, a pneumatic airbrake system, C++ controller code, seeded noise, and structured flight/pressure/actuator results.

## Future `/goal` Command

Use this command to continue the long implementation goal:

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

## Definition Of Done

- The workspace is based on `aarohkandy/R_SIM`.
- The frontend installs, builds, and lints from a clean checkout.
- The backend installs in a clean Python environment and passes smoke tests.
- A user can define rocket structure, motor data, launch weather, pneumatic air-system values, controller code, and noise settings.
- A sample active pneumatic rocket simulation completes through the main API.
- Output includes trajectory, attitude, drag, dynamic pressure, tank pressure, actuator pressure, valve command, surface deployment, controller history, warnings, and exportable results.
- Local simulation output is deterministic, structured, and labeled as `active_pneumatic_local_dynamics`.
- Cloud/GCP/OpenFOAM paths are future calibration integrations and must not be required for local use.
