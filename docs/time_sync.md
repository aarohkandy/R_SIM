# Time Sync

The native SIL path runs one deterministic fixed-step plant clock:

- plant integration step: `config/sim.yaml:data.integrator_dt_s`
- controller period: `1 / config/control.yaml:data.loop_rate_hz`
- valve state: zero-order-held inside each fixed plant step

Backend B uses the same plant clock. Renode advances in deterministic virtual-time
chunks equal to `config/sim.yaml:data.renode_sync_quantum_s`; the plant advances by the
same interval, then sensor and actuator data are exchanged at the boundary.

The intended lockstep boundary for every quantum is:

1. Serialize the latest plant truth and sensor readings with
   `sensor_packet_to_injection_frame`.
2. Inject IMU/barometer/deferred sensor channels into the Teensy-side virtual peripherals
   through the Renode External Control API or RESD-backed stream.
3. Advance Renode virtual time by one quantum.
4. Read Teensy GPIO/PWM solenoid lines and convert them with `actuator_levels_to_valves`.
5. Advance the fixed-step plant using those bang-bang valve states.
6. Record loop execution timing; flag any firmware loop body that exceeds its configured
   period plus `config/control.yaml:data.renode.loop_overrun_margin_s`.

`make hil` verifies the current configuration is coherent enough to attempt that loop.
As of Phase 12 scaffold bring-up, local blockers are documented in the generated status
bundle rather than silently falling back to SIL.
