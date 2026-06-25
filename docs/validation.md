# Validation

## Commands

Run these before starting the later `/goal`:

```bash
bash scripts/run_pre_goal_checks.sh
```

The active scenario matrix uses importable files in `examples/scenarios/`:

- `passive_baseline.json`
- `active_target_apogee.json`
- `calibrated_thrust_curve.json`
- `descent_airbrake.json`
- `low_pressure_warning.json`
- `invalid_no_motor.json`

## Required Passing Gates

- Python syntax compile succeeds over the repo.
- Active simulation unit tests pass.
- C++ controller safety tests pass for safe compilation, forbidden operations, runtime timeout, and output clamping.
- Active scenario matrix passes for passive, target-apogee, calibrated thrust-curve/aero-table, descent-brake, low-pressure, and invalid-input cases.
- Backend dependencies install in a clean Python 3.9 environment.
- Backend smoke tests pass:
  - `/api/health`
  - `/api/environment/motors`
  - `/api/environment/launch-sites`
  - `/api/openrocket/import`
  - `/api/control-code/compile`
  - `/api/control-code/compile` rejection of forbidden controller code
  - `/api/simulation/start`
  - `/api/simulation/status`
- Sample active pneumatic rocket simulation returns structured deterministic output.
- Frontend dependencies install.
- Frontend production build succeeds.
- Frontend lint succeeds.

## Result Acceptance

The sample simulation must include:

- `simulation_id`
- `status: completed`
- `results.max_altitude`
- `results.max_velocity`
- `results.total_flight_time`
- `results.drag_coefficient`
- `results.stability_margin`
- `results.source`
- `results.is_placeholder: false`
- `results.trajectory`
- `results.force_history`
- `results.moment_history`
- `results.active_system`
- `results.controller`

The smoke result must not claim to be CFD unless an actual CFD path ran.
The active-system result must show nonzero deployment and tank pressure use when active control is enabled.
