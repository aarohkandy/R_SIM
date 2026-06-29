# Aerodynamics Notes

- Compute CP/Cd live as functions of Mach, leg-deploy angle, and depletion state.
- OpenRocket exports are comparison anchors only; never make them the runtime aero source.
- CFD belongs in the high-fidelity validation/refinement stack after the fast live model
  is stable; it can generate coefficient anchors, flow-field diagnostics, and surrogate
  updates, but must not silently replace the runtime source without tests and docs.
- Physics outputs such as static margin trends are data to log and plot, not flight verdicts.
