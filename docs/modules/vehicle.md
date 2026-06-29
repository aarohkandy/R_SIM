# Vehicle Notes

- Physical quantities are config-driven; do not hide mass, geometry, material, or
  deployment parameters in code.
- Mass properties must support propellant depletion, CO2 depletion, and continuously
  changing leg deployment state.
- Determinism applies to every stochastic or dispersed vehicle input.
