# IO Notes

- Data bundles must include telemetry, plots, summaries, manifests, and animation artifacts
  when their phases are implemented.
- Physics outputs are reported as numbers and plots; never encode pass/fail verdicts on
  landing speed, tilt, temperatures, stresses, or CO2 margin.
- Input hashes and seed metadata belong in run manifests for reproducibility.
