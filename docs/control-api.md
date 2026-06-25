# Control API

## Controller Interface

The backend compiles C++ controller code using this required signature:

```cpp
ControlOutput control_function(SensorData sensor_data)
```

The active simulation can execute compiled C++ controller code during a run. The controller reads flight and pneumatic sensor fields and returns valve/surface commands.

## Controller Inputs

- Time, altitude, velocity, acceleration, attitude, angular rates.
- Pressure, temperature, battery or power state.
- Active-system pressure and actuator state.
- Configurable sensor noise and delay.

## Controller Outputs

- Pneumatic valve commands.
- Surface target position or deployment command.
- Recovery trigger.
- Data logging fields.

## Safety Constraints

- Controller execution must be sandboxed.
- User code may use the generated `SensorData`, `ControlOutput`, `std::map`, `std::string`, and math helpers already provided by the wrapper.
- User code may not add preprocessor directives such as `#include`, `#define`, or `#pragma`.
- Dangerous filesystem, process, console I/O, dynamic allocation, thread, and unbounded-loop patterns must remain blocked before compilation.
- Compile and runtime timeouts must be enforced.
- Runtime output must be finite and clamped to hardware/control limits before it can drive the active system.
- Compile and runtime errors must return clear messages to the user.
