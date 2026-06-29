# Renode Notes

- Renode HIL must run the real firmware binaries when available.
- If board bring-up blocks, keep the backend interface and document the exact blocker in
  `PROGRESS.md` and any stub in `ASSUMPTIONS.md`.
- Backend A/B divergence is data to quantify in Phase 16.

## Phase 12 Implementation Notes

- `config/control.yaml:data.renode` declares the two machines, expected firmware ELFs,
  platform `.repl` files, dual-machine `.resc` script, Python bridge module, sensor
  injection channels, solenoid actuator lines, inter-MCU link, and loop-overrun margin.
- `rocketsim.control.backend_renode` implements the Backend-B seam, HIL preflight report,
  sensor-packet serialization, and actuator-line conversion. It refuses to step firmware
  while blockers are present; it does not silently return closed valves as a fake flight.
- `make hil` / `rocketsim hil` writes `outputs/phase12_renode_hil_status/` with JSON and
  Markdown reports. A blocked report is a valid Phase-12 gate artifact only when the
  blockers are exact and actionable.
- Current Renode `.resc` and `.repl` files are scaffolds. They are intentionally marked
  unverified in config until real ESP32 and Teensy/i.MX RT1062 peripherals are brought up.
- The planned lockstep scheme is documented in `docs/time_sync.md`.
