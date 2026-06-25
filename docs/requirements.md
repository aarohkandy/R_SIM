# Requirements

## Prep Scope

The prep pass makes the repo dependable enough for a later overnight `/goal`. It does not implement the full active pneumatic rocket simulator yet.

## User Workflow For The Later Goal

- Define a rocket with structural parts, fins, motor data, mass, CG, and launch conditions.
- Define an active air system with pressure source, valves, actuator geometry, deployment location, and surface limits.
- Write controller code that receives simulated sensor data and commands the active system.
- Add deterministic or seeded noise for sensors, atmosphere, actuator response, and pressure behavior.
- Run a simulation and inspect trajectory, stability, controller, actuator, and pressure outputs.

## Prep Requirements

- Setup instructions must work locally on this machine.
- Validation must fail loudly when a dependency, endpoint, or result shape is wrong.
- Local smoke simulation may be simplified, but it must be deterministic and labeled as local pre-goal physics.
- Fake/random placeholder output must not be accepted as a passing main workflow result.

