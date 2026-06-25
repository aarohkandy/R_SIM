# Requirements

## User Workflow

- Define a rocket with structural parts, fins, motor data, mass, CG, and launch conditions.
- Define an active air system with pressure source, valves, actuator geometry, deployment location, and surface limits.
- Write controller code that receives simulated sensor data and commands the active system.
- Add deterministic or seeded noise for sensors, atmosphere, actuator response, and pressure behavior.
- Run a simulation and inspect trajectory, stability, controller, actuator, and pressure outputs.

## Current Requirements

- Setup instructions must work locally on this machine.
- Validation must fail loudly when a dependency, endpoint, or result shape is wrong.
- Local simulation must be deterministic and labeled as active pneumatic local dynamics.
- Fake/random placeholder output must not be accepted as a passing main workflow result.
- C++ controller code must compile before it is used by an active simulation.
- Pneumatic outputs must show pressure use, actuator movement, and surface deployment when active control commands it.
