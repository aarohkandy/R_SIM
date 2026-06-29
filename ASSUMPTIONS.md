# Assumptions

Every placeholder or stub below must be replaced or reaffirmed by later phases before its
dependent model is treated as real engineering data.

| ID | Area | Assumption | Replacement path |
| --- | --- | --- | --- |
| A-0001 | Inputs | Real motor `.eng`/`.rse` data is not present yet; `inputs/motor_D21_placeholder.eng` is a labeled placeholder. | Replace with measured or vendor motor data in `inputs/`, then update `config/motor.yaml`. |
| A-0002 | Inputs | Real vehicle BOM/mass/material data is not present yet; placeholder YAML files exercise mass, depletion, and deployable-leg behavior only. | Replace with measured BOM and material properties. |
| A-0003 | Inputs | Real OpenRocket frozen-configuration exports are not present yet; `inputs/openrocket/frozen_placeholder.csv` is a labeled comparison placeholder. | Add exported CP/Cd anchors under `inputs/openrocket/` and update `config/aero.yaml`. |
| A-0004 | Firmware | Real ESP32 and Teensy firmware ELFs are not present yet. | Add firmware sources/ELFs under `firmware/` before Phase 12. |
| A-0005 | Tooling | Renode, CalculiX/Gmsh, and ffmpeg are not required for Phase 0 and may be absent locally. | Later phases should attempt documented installs or stub/log blockers per `SPEC.md`. |
| A-0006 | Commands | `make e2e`, `make converge`, `make montecarlo`, `make sensitivity`, and `make soak` are exposed but intentionally fail until their phases implement them. | Replace command stubs during Phases 8, 13, 14, 15, and 17. |
| A-0007 | Cold gas | The Phase 5 CO2 model uses real-gas CoolProp properties, but tank volume, shell thermal mass, heat-transfer rate, regulator setpoint/sag, and nozzle throat areas are placeholder hardware values. | Replace with bench-measured cartridge/regulator/nozzle data and update `config/coldgas.yaml`; keep golden tests only after deliberate re-baselining. |
| A-0008 | Dynamics | Phase 6 dynamics settings for motor thrust axis, thrust application point, minimum aero speed, and angular damping are placeholder values used to exercise the plant. | Replace with measured thrust-line/alignment data, damping identification, and validated geometry before using trajectory outputs as engineering evidence. |
