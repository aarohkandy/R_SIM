# Actuation Notes

- Solenoid commands are finite-latency bang-bang valve states with a minimum reliable pulse.
- Control allocation may provide collective thrust and two torque axes with pure axial
  nozzles; roll authority is only available through modeled cant/misalignment choices.
- Faults and stubs must be explicit and logged.

## Phase 8 Implementation Notes

- `ControlAllocator` maps normalized collective + two-axis torque demand onto the three
  fixed axial nozzles using the configured nozzle positions. Pure axial nozzles provide no
  direct roll authority; roll requires cant/misalignment in later studies.
- `SolenoidValveBank` models open/close latency, a minimum reliable pulse floor, and
  explicit stuck-open/stuck-closed fault hooks from `config/actuation.yaml`.
- Allocation uses bang-bang sigma-delta duty accumulation rather than continuous throttle.
