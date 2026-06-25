# Progress Log

## 2026-06-25

- Replaced the previous OpenRocket checkout with `aarohkandy/R_SIM`.
- Created the local pre-goal documentation set.
- Added a planned validation harness for setup, backend smoke tests, frontend build, and frontend lint.
- Known environment default: use `/usr/bin/python3` on this machine because it is Python 3.9.6 and matches the current backend pins better than bundled Python 3.12.
- Known frontend default: expose the bundled Node and pnpm paths before installing/building.
- Added `LocalPreGoalSimulationManager` so local setup does not silently depend on GCP credentials or fake cloud output.
- Replaced the top-level `main.py` mock app with a compatibility launcher for `backend/f_backend.py`.
- Refreshed the frontend lockfile and added ESLint config.
- Ran `bash scripts/run_pre_goal_checks.sh`: passed.
- Smoke result: 4 motors, 3 launch sites, C++ controller compile ok, sample simulation source `local_pre_goal_physics`, max altitude about 54.46 m, max velocity about 30.72 m.
- Implemented active pneumatic local dynamics in `backend/active_simulation.py`.
- Wired local Flask simulation to preserve nested active-system/controller/noise config and execute compiled C++ controller code during the run.
- Added frontend setup controls for active air system, target apogee, tank pressure, tank volume, cylinder stroke, surface area, noise seed, and controller mode.
- Added active pneumatic results display for valve command, deployment, tank pressure, trajectory samples, and JSON/CSV export.
- Added active simulation unit tests for determinism, pressure consumption, active/passive flight differences, and pressure warnings.
- Ran active backend smoke check: sample source `active_pneumatic_local_dynamics`, max altitude about 55.75 m, max velocity about 26.71 m, max deployment 100%, final tank pressure about 601.6 kPa.
- Ran `bash scripts/run_pre_goal_checks.sh`: passed with 4 active simulation unit tests, backend API smoke, frontend build, and frontend lint.
- Browser-checked local app at `http://127.0.0.1:5001/`: active setup controls visible, controller compile button returned no browser errors, active results labels visible.
- Added input validation for missing motors, invalid mass, bad solver timing, and invalid pneumatic pressure/volume/actuator values.
- Added importable scenario files in `examples/scenarios/` for passive baseline, target-apogee active braking, descent airbrake, low-pressure warning, and invalid no-motor rejection.
- Added `scripts/run_active_scenario_matrix.py` and included it in the pre-goal check.
- Added frontend support for loading full rocket scenario JSON files, a built-in active demo rocket, and a controller-source selector.
- Ran `bash scripts/run_pre_goal_checks.sh`: passed with 6 active simulation unit tests, scenario matrix, backend API smoke, frontend production build, and frontend lint.
- Scenario matrix result highlights: passive baseline max altitude about 55.75 m with 0% deployment; active target-apogee max altitude about 45.51 m with about 41.5% deployment; descent airbrake max deployment 100%; low-pressure scenario produced the expected minimum-pressure warnings; invalid no-motor scenario failed honestly with `Rocket must include a motor.`
- Browser-checked local app at `http://127.0.0.1:5001/`: loaded the built-in active demo, launched it through the UI, reached results, showed active pneumatic fields, and produced no new browser console errors.
