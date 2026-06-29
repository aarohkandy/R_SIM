# Firmware

Add the real ESP32 and Teensy firmware sources or ELF binaries here for Phase 12.

Phase 0 intentionally provides no firmware placeholder binary. The missing firmware is
documented in `ASSUMPTIONS.md` and must become either real input or a logged Renode blocker.

Expected default ELF names, configured in `config/control.yaml`:

- `firmware/esp32_flight.elf`
- `firmware/teensy_flight.elf`

These must be the real, unmodified flight firmware artifacts for Backend B. Do not replace
them with dummy binaries just to clear the `make hil` preflight; the whole point of Phase
12 is to run the actual firmware against the plant.
