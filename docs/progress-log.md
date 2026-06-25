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
