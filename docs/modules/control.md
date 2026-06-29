# Control Notes

- Keep the `ControllerBackend` seam swappable between native SIL and Renode HIL.
- The plant must not import controller internals.
- Once Phase 8 SIL end-to-end flight is green, the full suite must pass before every
  commit and later phases may not regress it.
