# SPEC.md — Self-Landing Rocket Simulation & Hardware-in-the-Loop Emulator

> This file is the durable specification for a Codex `/goal` run. Codex must read this
> file in full before writing any code, and must treat it as the source of truth for
> scope, architecture, verification, and guardrails.

---

## 0. HOW TO USE THIS (human setup — do this once, then walk away)

1. **Upgrade Codex CLI to ≥ 0.128.0** (`/goal` lives here):
   `npm install -g @openai/codex@latest`
2. **Enable goals** (it is behind a feature flag):
   `codex features enable goals`
   — or add to `~/.codex/config.toml`:
   ```toml
   [features]
   goals = true
   ```
3. **Initialize a clean git repo** in an empty directory and put THIS file at the repo root as `SPEC.md`. Git is your safety net for a long autonomous run.
4. **Drop your input data files** into `inputs/` (see §6). At minimum: the motor `.eng`/`.rse` file, your parts/BOM list (CSV or YAML), and any OpenRocket exports you have. Anything missing, the sim must synthesize a documented placeholder and keep going (see Iteration Policy).
5. **Start Codex in full-auto, with logging**, from the repo root:
   `codex --approval-mode full-auto 2>&1 | tee codex-session.log`
6. **Paste the goal command** (the block in §1). Then leave it. Check status anytime with bare `/goal`. Pause/resume/clear with `/goal pause|resume|clear`.

> NOTE: `/goal` will follow a bad contract for hours. This file *is* the contract. If you
> change scope, `/goal clear` and re-issue rather than layering instructions.

> REQUIRED DEV/TEST TOOLING (install in the Phase-0 scaffold, in addition to the runtime
> deps numpy/scipy/pandas/matplotlib/pyarrow/pydantic/pyyaml/CoolProp/pyvista): `pytest`,
> `pytest-cov` (coverage), `hypothesis` (property-based tests), and a linter+formatter+type
> checker (`ruff` + `mypy`). Add a task runner (`Makefile` or `justfile`) exposing
> first-class commands: `test` (full suite + coverage), `lint`, `typecheck`, `e2e` (one
> full flight), `converge` (Phase-13 study), `montecarlo` (Phase-14), `sensitivity`
> (Phase-15), `soak` (Phase-17). Renode, CalculiX/Gmsh, and ffmpeg are NOT needed for
> Phase 0 — they're required for Phases 11–12; document the `brew install` commands now so
> the later phases can attempt them and stub/log if absent (per §1 iteration policy).

## 0.1 NON-NEGOTIABLE INVARIANTS (apply on EVERY phase)

These rules apply regardless of which file is open:

- **Physics fidelity:** real-gas CO2 via CoolProp (NEVER ideal gas); aero CP/Cd computed
  live as f(Mach, leg-deploy angle, depletion) — OpenRocket is a comparison anchor, never
  the runtime source; fixed-step RK4 + zero-order-hold on valve states (NEVER adaptive
  `solve_ivp`); cold gas is bang-bang through fixed nozzles (no continuous throttle);
  structural FEA is event-triggered on logged load cases (NEVER coupled into the flight loop).
- **Architecture:** the `ControllerBackend` seam stays swappable (SIL ↔ Renode); the plant
  never imports controller internals.
- **Rigor over speed:** time and compute are NOT constraints — always prefer slow,
  convergent, exhaustively-tested correctness; never trade accuracy for runtime. Every
  module gets unit + property-based (`hypothesis`) + golden/regression + integration tests
  before its gate passes. Conservation, convergence, cross-validation, ≥1000-run Monte
  Carlo, and sensitivity are first-class phases, not extras.
- **Keystone:** once the Phase-8 end-to-end SIL flight is green, run the FULL suite before
  every commit; no later phase may regress it. Commit only green; push to main after each
  green gate; keep `PROGRESS.md` current.
- **Determinism is sacred:** thread the master seed everywhere (including parallel Monte
  Carlo via `SeedSequence.spawn`); same seed ⇒ identical telemetry hash.
- **Physics outputs are DATA, never pass/fail:** report numbers + plots; asserts are for
  code/conservation/convergence/determinism only — never on flight outcomes.
- **No silent stubbing / no gold-plating:** every placeholder gets a `PROGRESS.md` +
  `ASSUMPTIONS.md` entry; reach each phase's test bar, commit, move on (heavy compute lives
  in phases 13–17); never fake completion.
- Read `SPEC.md` and the relevant `docs/modules/*.md` before building each phase.

---

## 1. THE GOAL CONTRACT (paste this after `/goal`)

```
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

### Contract fields (Codex: hold these in mind throughout)
- **Outcome:** a working, data-driven, editable simulation framework + emulator that takes the vehicle/part definitions and produces a full flight data bundle + animation, plus a hardware-faithful co-sim of the real firmware.
- **Verification surface:** per-phase commands in §4; the conservation/sanity suite in §7; the end-to-end run artifact bundle in §5.11.
- **Constraints (must not regress):** determinism/reproducibility (fixed seed ⇒ identical output); nothing hardcoded that belongs in config (§6); each module independently unit-testable; the controller-backend interface (§5.9) stays swappable.
- **Boundaries:** operate only inside this repo. External tools allowed: Python scientific stack, CoolProp, Renode, a 6-DOF/quaternion math lib, an open FEA solver (CalculiX or FEniCS), matplotlib/pyvista for plots/animation. Do not call paid APIs. Do not require network at sim runtime (fetch deps at build time only).
- **Iteration policy:** if an input is missing, generate a clearly-labeled placeholder, record the assumption in `ASSUMPTIONS.md`, and continue — do not stall waiting for data. If a board model or FEA case is too heavy to finish, stub it behind its interface, log it, and move on so the rest of the system still runs end-to-end.
- **Blocked-stop condition:** stop and summarize only when no phase can advance without human input (e.g., a required input format is ambiguous AND no reasonable placeholder exists).

---

## 2. SYSTEM OVERVIEW & ARCHITECTURE (read before coding)

This simulates a **bottle-sized, ~0.9 kg wet, 3D-printed, CO2 cold-gas self-landing
rocket** through full flight: launch-rail → boost → coast → apogee → controlled descent
→ landing-burn → touchdown. It then verifies the **actual flight-controller firmware**
by running it on **emulated microcontrollers** co-simulated against the physics plant.

### 2.1 The two-layer controller architecture (CRITICAL — do not collapse this)

The physics "plant" must be fully decoupled from the controller behind ONE interface
(`ControllerBackend`, §5.9). There are two interchangeable backends:

- **Backend A — Native SIL (build first).** The control algorithm compiled/loaded
  natively and called by the physics loop at the configured rate, with loop latency and
  jitter modeled as parameters. Fast (seconds–minutes per flight). This is how the
  physics gets validated and gains get tuned.
- **Backend B — Renode HIL co-sim (build second).** The *real, unmodified firmware
  binaries* for the ESP32 and the Teensy run inside Renode, co-simulated in lockstep
  with the physics plant. Slow (this is the overnight artifact). This verifies timing,
  ISRs, peripheral use, inter-MCU comms, and loop-overrun behavior.

Both backends consume the identical plant. Build A, validate the whole pipeline with it,
THEN add B. Rationale: de-risks the run — a working sim exists even if B's board
bring-up is hard.

### 2.2 Why not "just export Cd/CP from OpenRocket"

CP and Cd change continuously as the legs deploy and as propellant + CO2 deplete.
OpenRocket emits static coefficients for a frozen geometry only. Therefore aerodynamics
and mass properties are **computed live** from geometry + current configuration state.
OpenRocket exports are ingested as **validation anchors** (compare our coefficients to
OpenRocket's at matching frozen configs), never as the runtime source.

### 2.3 Why structural FEA is event-triggered, not co-simulated

Structural/vibration modes live at kHz–MHz; rigid-body flight dynamics at ~Hz. Coupling
a live FEA mesh into the flight timestep wastes enormous compute on dynamics that don't
affect the trajectory. Instead: the flight sim **logs the load state + thermal field at
critical events** (motor-thrust transient, max-Q, each leg deployment, landing impact),
and a separate structural stage runs FEA on **those load cases only**. Landing impact is
the dominant case. (If continuous aeroelastic coupling is later required, it slots in as
an optional plant extension — but it is out of scope for the default build.)

### 2.4 Time & determinism

Fixed master seed ⇒ bit-reproducible runs. The plant integrates at a fine internal
timestep; the controller runs at its own (slower) configured rate; Renode advances in
synchronized virtual-time quanta. All three share one clock. Document the time-sync
scheme in `docs/time_sync.md`.

---

## 3. VEHICLE DEFINITION (defaults — ALL overridable in config, §6)

These are the current locked/known parameters. They are **defaults in YAML**, not magic
numbers in code. Treat every value as editable.

- **Form factor:** bottle-sized (~Smartwater bottle), body ≈ 63 mm dia × ~200 mm (edit).
- **Mass:** target wet ≈ 0.9 kg. Computed from the parts list, not asserted.
- **Structure:** carbon-fiber tube stock (6 mm OD × 4 mm ID) members; bonded inserts at
  every clamp point; 3D-printed bodywork (PLA/PETG/ABS — material per part, with its
  glass-transition / heat-deflection temp as a thermal limit input).
- **Motor:** single-use 18 mm, AeroTech D21T class (~20 N·s). Sim reads the `.eng`/`.rse`
  thrust curve from `inputs/`. Burn time, mass-flow, and CG shift derive from the curve.
- **Cold-gas landing system:**
  - Source: 88 g / 90 g **threaded liquid-CO2 cartridge** → cartridge-to-regulator
    adapter → adjustable regulator stepping down to ~120 psi (edit). Model second
    regulator stage as an optional toggle (bench may show pressure sag).
  - Actuation: **3 downward nozzles, one per leg**, bang-bang (NC direct-acting 12 V
    brass solenoid, ~1/8"). Ideally axial; include a per-nozzle cant + position
    misalignment parameter (real builds aren't perfect).
  - Layout: heavy mass (tank) high, nozzles low — inverted-pendulum stability.
- **Legs:** 3 legs, **burn-wire deployment during coast** (servo sear rejected).
  Restraint = nylon or rubber (NOT Kevlar — burn-wire must sever it). Deployment is a
  parameterized event: wire current → time-to-melt → restraint release → spring/gravity
  deployment kinematics. The deployment ANGLE feeds aero (CP/Cd) and mass (CG/inertia)
  continuously. (Burn-wire melt model is a pluggable sub-model; human will refine it.)
- **Avionics:** Teensy (control + full-rate microSD logging) + ESP32 (live telemetry
  streaming + crash-survival backup). These are the two emulated MCUs.
- **Stability target:** 1–1.5 calibers for this low-L/D stubby form (the standard
  2-caliber rule does NOT apply); verify in the sim's own static-margin calc + a modeled
  swing test.
- **No parachute / no streamer.** Velocity is killed by drag + the cold-gas burn only.

---

## 4. PHASE PLAN (the spine — each phase has a verification GATE)

Build in this order. Each phase ends with a runnable command that proves it. Append to
`PROGRESS.md` after each. Do not skip gates silently.

| # | Phase | Deliverable | GATE (verification command) |
|---|-------|-------------|------------------------------|
| 0 | Scaffold | Repo layout (§5), config loader, seeded RNG, `PROGRESS.md`, `ASSUMPTIONS.md`, CI test runner | `pytest -q` runs (even if mostly empty); config round-trips |
| 1 | Mass properties | Parts→CG + full inertia tensor, time-depletion on motor curve + CO2 flow, leg-deploy effect | unit test: known parts ⇒ hand-checked CG/inertia; depletion monotonic |
| 2 | Environment | ISA atmosphere(h), wind (steady + gust + shear), launch rail constraint | unit test: density/pressure vs ISA tables; rail exit velocity sane |
| 3 | Aerodynamics | Component build-up CP(config) + Cd(Mach, config); leg-angle dependence; OpenRocket-export comparison | unit test: CP/Cd vs OpenRocket anchor within tolerance at frozen configs |
| 4 | Solid motor | Thrust(t), mass-flow, CG/inertia coupling from `.eng` | unit test: total impulse from curve matches header; mass conserved |
| 5 | Cold-gas propulsion | Two-phase CO2 blowdown (CoolProp), regulator, choked-nozzle thrust, evaporative cooling, per-nozzle thrust | unit test: tank pressure tracks saturation until liquid gone; Isp/thrust in sane band; energy/mass balance |
| 6 | 6-DOF dynamics | Quaternion rigid-body integrator, gravity, aero forces+moments, thrust forces+moments, time-varying mass | unit test: torque-free precession sane; energy bookkeeping; no-thrust ballistic matches analytic |
| 7 | Sensors | IMU (accel+gyro w/ noise, bias, drift, scale), baro (noise+lag), modeled at MCU sample rates; noise ON from start | unit test: noise stats match configured PSD/Allan params |
| 8 | Controller iface + Backend A | `ControllerBackend` interface; native-SIL cascaded controller (attitude + descent-rate; bang-bang allocation across 3 valves w/ min-pulse floor); loop-rate + latency + jitter model | **end-to-end flight runs to touchdown**; emits partial data bundle |
| 9 | Data & animation | Full telemetry log (every state, every valve, thrust, CO2, temps), plots, **3D ascent/descent animation showing which nozzles fired**, landing summary table | end-to-end run produces complete bundle (§5.11) |
| 10 | Thermal network | Lumped-node transient thermal: motor casing → shield (foil) → structure; solenoid/electronics self-heat; node temps vs each part's material limit | thermal run on logged flight; node temps + margins reported as DATA |
| 11 | Structural (event-triggered) | Extract load cases at critical events; FEA (CalculiX/FEniCS) on landing impact + thrust transient + max-Q against material props | FEA runs on ≥1 case (landing); stress/displacement reported as DATA |
| 12 | Backend B — Renode HIL | Emulate ESP32 + Teensy running real firmware ELFs; sensor injection plant→MCU; GPIO/PWM MCU→plant actuation; inter-MCU link; virtual-time sync to plant; loop-overrun detection | real firmware drives ≥1 full flight in co-sim, OR blockers documented in PROGRESS.md |
| 13 | Convergence + cross-validation | Timestep + Renode-sync-quantum refinement studies until landing-state metrics converge; cross-validate passive ascent vs RocketPy and vs analytic ballistic; aero vs OpenRocket anchors | convergence tables show metric stability under refinement; cross-val deltas within tolerance, all reported as DATA |
| 14 | Monte Carlo at scale | Large-N (≥1000, run until distributions are statistically stable) dispersed over wind/mass/CG/alignment/sensor-seed/valve-timing; full distributions | landing-speed, tilt, lateral-error, CO2-margin distributions emitted as DATA (histograms + percentiles) |
| 15 | Sensitivity analysis | One-at-a-time + Sobol/variance-based sensitivity of landing metrics to key params (CO2 mass, reg pressure, nozzle area, loop rate, sensor noise, alignment) | ranked sensitivity indices emitted as DATA — tells the human what actually matters |
| 16 | Backend cross-check | Run identical scenarios through Backend A (SIL) and Backend B (Renode firmware); quantify divergence to validate the SIL model faithfully represents the firmware | per-scenario A-vs-B control/trajectory deltas emitted as DATA |
| 17 | Soak / robustness | Many full flights back-to-back + repeated fixed-seed reruns to catch nondeterminism, state bleed, memory growth; fault-injected runs (stuck/leaking valve, sensor dropout) | determinism holds across N reruns; fault-mode behavior emitted as DATA |

> TIME IS NOT A BUDGET HERE. Long, thorough, convergent runs are explicitly preferred over
> fast ones. The only hard requirement is steady, *visible* progress: each phase must reach
> its full test bar, get committed green, and update `PROGRESS.md`. Do not stall an early
> phase by gold-plating it past its test bar (§8.13) — reach the bar, commit, move on, and
> let the heavy compute live in phases 13–17. If a single operation is genuinely
> intractable (not just slow), stub it behind its interface, log it, and keep the rest of
> the system running end-to-end. Never fake completion.

---

## 5. MODULE SPECIFICATIONS

Repo layout:
```
rocketsim/
  config/            # YAML configs + pydantic schema (§6)
  vehicle/           # mass properties, geometry, configuration-state
  aero/              # CP/Cd build-up, OpenRocket ingestion
  propulsion/        # solid motor + cold-gas CO2
  actuation/         # solenoids, control allocation
  environment/       # atmosphere, wind, launch rail
  dynamics/          # 6-DOF quaternion integrator
  sensors/           # IMU/baro models with noise
  control/           # ControllerBackend iface; backend_sil; backend_renode
  thermal/           # lumped-node network
  structural/        # load-case extraction + FEA driver
  sim/               # orchestrator, time-sync, run loop
  io/                # logging, data bundle, plotting, 3D animation
  gui/               # localhost OpenRocket-style inspection workbench
  tests/             # unit + integration + conservation suite
inputs/              # user data: .eng, BOM, OpenRocket exports, material props
outputs/             # per-run artifact bundles
firmware/            # user firmware sources/ELFs for Renode
renode/              # .resc scripts, .repl platform files
docs/                # time_sync.md, model notes, equations
SPEC.md PROGRESS.md ASSUMPTIONS.md
```

### 5.1 vehicle/ — mass properties & configuration state
- Input: parts list with mass, position (axial + radial), and a config-state tag
  (fixed / propellant / CO2 / deployable-leg).
- Compute total mass, CG (3-vector), and full 3×3 inertia tensor about CG.
- **Time-varying:** subtract solid-propellant mass per the motor curve (shift CG aft→fwd
  as grain burns); subtract CO2 mass per cold-gas mass-flow; move legs from stowed→
  deployed angle over the deployment event, updating CG + inertia continuously.
- Expose `mass_properties(t, config_state) -> (m, cg, I)`.
- This is the module that answers "burnout at t=Tb ⇒ mass = m(Tb)".

### 5.2 aero/ — aerodynamics (computed, not exported)
- **CP:** extended Barrowman over the body-of-revolution + fins/legs as lifting
  surfaces; CP is a function of Mach and **leg-deployment angle** (deployed legs add aft
  area ⇒ CP moves aft ⇒ static margin rises). Body-of-revolution + deployable-surface
  build-up.
- **Cd(Mach, config):** sum of component drags — skin friction, pressure/base drag,
  interference, and **leg drag as a function of deployment angle** (huge effect: stowed
  vs fully-deployed base-first descent differ by a large factor). Subsonic regime
  dominates here (Mach < ~0.3) but keep Mach dependence general.
- **Static margin** = (CP − CG)/diameter, reported continuously; target band 1–1.5 cal.
- **Modeled swing test:** simulate a pivot-suspended spin-up and report the restoring
  behavior, as an independent stability check.
- **OpenRocket ingestion:** parse exported Cd(Mach)/CP for frozen configs from `inputs/`
  and emit a comparison report (ours vs OpenRocket) — anchor, not source.

### 5.3 propulsion/solid — solid motor
- Parse `.eng`/`.rse`: thrust(t), propellant mass, total mass.
- Emit thrust force along body axis; feed mass-flow and CG/inertia shift to vehicle/.
- Verify integrated impulse matches the curve header.

### 5.4 propulsion/coldgas — CO2 cold-gas system (the subtle one)
Model the real thermodynamics — **do not use ideal gas**:
- **Storage:** CO2 stored as saturated liquid+vapor in the cartridge. Tank pressure =
  saturation pressure at current cartridge temperature (CoolProp `PropsSI`,
  CO2 EOS / Span–Wagner).
- **Blowdown:** as vapor is drawn, liquid evaporates to replenish it; **latent heat of
  vaporization cools the cartridge**, lowering saturation pressure and thus thrust over
  time. Track cartridge temperature and remaining liquid/vapor mass.
- **Pressure-sag question:** if commanded mass-flow exceeds what evaporation can supply,
  upstream pressure droops — this is exactly the effect the bench test will measure, so
  the model must be able to exhibit it (drives the "need a 2nd regulator stage?" call).
- **Regulator:** step inlet down to setpoint (~120 psi) while inlet > setpoint; below
  that, output tracks (sagging) inlet. Optional second stage = toggle.
- **Nozzle thrust:** choked/isentropic flow through each nozzle throat:
  thrust per nozzle from upstream stagnation P,T, throat area, and CO2 gas properties
  (real-gas γ, R via CoolProp); mass-flow = choked-flow relation. Sum across open
  nozzles. Expose `thrust_and_torque(valve_states, t, tank_state)`.
- Energy + mass balance must close each step (conservation test, §7).
- Reference physics: TALARIS cold-gas hopper (MIT) on liquid-CO2 replenishment + draw-
  rate limits (see §9).

### 5.5 actuation/ — solenoids & control allocation
- Per-valve model: NC, finite open/close latency, **minimum reliable pulse width**
  (bang-bang resolution floor), optional stuck/leak fault injection.
- **Control allocation:** map the controller's desired (collective downward thrust +
  body torque) onto the 3 fixed downward nozzles. With 3 axial nozzles you get collective
  thrust + 2 torque axes (roll is not directly controllable by pure-axial nozzles — note
  this limitation explicitly; expose nozzle cant params so the user can study adding
  roll authority). Bang-bang PWM with the min-pulse floor enforced.

### 5.6 environment/ — atmosphere, wind, rail
- **Atmosphere:** ISA — temperature, pressure, density vs altitude (constant-ish below
  ~500 m but keep the model general).
- **Wind:** steady component + gusts (e.g., Dryden/“1-cosine” gust) + altitude shear;
  all parameterized; default off, dispersed in Monte Carlo.
- **Launch rail:** rail length + angle; constrain attitude to the rail until the rocket
  clears it; report rail-exit velocity (must exceed a configured minimum for stability).

### 5.7 dynamics/ — 6-DOF rigid body
- **Quaternion** attitude (no gimbal lock) + body rates; translational state in an
  inertial frame.
- Forces: gravity, aerodynamic (from aero/ at current AoA, applied at CP), solid-motor
  thrust, cold-gas thrust (per-nozzle, at nozzle positions ⇒ produces control torques).
- Moments: aero restoring moment (CP–CG), thrust-misalignment + nozzle-cant moments,
  damping.
- **Time-varying m, CG, I** from vehicle/ every step.
- Integrator: fixed-step RK4 with **zero-order hold on valve states** within a step — NOT
  an adaptive `solve_ivp`, because bang-bang valve switching creates discontinuities that
  make adaptive steppers thrash. Step size configurable, fine enough to resolve the
  shortest valve pulse. Document this choice in `docs/`.

### 5.8 sensors/ — sensor models (noise ON from day one)
- **IMU:** 3-axis accel + gyro with additive noise (configurable PSD), bias + bias drift
  (random walk / Allan-style params), scale-factor error, misalignment, saturation,
  sampled at the MCU's real rate.
- **Barometer:** pressure→altitude with noise + first-order lag.
- (ToF rangefinder + pressure transducer: deferred to v2 per vehicle plan — include as
  disabled stubs behind the same interface.)
- These feed the controller (Backend A directly; Backend B via injection into Renode).

### 5.9 control/ — ControllerBackend interface + both backends
**Interface (the swappable seam — keep stable):**
```
ControllerBackend:
    reset(seed)
    step(sensor_packet, t) -> valve_commands   # called at controller rate
    telemetry() -> dict                         # internal controller state for logging
```
- **Backend A (SIL, build in Phase 8):** native cascaded controller — outer loop on
  attitude + descent-rate produces desired collective-thrust + body-torque; allocation
  (§5.5) → bang-bang valve commands. Model the **loop rate** (configured Hz), **latency**
  (sense→actuate delay), and **jitter**. Swappable control law (PD baseline; leave hooks
  for LQR/MPC). Fast.
- **Backend B (Renode HIL, build in Phase 12):**
  - Two Renode machines: **ESP32** (Xtensa) and **Teensy 4.x = NXP i.MX RT1062
    Cortex-M7**, each loading the user's **real firmware ELF** from `firmware/`.
  - **Plant → MCU sensor injection:** feed the §5.8 sensor packets into the emulated
    sensor peripherals/registers (Renode RESD sensor streams or a virtual sensor
    peripheral via the External Control API), so the firmware reads them as real hardware.
  - **MCU → plant actuation:** read the Teensy GPIO/PWM lines driving the 3 solenoids out
    of Renode; the resulting valve states feed actuation/. Latency + min-pulse then emerge
    from the *real firmware + valve model* rather than being assumed.
  - **Inter-MCU link:** model the Teensy↔ESP32 wired link (serial/SPI/I2C) between the two
    Renode nodes.
  - **Time sync:** advance Renode by a virtual-time quantum, advance the plant by the same
    quantum, exchange at the boundary; Renode's deterministic virtual time keeps it
    reproducible. Document in `docs/time_sync.md`.
  - **Loop rate / "exact Hz":** the control loop is driven by a hardware-timer ISR in the
    firmware; Renode models the timer, so the loop executes at exactly the configured Hz
    in virtual time. The sim **measures per-loop execution time and flags overruns** (loop
    body exceeding its period) — this is the meaningful timing-correctness check.
  - **KNOWN RISKS (log status in PROGRESS.md, stub if blocked):**
    - ESP32 **WiFi** stack emulation is the least-faithful part of any emulator; the ESP32
      here does telemetry streaming + crash-backup, so model the *link behavior* and
      MCU-side logic even if the RF/PHY is abstracted.
    - The **i.MX RT1062 board `.repl`** likely needs to be authored/verified (peripherals:
      timers, GPIO, the sensor bus) rather than pulled off-the-shelf. Reuse existing
      Cortex-M7 + NXP peripheral models where possible.
    - If full board bring-up can't complete in the run, deliver the co-sim harness +
      whichever peripherals work, and document precisely what remains.

### 5.10 thermal/ — lumped-node transient thermal
- Node network: motor casing → tinfoil heat shield → adjacent 3D-printed structure →
  carbon-fiber members → electronics bay; conduction links, radiation from the motor,
  convection to ambient (using flight velocity from the trajectory).
- Aerodynamic heating is negligible at these speeds — the **motor** is the dominant
  source; the question is whether nearby **3D-printed polymer** exceeds its
  glass-transition / heat-deflection temperature (PLA ~55–60 °C, PETG ~75–80 °C, ABS
  ~95–105 °C — actual limit per part from `inputs/`). Also check the solenoid/electronics
  self-heating.
- Run on the logged flight (post-trajectory). Output: temperature(t) per node + **margin
  to each material's limit**, reported as DATA (not pass/fail). Flag any node that crosses
  its limit and when.

### 5.11 io/ — data products (the whole point: "a shitload of data")
Every run writes a timestamped bundle under `outputs/<run_id>/`:
- **`telemetry.parquet/csv`** — full-rate time series: position, velocity, attitude
  (quat + Euler), body rates, AoA, mass, CG, inertia, static margin, Mach, dynamic
  pressure, each valve's open/closed state, per-nozzle + total thrust, CO2 mass + tank
  pressure + cartridge temp, controller internal states, sensor raw vs truth.
- **Plots** (matplotlib): altitude/velocity/accel vs time; attitude + rates; static
  margin vs time; thrust (solid + each nozzle) vs time; CO2 remaining + tank pressure vs
  time; valve activity raster (which nozzle fired when); sensor-vs-truth overlays;
  controller error signals; thermal node temps; FEA stress summary.
- **3D animation** (pyvista/matplotlib): the vehicle flying up and coming down along its
  trajectory, attitude shown, **with nozzle plumes lighting up when each valve fires** and
  legs deploying at the deployment event. Export mp4 + interactive if feasible.
- **`landing_summary.json`** — touchdown speed, tilt at touchdown, lateral position,
  CO2 remaining at touchdown, peak loads, peak temps. **DATA, not a verdict.**
- **`run_manifest.json`** — config used, seed, code version, input file hashes (for
  reproducibility).

### 5.12 gui/ — localhost workbench
- Serve a local browser GUI from the repo with `make gui` / `rocketsim gui`.
- The GUI must open directly into a usable engineering workbench, not a landing page:
  run tree, phase/status tree, metrics, plots, animation, telemetry preview, thermal
  summary, structural/FEA summary, and emulator/HIL status.
- Layout should stay dense and inspection-oriented, closer to OpenRocket than to a
  marketing dashboard. It must be usable on localhost without network access at runtime.
- GUI data comes from the same output bundles and manifests as the CLI analysis; it must
  not maintain a separate truth source.

---

## 6. CONFIG SCHEMA (data-driven — nothing physical hardcoded)

All physical/scenario parameters live in versioned YAML, validated by pydantic models
(strict types, ranges, required fields). Code reads config; code never embeds a tunable
physical constant. The user feeds data and
links; Codex maps the data into config. Suggested files:
```
config/vehicle.yaml      # geometry, parts list (mass+position+state-tag), materials
config/motor.yaml        # path to .eng/.rse, ignition time
config/coldgas.yaml      # cartridge mass, regulator setpoint, 2nd-stage toggle,
                         #   nozzle throat areas, positions, cant/misalignment
config/actuation.yaml    # solenoid latency, min pulse, fault injection
config/aero.yaml         # body/fin/leg geometry, leg deploy-angle schedule,
                         #   OpenRocket export paths
config/environment.yaml  # atmosphere, wind (steady/gust/shear), launch rail len/angle
config/sensors.yaml      # IMU/baro noise, bias, drift, scale, sample rates
config/control.yaml      # backend select (sil|renode), loop rate, latency, jitter, gains
config/thermal.yaml      # node network, link conductances, material temp limits
config/structural.yaml   # FEA mesh/material props, which load cases to run
config/sim.yaml          # master seed, integrator dt, sync quantum, end conditions
```
Validation: on load, check units, ranges, and required fields; missing inputs ⇒ labeled
placeholder + `ASSUMPTIONS.md` entry (never a silent default).

---

## 7. TESTING & RIGOR MANDATE (time is not a constraint — thoroughness is the priority)

The point of this section: "test a lot" must mean *deep* testing that proves physics and
behavior, not a pile of shallow asserts. Compute is free here; spend it on rigor.

### 7.1 Test layers (EVERY module must have all that apply, before its gate passes)
- **Unit tests** — every public function/class; edge cases, boundary values, failure paths.
- **Property-based tests** (use `hypothesis`) — invariants that must hold over randomized
  inputs, e.g.: mass is monotonically non-increasing; quaternion stays unit-norm; energy
  is conserved within tolerance in the no-dissipation case; CP, Cd, Isp, thrust stay
  within physical bounds; tank pressure never exceeds saturation pressure; valve pulses
  never go below the configured min-pulse floor.
- **Regression / golden tests** — freeze known-good outputs (trajectories, coefficient
  curves, telemetry hashes); fail on unexplained drift. Provide an explicit, logged
  re-baseline procedure so intended changes can update goldens deliberately.
- **Integration tests** — modules wired together (e.g., aero+dynamics, propulsion+vehicle,
  sensors+controller) behave consistently.
- **Determinism tests** — same seed ⇒ identical telemetry hash, asserted across repeated
  runs (also see soak, Phase 17).
- **End-to-end tests** — a full rail→touchdown flight runs and emits the complete bundle.
- Aim for high coverage, but treat coverage as a floor, not the goal — a covered line with
  no meaningful assertion is not a test. Run `pytest` with coverage; wire it into CI.

### 7.2 Conservation / sanity suite (the trust backbone — must hold)
- No-thrust ballistic trajectory matches an analytic/known solution within tolerance.
- Torque-free rigid-body rotation conserves angular momentum; precession is physical.
- Mass strictly decreases; total impulse recovered from the motor curve matches its header.
- Cold-gas mass + energy balance closes each step; tank pressure tracks the CO2 saturation
  curve until liquid is exhausted, then blows down.
- Atmosphere model matches ISA reference points.
- Static margin computed two independent ways (build-up vs the modeled swing test) agree.

### 7.3 Rigor activities that productively consume time (Phases 13–17 — schedule them)
- **Numerical convergence studies (Phase 13):** halve the integrator dt (and the Renode
  sync quantum) repeatedly until landing-state metrics (touchdown speed, tilt, CO2 used)
  converge; report the convergence table. This is the single most important evidence that
  the integration is trustworthy — without it the numbers are unanchored.
- **Cross-validation (Phase 13):** validate the passive ascent against RocketPy and against
  an analytic ballistic solution; validate aero coefficients against the OpenRocket anchors
  at frozen configs. Report deltas. Disagreement is a finding, not a failure to hide.
- **Monte Carlo at scale (Phase 14):** ≥1000 runs (more until distributions stabilize),
  dispersed over wind, mass, CG, nozzle alignment/cant, sensor seeds, and valve timing.
  Emit full distributions (histograms + percentiles), not just means — the spread is what
  tells you whether you reliably have enough CO2.
- **Sensitivity analysis (Phase 15):** one-at-a-time + Sobol/variance-based indices ranking
  which parameters actually drive landing outcome. This tells the human where to spend
  engineering effort and bench time.
- **Backend cross-check (Phase 16):** quantify how closely Backend A (SIL) reproduces
  Backend B (real firmware) on identical scenarios — this is what justifies trusting the
  fast SIL loop for tuning.
- **FEA mesh-convergence (within Phase 11):** refine the landing-impact mesh until peak
  stress converges; report it.
- **Soak / robustness (Phase 17):** many back-to-back flights + fixed-seed reruns to catch
  nondeterminism / state bleed / memory growth; fault-injected runs.

### 7.4 The evidence-based "done" condition (what lets the `/goal` complete)
All of: §7.1 tests pass; §7.2 conservation suite holds; §7.3 convergence + cross-validation
hold and are reported; Phase-8 end-to-end SIL flight runs rail→touchdown and emits the full
bundle (§5.11) incl. animation; a large-N Monte Carlo (Phase 14) has run to statistical
stability; and Backend B runs the real firmware for ≥1 full flight OR PROGRESS.md documents
the exact board-bring-up blocker + remaining steps.

### 7.5 Physics RESULTS are DATA, never pass/fail
Landing speed, tilt, lateral error, CO2 remaining, per-node temps + margins, peak
stresses/displacements, and all distributions: **report the numbers + plots**, so the human
judges whether there's enough CO2 and whether anything melts or breaks. Do NOT write
`assert landing_speed < 2.0` or any physics verdict. There is no "pass." There is the data.
The asserts live only at the *engineering* layer (§7.1–7.4): code correctness, conservation,
convergence, determinism — never on the flight outcome.

---

## 8. GUARDRAILS (Codex: read before coding — "don't do X")

1. **No hardcoded physical constants** that belong in config. If it could be tuned or
   measured, it lives in YAML (§6).
2. **No adaptive ODE integration** for the controlled phases. Fixed-step RK4 + ZOH on
   valve states. Adaptive steppers thrash on bang-bang discontinuities.
3. **No ideal-gas CO2.** Use CoolProp real-gas properties for the cold-gas model.
4. **No static-only aero.** CP/Cd are computed live as functions of Mach + leg-deploy
   angle + depletion. OpenRocket is a comparison anchor, not the runtime source.
5. **No live FEA in the flight loop.** Structural analysis is event-triggered on logged
   load cases (§2.3). Landing impact is the priority case.
6. **No throttleable-thruster fantasy.** Cold gas is bang-bang on/off through fixed
   nozzles. Authority comes from pulse timing + which nozzles, not continuous throttle.
7. **No collapsing the controller seam.** Keep `ControllerBackend` swappable between SIL
   and Renode; the plant must not import controller internals.
8. **No pass/fail verdicts on physics.** Emit data + plots (§7).
9. **No network dependency at sim runtime.** Fetch packages at build time only.
10. **No silent stubbing.** Every placeholder/stub gets a PROGRESS.md + ASSUMPTIONS.md
    entry stating what's faked and what real work remains.
11. **Determinism is sacred.** Thread the master seed everywhere; never call an
    unseeded RNG.
12. **Don't fake completion at the budget limit.** Stop, summarize, name the next step.
13. **Don't gold-plate early phases.** Time is free, but spend it on the §7.3 rigor
    activities (convergence, MC, sensitivity, soak), NOT on polishing Phase 1's tests for
    hours while Phases 8–17 never get built. Each phase: reach its full test bar, commit
    green, move on. Heavy compute belongs in phases 13–17.
14. **Don't sacrifice rigor or physical accuracy for speed.** If a choice is between a
    fast approximation and a slow correct model, take the slow correct one and let it run.
    The only thing you optimize for is correctness + evidence, not wall-clock.
15. **Don't regress the keystone.** Once the Phase-8 end-to-end SIL flight is green, run
    the FULL test suite before every commit; no later phase (thermal, structural, Renode,
    MC) may break an earlier one. Commit only green; push to main after each green gate.
16. **Don't assert on physics outcomes.** Asserts are for code/conservation/convergence/
    determinism only. Flight results are data + plots (§7.5).

---

## 9. REFERENCES (plain-text URLs — verify before relying)

Codex `/goal` mechanics & best practices:
- https://developers.openai.com/codex/use-cases/follow-goals
- https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex

Renode (deterministic multi-node co-sim, runs real firmware, sensor→actuator HIL):
- https://renode.io/
- https://renode.readthedocs.io/en/latest/introduction/supported-boards.html
- Xtensa/ESP32 ISA support: https://antmicro.com/blog/2022/01/xtensa-isa-in-renode-for-sof-project
- SystemC/virtual-time co-sim + time sync: https://antmicro.com/blog/2024/07/systemc-co-simulation-in-renode
- Synchronized sensor injection (RESD): https://renode.io/news/synchronized-multi-sensor-data-in-renode-with-resd/
- Programmatic control: pyrenode3 (see the renode/renode GitHub README)

CO2 cold-gas thermodynamics (two-phase storage, evaporative replenishment, draw-rate limit):
- TALARIS cold-gas hopper, MIT: https://dspace.mit.edu/bitstream/handle/1721.1/67069/758664618-MIT.pdf;sequence=2
- CoolProp (real-gas CO2 properties, Span–Wagner EOS): http://www.coolprop.org/

Reference 6-DOF rocket flight sim (quaternion, variable mass — established methodology to mirror):
- RocketPy: https://docs.rocketpy.org/

Aerodynamics / stability (extended Barrowman; static margin):
- OpenRocket technical documentation (for the build-up method + as the comparison anchor):
  https://openrocket.info/documentation.html

Motor data:
- ThrustCurve (motor `.eng`/`.rse` files): https://www.thrustcurve.org/
