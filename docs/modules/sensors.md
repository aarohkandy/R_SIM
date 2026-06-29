# Sensors Notes

- Sensor noise is on from the first real sensor phase and must be seed-driven.
- IMU/barometer models need unit, property-based, regression, and integration tests before
  their gate passes.
- Sensor truth-vs-measurement plots are data products, not verdicts.

## Phase 7 Implementation Notes

- `rocketsim.sensors` models the controller-facing packet layer separately from the plant.
  The plant emits `SensorTruth`; the sensor suite emits sampled IMU/barometer packets.
- IMU measurements include configurable white noise density, fixed bias, bias random walk,
  per-axis scale factor, a 3x3 misalignment matrix, and saturation. Accelerometer truth is
  specific force in the body frame, computed from plant acceleration minus gravity.
- Barometer measurements include configurable pressure noise density, pressure bias,
  pressure-bias random walk, first-order lag, pressure clamping, and pressure-to-altitude
  conversion using the configured ISA atmosphere parameters.
- Sample clocks are explicit: IMU and barometer readings are emitted only when their
  configured MCU-rate sample periods are due. Deferred ToF and pressure-transducer sensors
  stay behind explicit disabled stubs.
- Stochastic terms use named RNG streams derived from the master seed, so identical seeds
  produce identical sensor packet hashes.
