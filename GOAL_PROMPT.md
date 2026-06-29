# Goal Prompt

Paste this into Codex after `/goal` support is available. Do not start it until the
Phase-0 setup has been committed and pushed.

```text
/goal Build the self-landing rocket simulation + HIL emulator defined in SPEC.md.
Work the phases in SPEC.md §4 in order. TIME AND COMPUTE ARE NOT CONSTRAINTS: always
prefer slow, convergent, exhaustively-tested correctness over speed, and NEVER trade
rigor or physical accuracy for runtime. Test heavily per the §7 Testing & Rigor Mandate —
every module gets unit + property-based + regression/golden + integration tests before
its phase gate is allowed to pass, and the conservation, cross-validation, convergence,
Monte-Carlo, and sensitivity work in §7 are first-class phases (13–17), not optional
extras. After each phase: run that phase's verification command, run the FULL test suite,
and only if everything is green, commit and push to main and append a dated PROGRESS.md
entry (what passed, what is stubbed, what's next). Do NOT advance until the prior gate is
green, OR log in PROGRESS.md a specific justified blocker and proceed with a documented
stub. Once the Phase-8 end-to-end SIL flight works it is the KEYSTONE and must STAY green:
no later phase may regress it; run the suite before every commit. The objective is
COMPLETE only when all tests pass, the §7 conservation + convergence + cross-validation
checks hold, a full end-to-end flight runs rail→touchdown on the native-SIL backend and
emits the complete data bundle (§5.11) incl. the 3D animation, a large-N Monte Carlo has
run to statistical stability, AND the Renode co-sim backend (§5.9) runs the real firmware
against the plant for ≥1 full flight OR PROGRESS.md documents the exact board-bring-up
blocker and what remains. Treat ALL physics outputs (landing speed, tilt, CO2 remaining,
temps, stresses) as DATA to log and plot — never pass/fail asserts; there is no "the
rocket passed," only the numbers. Keep making visible progress (frequent green commits,
current PROGRESS.md). Enforce SPEC.md §0.1 invariants on every phase, regardless of
which file is open. Before building each phase, read SPEC.md and the relevant
docs/modules/*.md. Stop and report only if blocked with no defensible path. Read
SPEC.md §8 guardrails before coding.
```

Current Codex CLI note: this machine already has goal support available. If launching from
the modern CLI instead of the Desktop app, prefer current permission flags such as
`codex --sandbox danger-full-access --ask-for-approval never 2>&1 | tee codex-session.log`.
