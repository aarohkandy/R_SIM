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
  - `/health`
  - `/api/environment/motors`
  - `/api/environment/motors/import`
  - `/api/environment/launch-sites`
  - `/api/openrocket/import`
  - `/api/control-code/compile`
  - `/api/control-code/compile` rejection of forbidden controller code
  - `/api/simulation/start`
  - `/api/simulation/status`
- Sample active pneumatic rocket simulation returns structured deterministic output.
- Sample active pneumatic rocket simulation uses a motor thrust curve from the backend motor database.
- Sample active pneumatic rocket simulation preserves builder split markers in `results.stage_splits`.
- Sample active pneumatic rocket simulation carries valid fin/motor attachment hosts, while invalid subpart-to-subpart attachments fail backend validation.
- Sample active pneumatic rocket simulation carries an internal mass component that affects mass/CG inputs without changing external length, diameter, split markers, or aero geometry.
- Frontend launch-site selection is wired to `/api/environment/launch-sites`.
- Frontend setup exposes deterministic sensor, atmosphere, attitude, and pneumatic pressure noise settings.
- Frontend motor search is wired to `/api/environment/motors` and must not contain a mock motor list.
- Frontend motor import is wired to `/api/environment/motors/import` and backend smoke tests preserve imported `.eng`/`.rse` thrust-curve points.
- Frontend design tree and rocket side-view drawing expose structural split markers.
- Frontend inspector/table expose subpart attachment hosts for fins, motors, and rail buttons.
- Frontend design tree nests attached subparts beneath their host airframe part and separates unattached subparts.
- Frontend palette, inspector, table, mass breakdown, and side-view drawing expose internal mass components.
- Frontend palette, inspector, table, side-view drawing, OpenRocket import, and backend simulation config expose parachute, streamer, and shock-cord recovery components.
- Recovery safety output applies shock-cord rated strength as a harness opening-load limit and reports the effective opening-load limit.
- Frontend results view renders live charts from trajectory, force, pressure, and active-system histories.
- Frontend export actions include trajectory CSV, force/moment CSV, active-system CSV, and full JSON.
- Frontend API configuration does not default to hardcoded cloud/GCP services for the local workflow.
- Backend main server does not contain random placeholder result generation.
- Cloud/GCP and heavy OpenFOAM paths fail with explicit unavailable errors when their real credentials/toolchains are missing.
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
- `results.stage_splits`
- `results.active_system`
- `results.controller`

The smoke result must not claim to be CFD unless an actual CFD path ran.
The active-system result must show nonzero deployment and tank pressure use when active control is enabled.
