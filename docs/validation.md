# Validation

## Commands

Run these before starting the later `/goal`:

```bash
bash scripts/run_pre_goal_checks.sh
```

## Required Passing Gates

- Python syntax compile succeeds over the repo.
- Backend dependencies install in a clean Python 3.9 environment.
- Backend smoke tests pass:
  - `/api/health`
  - `/api/environment/motors`
  - `/api/environment/launch-sites`
  - `/api/control-code/compile`
  - `/api/simulation/start`
  - `/api/simulation/status`
- Sample rocket simulation returns structured deterministic output.
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

The smoke result must not claim to be CFD unless an actual CFD path ran.

