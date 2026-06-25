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
- Dangerous filesystem/process operations must remain blocked.
- Timeouts must be enforced.
- Compile and runtime errors must return clear messages to the user.
