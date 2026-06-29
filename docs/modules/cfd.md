# CFD Notes

- This project is intended to grow into a high-fidelity rocketry simulation, not a tiny
  toy model. Add CFD as an explicit validation/refinement path once the live aero and
  end-to-end SIL loop are stable.
- Prefer open tools such as OpenFOAM or SU2 for build-time/offline CFD. Runtime flight
  simulation should use tested coefficient models or surrogates generated from those
  studies, so the 6-DOF loop remains deterministic and inspectable.
- CFD outputs should include meshes/cases, solver settings, residual/convergence evidence,
  coefficient tables, flow-field plots, and comparison reports against OpenRocket anchors
  and the live build-up model.
- Missing CFD tooling is a documented blocker/stub, not silent failure. Do not require
  paid APIs or network access at simulation runtime.
