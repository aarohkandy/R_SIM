# Control API

## Prep Controller Interface

The current backend compiles C++ controller code using this required signature:

```cpp
ControlOutput control_function(SensorData sensor_data)
```

The pre-goal smoke test verifies that a minimal controller compiles successfully.

## Future Controller Inputs

- Time, altitude, velocity, acceleration, attitude, angular rates.
- Pressure, temperature, battery or power state.
- Active-system pressure and actuator state.
- Configurable sensor noise and delay.

## Future Controller Outputs

- Pneumatic valve commands.
- Surface target position or deployment command.
- Recovery trigger.
- Data logging fields.

## Safety Constraints

- Controller execution must be sandboxed.
- Dangerous filesystem/process operations must remain blocked.
- Timeouts must be enforced.
- Compile and runtime errors must return clear messages to the user.

