# Tooling Notes

Phase 0 requires only the Python environment and dev/test tools declared in
`pyproject.toml`.

Later phases may need external tools that are not required for the scaffold:

```bash
# Video export for animation bundles
brew install ffmpeg

# Structural/mesh tooling for Phase 11
brew install calculix gmsh

# Renode HIL co-simulation for Phase 12
brew install --cask renode
```

If these tools are unavailable or cannot be installed during the long goal run, keep the
interface in place, document the blocker in `PROGRESS.md`, document any stub in
`ASSUMPTIONS.md`, and continue per `SPEC.md`.
