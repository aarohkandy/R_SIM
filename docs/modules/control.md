# Control Notes

- Keep the `ControllerBackend` seam swappable between native SIL and Renode HIL.
- The plant must not import controller internals.
- Once Phase 8 SIL end-to-end flight is green, the full suite must pass before every
  commit and later phases may not regress it.

## Phase 8 Implementation Notes

- `ControllerBackend` is the stable seam: `reset(seed)`, `step(sensor_packet, t)`, and
  `telemetry()`. The physics plant does not import backend internals.
- `NativeSILBackend` implements the fast Backend A path. It estimates altitude/descent
  rate from barometer packets, uses IMU acceleration/gyro terms for a baseline attitude
  damping demand, queues commands through a configured latency+jitter model, and emits
  bang-bang valve commands.
- The Phase 8 PD gains are placeholders in `config/control.yaml`. Physics outputs from
  the resulting flight are data, not a statement that the vehicle lands softly.
