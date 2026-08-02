# Status

- Updated: 2026-08-01 America/Los_Angeles
- Completed phase: Phase 2 — 27-cell controlled RL study
- Current experiment: Phase 3 / `02_dofbot`; Goal 4 corrected front-side,
  no-contact reaching passed all gates; the first lower/farther world-down
  pre-grasp is rejected; the first angled terminal-finger machine attempt
  failed narrowly; the direct validated-joint-candidate now reaches its exact
  API endpoint remotely, but Isaac joint tracking still fails under load; the
  isolated three-case actuator matrix now proves gravity dependence, falsifies
  effort-250 as a sufficient fix, and the local follow-up now separates
  position-derived settling from incompatible raw velocity; the completed
  four-case solver/drive matrix repairs velocity telemetry but does not repair
  the approximately five-degree gravity-on joint tracking error; the completed
  official-asset audit corrected the prior torque-evidence interpretation; the
  completed five-case drive-model matrix rejects the old high-gain force drive
  as unstable and improves the best stable error to `1.73936°`, but no case
  passes the unchanged one-degree gate; the completed GPU-free residual-force
  audit explains the `100`/`5.2` invariance at high confidence as a non-binding
  impulse limit, rejects joint-frame correction as the primary fix, and
  selects bounded gravity-compensation feed-forward; after one fail-closed
  Warp/Torch setter-boundary error and a minimal native-Warp repair, the
  isolated machine matrix now reduces the worst settled error from `1.73936°`
  to `0.002391°` with zero contact and zero effort clipping; the accepted
  actuator contract now passes GPU-free pre-grasp runtime integration; the
  first integrated machine run passed its actuator gates and exposed repeated
  smoothstep reissue lag; the repaired headless rerun proves no-reissue is
  active but insufficient, with `4.17702°` tracking error and `0.0318089 m`
  position error; later target-buffer and projected-force discriminators
  proved command propagation and complete telemetry without resolving the
  residual; the DF-035 single 2000-ms boundary then reproduced
  `4.196145 degrees / 0.0318115 m`, falsifying trajectory segmentation as a
  sufficient repair; 40 historical failure, falsification, partial-fix, and
  operational cases are consolidated in
  `experiments/02_dofbot/FAILURE_LEDGER.md`; no new paid discriminator is
  selected until the passing isolated calibration and failed integrated task
  contexts are compared offline; Viewer remains blocked
- Brev instance: `isaac-launchable-f150a5` (`92xbacz46`)
- Instance state: `STOPPED`, re-verified with `brev ls --all --json` at
  2026-08-01 19:25 PDT after the DF-035 evidence retrieval
- Billable GPU compute still running: no
- Remaining resource: 256 GiB persistent disk, approximately `$0.04/hour`
  from the deployment quote
- Deletion status: not requested; instance and disk preserved
- Latest live L4 quote: existing AWS `g6.4xlarge` class displayed
  `$1.58784/hour` compute; rechecked 2026-08-01 before the DF-035 run

## DOFBOT Goal 4 fixed-tabletop reaching gate

- Branch: `codex/dofbot-goal4-jacobian-compat`; corrected remote commit
  `eb7a266`; PR #21
- Historical rear-side remote commit: `d12b987`
- Scope: safe reach/approach/retract only; no target contact, pushing, grasping,
  lifting, placing, gripper command, camera controller input, learning, or real
  hardware
- Scene contract:
  `configs/dofbot/reaching/goal4_fixed_tabletop.json`
- Corrected v2 base-frame contract: world `+Y` is workspace front and world
  `-Y` is the Jetson/electronics rear. The complete official robot asset stays
  fixed.
- Corrected v2 physical composition: collision-enabled static table centered
  at `(0.00, +0.25, 0.10) m`, with top at `z=0.12 m`; collision-enabled static
  5 cm red cube centered at `(0.00, +0.18, 0.145) m` and resting exactly on
  the table; the nearest tabletop edge remains 10 cm in front of the base
- End-effector contract: `Wrist_Twist`; approach waypoint
  `(0.00, +0.18, 0.235) m`, nine centimeters above the cube center
- Corrected v2 scripted comparison: five ActionChunk poses, with the three
  non-neutral poses mirrored around 90° to
  `[90,82,80,82]`, `[90,76,75,79]`, and `[90,82,80,82]`; 20 official
  pose-boundary `Arm_serial_servo_write(id, angle, time)` calls, neutral
  start/end, and 60°-120° safe angles
- State controller: 5 Hz damped-least-squares translation Jacobian, at most 30
  steps, at most 4° per joint per step, same absolute-angle Yahboom API
- Corrected v2 local fail-closed gates: fixed `+Y` work-front and `-Y`
  electronics-rear vectors, rejection of a rear-side table or relabeled
  frame, physical table/cube geometry, static target, keepout, end-effector
  body, controller cadence and safe envelope, Jacobian shape/finite math,
  bounded API output, synthetic pass/failure evaluation, reset, no
  hardware/Isaac use in dry-run, and mirrored Viewer-camera wiring
- Corrected v2 local validation: all 112 repository tests pass, including 15
  focused Goal 4 tests, Git LFS checks, and remote command previews; targeted
  Ruff, shell syntax, the local dry-run, and both reach command previews also
  pass
- Corrected v2 remote Viewer evidence:
  `artifacts/dofbot/reaching_viewer_contract.json`, cycle 27, SHA-256
  `87faa5f892553c093dc190e331967990676672e4b383587e21a298cd8446d893`
- Machine gates: physical prims and static target present,
  live asset compatibility, angle envelope, four-centimeter table clearance,
  at least three-centimeter distance improvement for both the scripted and
  state-based approaches, final state distance at most four centimeters, exact
  API call count, neutral reset within one degree, the fixed front/rear frame,
  and table/cube placement on the physical work side
- Viewer contract: 20-second neutral connection hold followed by a loop of the
  scripted comparison and state-based approach
- Corrected v2 remote machine result: **passed**. All fourteen checks passed;
  the headless scripted distance improved from `0.18821 m` to `0.07579 m`,
  the state controller improved from `0.21226 m` to `0.02037 m`, minimum
  wrist/table clearance was `0.13258 m`, 52/52 official API calls were
  accounted for, and neutral reset error was `0.2295 deg`
- Corrected v2 Viewer machine result: **passed**. The downloaded cycle-27
  artifact again passed 14/14 checks; its state-controller final distance was
  `0.02037 m`, minimum clearance was `0.13258 m`, and neutral reset error was
  `0.2028 deg`
- Corrected v2 Viewer result: **passed for safe no-contact reaching**. The user
  confirmed that the table/cube and Jetson/electronics are on opposite sides
  and that the arm approaches in the correct direction. The open gripper and
  static cube were visible, and four screenshots were reviewed but not
  committed.
- Motion-quality limitation: the user correctly observed only roughly
  30°-45° of required visible bending and an awkward motion. The target/table
  are close and high, the controlled point is `Wrist_Twist` rather than the
  fingertip grasp frame, and the 5 Hz translation-only damped-least-squares
  controller does not constrain gripper orientation or prefer a natural elbow
  posture. These are expected baseline limitations, not evidence of grasp
  readiness.
- Current acceptance: **local passed / corrected remote machine passed /
  corrected user Viewer passed**. Goal 4 is complete for safe, policy-free,
  no-contact reaching only.
- Next free local gate: recalibrate table height and target reach distance,
  define a fingertip/grasp pose frame, and design pose-aware IK with preferred
  posture and smoother velocity/acceleration before any contact, pushing,
  grasping, or placing experiment.
- Compute lifecycle: the existing instance was started after the unchanged
  `$1.58784/hour` quote was verified. Stop was requested at approximately
  08:35 PDT after artifact retrieval and human review; Brev reported
  `STOPPING` during asynchronous cleanup and terminal `STOPPED` at 08:44 PDT.
  The instance and persistent disk were retained; neither was deleted or
  resized.

## DOFBOT pre-grasp scene calibration gate

- Branch: `codex/dofbot-pregrasp-scene-calibration`
- Scope: local scene geometry only; no Brev/GPU start, Isaac execution, new
  joint motion, real hardware, gripper command, cube contact/motion, camera
  controller input, policy, checkpoint, PPO, or VLA
- Immutable baseline: Goal 4's accepted config plus
  `artifacts/dofbot/reaching_viewer_contract.json`, SHA-256
  `87faa5f892553c093dc190e331967990676672e4b383587e21a298cd8446d893`;
  all 14 recorded machine checks passed, and its validated neutral
  `Wrist_Twist` origin radius is `0.33865 m`
- Candidate config:
  `configs/dofbot/reaching/goal4_pregrasp_scene_candidate.json`
- Candidate geometry: the axis-aligned tabletop stays horizontal, its center
  moves from `(0.00, +0.25, 0.10) m` to `(0.00, +0.31, 0.06) m`, its top
  drops from `z=0.12 m` to `z=0.08 m`, and its nearest edge moves from
  `y=0.10 m` to `y=0.16 m`
- Candidate target: the static 5 cm cube moves from
  `(0.00, +0.18, 0.145) m` to `(0.00, +0.25, 0.105) m`, still rests exactly
  on the table, and leaves at least `0.065 m` to every tabletop edge
- Candidate waypoint: `(0.00, +0.25, 0.195) m`; its origin radius is
  `0.31706 m`, leaving a `0.02159 m` necessary radial margin inside the
  validated neutral-wrist radius. This is a geometry plausibility check, not
  an IK, collision, posture, dynamics, or visual proof.
- Controller-reuse warning: the accepted Goal 4 final observation already had
  one recorded joint at `59.50°`, reaching the 60° lower safety boundary
  within the machine gate's 1° measurement tolerance. Therefore the existing
  translation-only controller is explicitly **not certified** for this
  lower/farther candidate; the radial margin must not be read as joint-space
  reach evidence.
- Local command:

  ```bash
  make dofbot-pregrasp-dry-run
  ```

- Evidence:
  `artifacts/dofbot/pregrasp_scene_calibration.json` and the side/top
  `artifacts/dofbot/pregrasp_scene_calibration.svg`
- Local acceptance: **passed 20/20 geometry and provenance checks**. All 119
  repository tests passed, including seven focused calibration tests; the
  candidate changes scene positions only and leaves the accepted scripted
  actions, state controller, frame, API boundary, and `Wrist_Twist` anchor
  unchanged for comparison, not as a claim that the old controller is
  sufficient.
- Candidate acceptance: **local geometry passed / Isaac machine pending /
  Viewer pending**. Contact and grasp remain unauthorized. A later paid gate
  must prove pose-aware IK, collision clearance, posture quality, and the
  user-visible lower/farther scene before this candidate replaces the
  accepted Goal 4 baseline.

## DOFBOT pose-aware terminal-finger pre-grasp gate

- Branch: `codex/dofbot-pose-aware-pregrasp`
- Scope: local controller and remote-runner preparation only; no Brev/GPU
  start, Isaac execution, real hardware, wrist-twist or gripper command, cube
  contact/motion, camera controller input, policy, checkpoint, PPO, or VLA
- Pose config:
  `configs/dofbot/pregrasp/goal5_pose_aware_pregrasp.json`
- Grasp frame: origin is the midpoint of official bodies
  `Finger_Left_03` and `Finger_Right_03`; closing is left-to-right terminal
  finger; approach is `Wrist_Twist` to the terminal-finger midpoint,
  orthogonalized against closing
- Target: terminal-finger midpoint at `(0.00,+0.25,0.195) m`, approach axis
  world `-Z`, closing axis world `+X`, position tolerance `0.025 m`,
  approach tolerance `12°`, and closing tolerance `20°`
- API boundary: only `joint1`-`joint4` are optimized and emitted through
  four `Arm_serial_servo_write(id, angle, time)` calls per control step.
  Wrist twist and the gripper remain uncommanded. Closing-axis alignment is a
  monitor-only gate because the current four-servo API does not control it.
- Controller: 5 Hz weighted damped-least-squares over the averaged two
  terminal-finger `6x4` link Jacobian, with translation plus approach-axis
  error and a preferred `[90,78,78,90]°` posture
- Motion safety: `[60,120]°` envelope with an 8° command margin,
  integer-degree commands, at most 4° per step, 20°/s velocity, and 60°/s²
  acceleration
- Collision safety: local signed point-to-box body-center proxies reject table
  or target encroachment; the remote scene enables Isaac contact reporting
  for every DOFBOT rigid body and rejects critical-body force above `0.5 N`.
  The target remains static and contact remains unauthorized.
- Local command:

  ```bash
  make dofbot-pregrasp-pose-dry-run
  ```

- Local evidence: `artifacts/dofbot/pregrasp_pose_contract.json`; all 21
  preparation checks pass, including deliberate terminal-finger collision,
  excessive contact-force, and reversed fixed-closing-axis rejection
- Local validation: all 139 repository tests pass, including 27 focused
  pose/runner tests; targeted Ruff, shell syntax, dry-run generation, Git LFS
  checks, and both remote command previews pass
- Remote validation branch:
  `codex/dofbot-pregrasp-remote-validation`; machine commit `05ececc`
- Remote machine result: **failed closed**. Position error improved from
  `0.33035 m` to `0.07212 m`, but the required `0.025 m` position tolerance
  and `12°` top-down approach tolerance were not met; final approach error was
  `103.21°`. The command trajectory braked to `[90,69,69,69]°` before the
  68° API margin while the observed joints remained within the 60°-120°
  physical envelope.
- Safety result: all velocity, acceleration, collision-proxy, no-contact,
  static-target, exact 248-call, API-margin, and neutral-reset checks passed;
  maximum reported contact force was `0 N`, and neutral reset error was
  `0.2886°`.
- Evidence:
  `artifacts/dofbot/pregrasp_machine_failure_2026-07-29.json`, summarizing the
  retrieved 326,627-byte machine artifact with SHA-256
  `bc0ff9942be17fb542c9b56dc8cd04aa9bf2af4093ec97be4488fb7c34c7b8e5`
- Viewer result: **not run** because the machine gate failed; no Viewer URL or
  visual acceptance claim was produced.
- Candidate acceptance: **local preparation passed / first Isaac machine
  candidate failed / Viewer blocked**. Goal 5 is not complete, and contact or
  grasp remains unauthorized.
- Local reachability branch: `codex/dofbot-multistart-reachability`
- Local calibration: twelve recorded Isaac observations from steps 0-11 fit a
  planar three-pitch-chain model with `0.00203 m` maximum position residual,
  `0.00136 m` RMS position residual, and `0.00246°` maximum approach residual.
- Exhaustive result: all `226,981` integer-degree combinations in the
  `[60,120]°` physical envelope and all `91,125` combinations in the
  `[68,112]°` command-margin envelope were evaluated across nineteen visible
  workspace-front posture branches. Neither search produced a candidate.
- Global rejection: even ignoring position, the theoretical world-down
  approach error is bounded below by `88.41°` over the physical envelope and
  `112.41°` over the command-margin envelope, versus the `12°` tolerance. The
  coupled world-down pose requires `0.35791 m` of proximal reach, while the
  calibrated first two links provide only `0.19656 m`, a `-0.16134 m` margin
  even before joint-angle bounds.
- Evidence: `artifacts/dofbot/pregrasp_reachability.json`; all sixteen local
  provenance, residual, exhaustive-search, rejection, and no-runtime-action
  checks pass.
- Candidate acceptance: **search contract passed / current target infeasible /
  revised candidate absent / GPU and Viewer blocked**. This is a bounded
  planar-model conclusion, not Isaac dynamics or collision acceptance.
- Next design gate: choose between preserving the current safety envelope and
  revising the approach/scene, or separately calibrating a wider envelope.
  The current lower/farther world-down target must not receive another paid
  run unchanged.

## DOFBOT revised angled pre-grasp local design gate

- Branch: `codex/dofbot-taskspace-candidate-search`
- Scope: local pure Python joint/scene/approach design only; no Brev start,
  GPU, Isaac runtime, policy, real-hardware command, wrist-twist or gripper
  command, contact, or grasp authorization
- Command:

  ```bash
  make dofbot-pregrasp-taskspace
  make dofbot-pregrasp-pose-dry-run
  ```

- Provenance: the search binds the accepted Goal 1 asset contract, the
  machine-passed ActionChunk motion contract, the calibrated reachability
  config, and the immutable first-pose rejection artifact by SHA-256.
- Search coverage: all `226,981` physical-envelope combinations in
  `[60,120]°` and all `148,877` candidate-envelope combinations in
  `[64,116]°` were evaluated at 1° resolution. The latter stays two degrees
  inside the machine-validated `[62,118]°` command span.
- Low-table conclusion: among meaningful front/up approaches, the minimum
  derived table top is `0.17945 m` at `[90,60,60,60]°`, a zero-margin
  physical-boundary pose. Therefore the requested `<=0.12 m` table is
  rejected without weakening a safety threshold.
- Selected candidate: exactly one posture passes all strict filters:
  `[90,66,66,66]°`; terminal-finger midpoint
  `(-0.00071,+0.22052,0.28278) m`; approach axis
  `(0,+0.94213,+0.33526)`; cube center
  `(-0.00071,+0.29589,0.28660) m`; horizontal table top `z=0.26160 m`.
- Margins: 6° from the physical envelope, 2° inside the candidate envelope,
  2.12 cm raw terminal/table clearance, 5.04 cm raw terminal/cube clearance,
  and 4.15 mm minimum reserve after subtracting the fitted model's 2.03 mm
  maximum position residual and the configured clearance thresholds.
- Configs:
  `configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json`,
  `configs/dofbot/pregrasp/goal5_angled_pregrasp.json`, and
  `configs/dofbot/pregrasp/goal5_taskspace_search.json`
- Evidence: `artifacts/dofbot/pregrasp_taskspace_candidate.json`; all 30
  provenance, exhaustive-search, candidate-linkage, margin, and no-runtime
  checks pass. The generalized pose dry-run also passes 21/21 checks for both
  the new angled candidate and the historical world-down fixture.
- Validation: all 154 repository tests, targeted Ruff, shell syntax, Git LFS
  attributes, both remote command previews, and `git diff --check` pass.
- Acceptance: **local design passed / Isaac machine pending / Viewer
  pending**. The result is calibrated task-space evidence, not Isaac
  kinematics, self-collision, dynamics, contact, grasp, or visual proof.
- Infrastructure: `brev ls --json` re-verified
  `isaac-launchable-f150a5` (`92xbacz46`) as `STOPPED` at 20:31 PDT. No
  instance, disk, or hardware was created, resized, started, or deleted.

## DOFBOT angled pre-grasp machine failure and local controller correction

- Remote baseline: merged `main@7b4591f`, existing
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4,
  quoted at `$1.58784/hour`; no instance/disk creation, resize, or deletion
- Headless command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp
  ```

- Machine result: **failed closed**. Position error improved from
  `0.25660 m` to `0.03382 m`, but remained outside the unchanged `0.025 m`
  gate; approach error was `13.568°`, outside the unchanged `12°` gate.
  Closing error was `0.321°`.
- Safety result: all sixteen non-pose safety/API/reset checks passed, including
  physical table/static cube presence, joint envelope, command margin,
  velocity, acceleration, collision proxies, static/no-contact target,
  exact `248/248` official API calls, and neutral reset within `0.0613°`.
  Maximum reported contact force was `0 N`.
- Root cause: the scene target was derived from the safe joint candidate
  `[90,66,66,66]°`, but Cartesian DLS converged to API command
  `[90,65,67,76]°` and observed
  `[89.989,65.073,68.603,77.889]°`, trading away from the selected joint
  branch. Increasing the offline candidate boundary margin from 2° to 3°
  leaves zero candidates, so silently tightening the old search is not a
  viable correction.
- Evidence:
  `artifacts/dofbot/pregrasp_angled_machine_failure_2026-07-29.json`;
  it summarizes the retrieved 327,197-byte machine artifact with SHA-256
  `396e19b56805f7771aeee284e9722b49be3bf2006c999d42d32baaafc0ecd555`.
- Viewer: **not started**, because the headless gate failed. There is no
  visual acceptance claim.
- Local correction branch:
  `codex/dofbot-isaac-tracking-calibration`. The angled pose now declares
  `control_mode=validated_joint_candidate` and smoothly tracks its selected
  joint pose through the same four official Yahboom API calls. The historical
  world-down fixture retains `control_mode=cartesian_pose_ik`.
- Unchanged gates: target position/orientation, scene geometry, command
  margins, per-step delta, velocity, acceleration, collision/contact,
  exact API count, and neutral reset are not loosened. Actual terminal-finger
  Cartesian position and axes remain the machine pass/fail authority.
- Local result: task-space evidence passes `33/33`; pose dry-run passes
  `21/21`; Git LFS checks, remote command previews, all `155` repository
  tests, targeted Ruff, and `git diff --check` pass.
- Acceptance: **local correction passed / corrected Isaac machine pending /
  Viewer blocked pending machine pass**. Contact and grasp remain
  unauthorized.
- Compute lifecycle: the instance started at approximately 20:02 PDT. A clock
  audit at 21:12 PDT found that the intended 30-minute paid cap had been
  exceeded; stop was requested immediately, repeated idempotently when the
  control plane remained `STOPPING`, and terminal `STOPPED` was verified at
  approximately 21:17 PDT. This roughly 75-minute window exceeded the intended
  cap and is recorded as an operational failure. The instance and disk were
  retained.

## DOFBOT direct-candidate command-space correction

- Remote source: merged `main@150fa5d`; approved existing
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4
- Machine result: **failed closed only on position**. Final position error was
  `0.03243 m` against `0.025 m`; approach and closing errors passed at
  `10.397°` and `0.313°`. All safety/API/reset checks passed, including
  `0 N` contact, a static cube, `248/248` official calls, and `0.0689°`
  neutral reset. Viewer was not started.
- Endpoint evidence: configured candidate `[90,66,66,66]°`; final API command
  `[90,66,68,69]°`; final observed joints
  `[89.980,66.328,70.529,71.535]°`
- Diagnostic falsification: temporary preferred
  `[90,66,64,64]°` produced final API `[90,66,70,67]°`, final observed
  `[89.982,66.168,72.067,69.270]°`, and `0.03211 m` position error. Merely
  lowering preferred angles does not control the old implementation's
  endpoint.
- Located root cause: direct-candidate deltas used observed joint angles while
  quantized velocity/acceleration/braking used the previous API command. The
  prior single-step regression did not prove the complete stopped command
  sequence.
- Fix branch: `codex/dofbot-command-space-tracking-fix`
- Correction: direct candidates now advance exclusively in command space;
  observations retain every physical/Cartesian/collision/contact gate; the
  machine contract requires an exact stopped candidate endpoint; unreachable
  boundary candidates are rejected before Kit launch. Cartesian IK behavior
  remains separate.
- Evidence:
  `artifacts/dofbot/pregrasp_joint_candidate_machine_failure_2026-07-29.json`
  and `artifacts/dofbot/pregrasp_command_space_contract.json`. The latter
  injects the remote tracking-lag neighborhood and reaches exact stopped
  `[90,66,66,66]°` in eight bounded steps with 22/22 local checks.
- Validation: `make test` passes all 159 repository tests; targeted Ruff,
  byte-identical artifact regeneration, both remote dry-run previews, JSON
  parsing, and `git diff --check` pass. Full-repository Ruff has one
  pre-existing unrelated line-length finding in
  `tools/collect_environment_info.py:47`.
- Acceptance: **local command-space correction passed / corrected Isaac
  machine pending / Viewer blocked pending machine pass**. The position,
  approach, collision, contact, command, reset, and no-grasp gates are not
  loosened.
- Compute lifecycle: the approved window started at 21:40:39 PDT; stop was
  requested after evidence retrieval, `brev refresh` cleared stale list state,
  and `brev ls --json` explicitly returned `STOPPED` at 21:55 PDT. The
  instance and disk were retained.

## DOFBOT exact-command failure and actuator-diagnostic preparation

- Remote source: merged `main@54b25ed98d325f5079daf5d34bec3ad1629ee136`;
  existing `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`,
  NVIDIA L4, quoted `$1.58784/hour`
- Official command:
  `BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp`
- Result: **failed closed only on Cartesian position**. The API command now
  reached the exact stopped `[90,66,66,66]°` candidate, proving the prior
  command-space bug is fixed. Observed joints instead settled at
  `[90.093,66.987,70.641,69.828]°`, a maximum `4.641°` tracking error.
- Cartesian/safety evidence: position improved
  `0.25660 -> 0.03213 m` against the unchanged `0.025 m` gate; approach and
  closing passed at `9.465° / 0.412°`; all collision, static-target,
  no-contact, API-count, command-margin, and reset gates passed; maximum
  contact was `0 N`; Viewer was not started.
- Diagnosis boundary: the final planned command velocity was zero and contact
  was `0 N`, but the old artifact did not record actual `joint_vel`,
  `joint_pos_target`, resolved drive buffers, or computed/applied torque.
  Multiplying error by stiffness is compatible with solver effort clipping,
  but it cannot distinguish clipping from a target-buffer mismatch, unresolved
  settling, implicit-drive semantics, joint-axis mapping, self-collision,
  solver configuration, or mass/inertia effects.
- Local preparation keeps the default effort limit at `100`, retains the
  independent `<=1°` `final_api_joint_tracking_within_tolerance` pre-grasp
  gate, and adds
  `configs/dofbot/calibration/goal5_actuator_diagnostic.json`.
- The future diagnostic runs exactly three isolated cases:
  gravity-on/effort-100, gravity-off/effort-100, and
  gravity-on/effort-250. Every case uses the same neutral, mid-load,
  `[90,66,66,66]°` candidate, and neutral-return poses through sixteen
  official API calls.
- Per-physics-step evidence includes API command, backend interpolated target,
  Isaac `joint_pos_target`, observed `joint_pos` and actual `joint_vel`,
  resolved stiffness/damping/effort-limit buffers, computed/applied torque
  as implicit PD estimates only, optional PhysX mass/inertia/DOF properties, terminal body
  positions, and monitored contact. Missing optional fields are recorded as
  null together with probe error details; implicit zero or unavailable torque
  buffers are explicitly
  non-evidence. When nonzero computed/applied buffers exist, the case also
  records their maximum gap and whether applied effort reached 98% of the
  configured limit.
- Settling is based on actual velocity below `0.1°/s` for `0.5 s`, not on
  planned command velocity. Case completion, tracking pass, and matrix
  classification are separate so a tracking failure still produces useful
  evidence. The 2-second smoothstep has bounded 18°/s peak velocity and
  36°/s² peak acceleration, inside the existing 20°/s and 60°/s² limits.
- The decision tree prioritizes contact/self-collision, settling instability,
  target-buffer mismatch, and telemetry/runtime compatibility before comparing
  gravity and effort controls. Implicit-actuator torque buffers do not directly
  measure solver torque or prove saturation. The wrapper prints
  an internal matrix exit code while returning outer success to prevent Brev
  from retrying the paid matrix automatically; the local wrapper parses that
  code and fails `make` when the internal matrix failed.
- Evidence:
  `artifacts/dofbot/pregrasp_joint_tracking_failure_2026-07-29.json`;
  full retrieved artifact was 327,442 bytes with SHA-256
  `50efb65e1b31299e3e39fb517f024b4762ea68773d6c7a58e2a62df6e0d57033`.
  The deterministic local preparation evidence is
  `artifacts/dofbot/actuator_calibration_plan.json`.
- Local validation: all 171 repository tests pass, including strict config,
  synthetic failure-routing, stale-artifact, Git-commit/SHA, and remote-command
  preview checks; targeted Ruff, Python compilation, shell syntax,
  deterministic plan regeneration, JSON parsing, and `git diff --check` pass.
- Resource lifecycle: approved start at 22:42:05 PDT; machine evidence was
  retrieved before stopping; `brev ls --json` explicitly returned `STOPPED`
  at 22:55:05 PDT. A read-only check during local preparation again returned
  `STOPPED` at 23:17 PDT. The instance and disk were retained.
- Acceptance: **remote exact API endpoint passed / Isaac joint tracking and
  Cartesian position failed / local actuator diagnostic prepared / diagnostic
  matrix and Viewer pending**. Pre-grasp rerun, contact, closing, grasping,
  lifting, and placing remain unauthorized.

## DOFBOT actuator diagnostic remote result

- Remote provenance: merged `main@95b0ab1`, runtime-fix commit
  `abd109f38dba838557910ed1ab439749cbd53120`, config SHA-256
  `e3be35ad14617c252151cdbf9d6090fd7655f9e96ba3600bb659cc9f577cf6f9`.
  Existing `isaac-launchable-f150a5` (`92xbacz46`) remained the approved AWS
  `g6.4xlarge` / NVIDIA L4; no instance or disk was created, resized, or
  deleted.
- The first matrix attempt executed the poses but exposed an Isaac
  6.0.1 compatibility defect while serializing an optional PhysX array:
  `TypeError: Object of type array is not JSON serializable`. The launcher
  still returned zero. Commit `abd109f` normalizes tensor/NumPy values to JSON,
  persists a log per case, and fails a case when its artifact is missing.
- The repaired matrix completed all three cases with
  `[MATRIX_EXIT_CODE] 0`, `matrix_complete=true`, and zero monitored contact:
  - gravity off / effort 100 passed: maximum tracking error `0.00316°`,
    maximum terminal reported velocity `0.04567°/s`;
  - gravity on / effort 100 failed: maximum tracking error `4.97619°`,
    maximum terminal reported velocity `16.34411°/s`;
  - gravity on / effort 250 produced exactly the same selected target,
    position, and velocity sequence as effort 100, despite confirmed
    `250` effort buffers and PhysX maximum-force write. The recorded
    applied-torque value is an implicit PD estimate, not measured solver torque.
- The API, backend target, and Isaac target buffer agree within
  `0.0000013°`, and every case recorded `0 N` contact. Gravity dependence is
  therefore established, while increasing only `effort_limit_sim` from
  `100` to `250` is falsified as a sufficient correction.
- The gravity-on candidate's last twelve position samples span `0.183 s` and
  vary by at most `0.0000103°` per joint, yet raw `joint_vel` reports as much
  as `16.344°/s`. Isaac also warns that this TGS configuration may produce
  noisy velocities. The current automatic
  `settling_or_drive_stability_failure` is therefore not a safe final
  diagnosis: raw velocity is a compatibility signal, not a trustworthy sole
  settling criterion in this runtime.
- Durable evidence:
  `artifacts/dofbot/actuator_calibration_contract.json` and
  `artifacts/dofbot/actuator_calibration_result_2026-07-30.json`. Full case
  JSON and logs were retrieved locally but remain ignored; their exact sizes
  and SHA-256 values are bound by the concise result artifact.
- Resource lifecycle: paid start at 08:16:04 PDT; stop requested after artifact
  retrieval at 08:36:28 PDT, 20 minutes 24 seconds after start. Brev's
  asynchronous transition and list refresh reached explicit `STOPPED` at
  08:50:21 PDT, 34 minutes 17 seconds after start. No instance or disk was
  created, resized, or deleted.
- Acceptance: **matrix machine execution passed / gravity-on actuator
  tracking failed / effort-250 hypothesis falsified / velocity instrumentation
  requires correction / pre-grasp and Viewer blocked**. No pre-grasp, Viewer,
  contact, closing, grasping, lifting, or placing ran in this paid window.

## DOFBOT velocity-contract repair and solver/drive preparation

- Offline evidence replay uses the exact retrieved case JSON bound by the
  promoted result artifact's byte counts and SHA-256 values. A `100 ms`
  finite difference of observed `joint_pos` is now the physical settling
  signal; raw `joint_vel` remains recorded as a compatibility signal.
- Gravity-on effort-100 and effort-250 both settle on every pose by the
  position-derived signal. Their maximum terminal derived speed is
  `0.041972°/s`, while raw speed reaches `16.363141°/s` and maximum
  raw/derived mismatch reaches `16.444165°/s`. The approximately
  `4.974117°` tracking error remains real.
- Gravity-off ends below the derived threshold at `0.025304°/s` and has only
  `0.085753°/s` maximum raw/derived mismatch. Its old record is right-censored:
  the original raw-velocity gate ended collection before a full new derived
  `500 ms` hold, so this replay does not rewrite the historical machine result.
- The runner now fails closed if position-derived telemetry is unavailable,
  if a pose does not settle by position difference, or if raw and derived
  velocity differ by more than `1°/s` during settling.
- The next remote-only matrix is locally locked to four gravity-on,
  effort-100 cases: baseline TGS; external forces applied each TGS position
  iteration; then two velocity iterations; then damping `100 -> 50`.
  Each stage changes exactly one field. Stiffness remains `10000`, position
  iterations remain `8`, and the rejected effort-250 comparison is not
  repeated.
- Local evidence:
  `artifacts/dofbot/actuator_velocity_reanalysis_2026-07-30.json` and
  `artifacts/dofbot/solver_drive_diagnostic_plan.json`.
- Validation: all `178` repository tests passed, including Git LFS checks,
  remote-command previews, velocity/solver contract tests, Python compilation,
  targeted Ruff, shell syntax, JSON parsing, and `git diff --check`.
- Acceptance: **offline velocity diagnosis passed / solver-drive plan passed /
  remote Isaac result pending / pre-grasp and Viewer blocked**. No Brev,
  Isaac, Viewer, camera, contact, grasp, hardware, policy, or checkpoint
  command was issued during this local work.

## DOFBOT solver/drive remote result

- Provenance: merged `main@02f27d259d271a5bb01a9739c1c270db702de9f7`;
  config SHA-256
  `5ae01f684857f78fb3eb973cf32655617a18eb3ec8d3847e20631140a0bb018d`.
  The approved retained instance remained
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4,
  at the rechecked `$1.58784/hour` compute quote.
- Command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-solver-drive
  ```

- Machine execution passed with `[MATRIX_EXIT_CODE] 0`,
  `matrix_complete=true`, and decision
  `external_force_iteration_repairs_velocity_telemetry_only`.
- Results:
  - baseline TGS: `4.97412°` tracking error, `0.04190°/s` derived speed,
    `16.36310°/s` raw speed, and `16.44402°/s` mismatch;
  - external forces every TGS iteration: mismatch fell to `0.09921°/s`,
    but tracking error remained `5.04065°`;
  - two velocity iterations: `5.04064°` tracking error, indistinguishable
    from the preceding case;
  - damping 50: tracking improved only to `4.88333°`, still far outside the
    unchanged `1°` gate.
- Every case settled by position difference, matched the backend target buffer
  within `0.0000017°`, and recorded `0 N` monitored contact. Joint 3 remains
  the largest-error controlled joint at the candidate pose.
- Established: external-force iteration repairs the runtime's noisy raw
  velocity telemetry. Falsified: that telemetry defect causes the position
  error; two velocity iterations fix tracking; or halving damping fixes
  tracking.
- Durable evidence:
  `artifacts/dofbot/solver_drive_diagnostic_result_2026-07-30.json`. It binds
  the ignored four multi-megabyte case JSON files, four logs, and retrieved
  matrix contract by exact byte size and SHA-256.
- Resource lifecycle: artifacts were retrieved before stop; standard
  `brev ls --json` reached explicit `STOPPED` at 18:12:50 PDT. No instance or
  disk was created, resized, or deleted.
- Validation: `179/179` repository tests, Git LFS attributes, remote command
  previews, targeted Ruff, promoted source SHA/size bindings, JSON parsing,
  and `git diff --check` passed.
- Acceptance: **matrix execution passed / velocity telemetry repair identified /
  all four tracking gates failed / pre-grasp and Viewer blocked**. No table,
  cube, camera, Viewer, pre-grasp, gripper, contact, hardware, policy, or
  checkpoint command ran.

## DOFBOT official-asset drive audit and next matrix preparation

- Scope: GPU-free official-USD inspection, evidence correction, diagnostic
  implementation, and remote-command preview. No Brev start, Isaac run,
  Viewer, task scene, contact, gripper, hardware, policy, or checkpoint ran.
- Official source: NVIDIA Isaac 6.0
  `Robots/Yahboom/Dofbot/dofbot.usd`, 104,922,919 bytes, SHA-256
  `52c524ebb26c38a3d164daee10f6cac0f15487fce5408a38c0c94199a37f1303`.
  The source USD was inspected only from temporary storage and is not
  committed.
- Established asset contract: meter scale, Z-up, the expected
  joint1-to-joint4 serial body chain, X axis on every controlled revolute
  joint, and uniform authored angular drives with type `acceleration`,
  stiffness `1048`, damping `53`, and maximum force `5.2`.
- Current composition boundary: the project overrides stiffness `10000`,
  damping `100`, and effort limit `100`, but previously did not override the
  authored acceleration drive type. Joint 3 is the largest runtime error but
  is not uniquely axised or uniquely tuned in the official USD.
- Evidence correction: Isaac Lab implicit-actuator `computed_effort` and
  `applied_effort` are approximate PD calculations, not measured PhysX solver
  torque. The old 100-to-250 run proves the effort-limit and PhysX
  maximum-force writes changed and the trajectory did not; it does not prove
  physical torque saturation.
- New five-case contract:
  `configs/dofbot/calibration/goal5_drive_model_diagnostic.json`. It holds
  gravity, trajectory, solver settings, and external-force iteration fixed,
  then changes exactly one field per stage: drive type, stiffness, damping,
  and maximum force. Runtime evidence reads back composed drive type, gains,
  axis, bodies, and maximum force for every controlled joint before motion.
- GPU-free commands:

  ```bash
  make dofbot-drive-model-dry-run
  BREV_INSTANCE_NAME=preview-only make show-dofbot-drive-model
  ```

- Evidence:
  `artifacts/dofbot/asset_drive_audit_2026-07-30.json` and
  `artifacts/dofbot/drive_model_diagnostic_plan.json`.
- Validation: `185/185` repository tests, targeted Ruff, Python compilation,
  shell syntax, JSON parsing, Git LFS attribute checks, deterministic plan
  regeneration, and the headless remote-command preview pass.
- Acceptance: **official-asset audit passed / five-case plan passed locally /
  root-cause hypothesis unproven / paid run, pre-grasp, and Viewer blocked**.
  After merge, a fresh quote, and explicit approval, the next paid command is
  `BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-drive-model`.

## DOFBOT drive-model remote result

- Provenance: merged `main@d2abb247a188c23889778cfdd1f211f2bc8dd1a1`;
  config SHA-256
  `7644ca7f88f0fbcda2b041fc4eb5fd79f4aa21560dbf054c6da4e453f118bddd`.
  The retained instance remained AWS `g6.4xlarge` / NVIDIA L4 at the freshly
  confirmed `$1.58784/hour` quote.
- Command:

  ```bash
  BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-drive-model
  ```

- Machine execution completed all five case JSON/log pairs with
  `[MATRIX_EXIT_CODE] 0`, `matrix_complete=true`, exact target-buffer
  agreement, composed drive-type readback, and `0 N` monitored contact.
- Results:

  | Case | Drive / stiffness / damping / max force | Tracking error | Result |
  | --- | --- | ---: | --- |
  | acceleration runtime | acceleration / 10000 / 100 / 100 | `5.04065°` | fail |
  | force runtime | force / 10000 / 100 / 100 | `221160.35°` | unstable, rejected |
  | force stiffness 1048 | force / 1048 / 100 / 100 | `3.22899°` | fail |
  | force damping 53 | force / 1048 / 53 / 100 | `1.73936°` | fail |
  | force authored tuning | force / 1048 / 53 / 5.2 | `1.73936°` | fail |

- Established: force semantics plus official-scale stiffness and damping reduce
  the stable residual by `3.30129°` or `65.49%`, and lowering damping from
  `100` to `53` supplies `1.48963°` of that improvement. The best stable
  cases settle by position difference and pass the two-degree overshoot
  diagnostic, but remain outside the independent one-degree tracking gate.
- Maximum-force finding: PhysX readback changes from `100` to `5.2`, and the
  implicit PD estimate clip changes with it, but all 647 API targets, backend
  targets, Isaac targets, observed positions, raw/derived velocities, contact
  samples, and pose summaries remain identical. Lowering maximum force is not
  a tracking correction in this runtime.
- Decision correction: the machine summary labeled the high-gain force
  divergence as `position_velocity_instrumentation_incomplete`. Position-
  derived telemetry was present and recorded genuine unbounded dynamics.
  The local classifier now rejects unstable cases separately while continuing
  the later ladder; the reviewed decision is
  `drive_model_ladder_no_resolution`.
- Evidence:
  `artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json`. It binds
  the ignored 5 case JSON files, 5 logs, and raw matrix contract by exact byte
  size and SHA-256.
- Resource lifecycle: approved start `19:51:11 PDT`; matrix summary generated
  `19:54:41 PDT`; artifacts were retrieved before stop; standard
  `brev ls --json` reached explicit `STOPPED` at `20:05:30 PDT`. The
  14-minute-19-second window cost approximately `$0.379` at the quoted rate.
  No instance or disk was created, resized, or deleted.
- Validation: `187/187` repository tests, 23 focused drive/actuator/solver
  tests, targeted Ruff, JSON parsing, raw source byte/SHA bindings, Git LFS
  checks, remote-command previews, and `git diff --check` pass.
- Acceptance: **remote matrix complete / drive hypothesis materially improves
  tracking / no case passes / high-gain force rejected / pre-grasp and Viewer
  blocked**.

## DOFBOT Goal 3 camera gate

- Branch: `codex/dofbot-camera-contract`
- Official camera prim retained:
  `/World/envs/env_0/Dofbot/link4/Camera`; the baseline sets
  `CameraCfg.spawn=None` rather than creating a replacement sensor prim
- Input contract:
  `configs/dofbot/camera/goal3_onboard_rgb.json`
- Baseline output: RGB only, `640x480`, `torch.uint8`, `NHWC`, one camera
  instance; no depth, segmentation, CV model, policy, or checkpoint
- Timing contract: `update_period_s=0.1`, nominally 10 Hz in simulation time.
  This is an explicit simulator observation rate, not a claim about the
  unresolved physical camera model, exposure, transport latency, or measured
  hardware FPS.
- Deterministic static scene: a red cube, green cylinder, and blue cuboid in a
  world-fixed optical calibration plane `0.32 m` in front of the settled
  neutral camera, with `0.08 m` lateral spacing. The objects intentionally
  float above the robot; this validates camera geometry and dynamic binding,
  not a physically realistic tabletop scene.
- Planned remote inspection: authored focal length, horizontal and vertical
  aperture, aperture offsets, clipping range, focus distance, f-stop, derived
  field of view, world transform, ROS/OpenGL pose, and the effective intrinsic
  matrix
- Planned machine artifacts:
  `artifacts/dofbot/camera_contract.json` and
  `artifacts/dofbot/camera_rgb.png`; the PNG is covered by Git LFS
- Machine gates: original prim is a `UsdGeom.Camera`, sensor initializes,
  five distinct frames advance at 10 Hz simulation time, every tensor is
  non-empty/non-constant `1x480x640x3 uint8`, all three target centers project
  inside the image, the fixed `link4`-to-camera extrinsic round-trips within
  tolerance, the applied camera world pose matches that extrinsic, the camera
  pose changes with `link4`, and the PNG is saved with a SHA-256
- Local validation: `make test` passed all 97 tests; targeted Ruff, Python
  compilation, and `git diff --check` passed
- Remote static sensor facts on Isaac Sim `6.0.1`: the official prim is a
  `UsdGeom.Camera`; the sensor initializes; RGB is
  `torch.uint8[1,480,640,3]`; five frames advance at the exact configured
  `0.1 s` simulation cadence; the effective intrinsic matrix has
  `fx=fy=732.9993`, `cx=320`, and `cy=240`
- Remote binding result at `dbd09a7`: the official camera remained the sensor
  prim, while the explicit adapter followed live `link4` motion. Maximum
  dynamic translation was `0.065636 m` and maximum dynamic rotation was
  `57.4071 deg`; maximum applied position/orientation errors were
  `1.46e-8 m` and `1.12e-5 deg`.
- Rejected diagnostic: a 180-degree optical-frame flip made all target centers
  project inside the image but rendered five all-zero frames because the view
  pointed into the robot body. This is not a valid camera calibration and was
  removed from the current branch.
- Local remediation: the runner now calibrates one fixed
  `T_link4_camera` from the official neutral pose, computes
  `T_world_camera = T_world_link4 * T_link4_camera`, and calls the Isaac
  Camera world-pose API with the OpenGL convention before each rendered
  capture and Viewer step. The same path records calibration, applied-pose,
  and dynamic-motion errors in `camera_contract.json`. Isaac Lab 3.0's public
  `(x,y,z,w)` quaternion boundary is explicitly converted to the internal
  scalar-first transform representation; the adapter does not create a
  replacement camera or change the official optics.
- Current acceptance: **complete**. All machine checks passed, including
  non-constant RGB, exact 10 Hz simulation cadence, three in-frame target
  centers, fixed-extrinsic round-trip, applied-pose accuracy, and dynamic
  camera motion. At 2026-07-28 22:13 PDT the user confirmed the onboard view
  contained the red cube, green cylinder, and blue cuboid, then switched to
  Perspective and confirmed their expected world-relative placement above the
  moving DOFBOT.
- Machine evidence: `artifacts/dofbot/camera_contract.json`; captured RGB:
  `artifacts/dofbot/camera_rgb.png` through Git LFS.
- Compute lifecycle: stop requested immediately after visual acceptance;
  terminal `STOPPED` was verified with `brev ls --json` at 22:22 PDT.
  Instance and persistent disk were retained, with no deletion or resize.

## DOFBOT Goal 1 machine result

- Git source at remote sync: `f9a44ee`
- Environment: Isaac Launchable `3.0.0-beta2-post1`, Isaac Sim `6.0.1`,
  1x NVIDIA L4
- Official USD:
  `Robots/Yahboom/Dofbot/dofbot.usd`
- Resolved source:
  `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.0/Isaac/Robots/Yahboom/Dofbot/dofbot.usd`
- Robot/articulation root prim: `/World/envs/env_0/Dofbot`
- Articulation: initialized, fixed base, 11 joints, 12 bodies
- Onboard camera prim: `/World/envs/env_0/Dofbot/link4/Camera`
- Actuator groups: `front_joints`, `joint3_act`, `joint4_act`
- Machine acceptance: passed; every required contract check is `true`
- Machine-readable evidence: `artifacts/dofbot/asset_contract.json`
- Asset contract SHA-256:
  `1c0d806e4c61206355bddea738481496c45a98d789b5f64f269ec1d3f574a2b2`
- Viewer process: reached `Simulation App Startup Complete` and `app ready`
  with the Kit visualizer and WebRTC extension
- User visual result: passed at 2026-07-26 22:34 PDT; the user confirmed the
  stationary green DOFBOT in the secure Viewer
- Scope audit: no joint motion, RGB tensor capture, policy, checkpoint, PPO,
  SFT, or CV pipeline was run

## DOFBOT Goal 2 result

- Branch: `codex/dofbot-goal2-validation`
- Remote source: `c151777`
- Environment: Isaac Launchable `3.0.0-beta2-post1`, Isaac Sim `6.0.1`,
  1x NVIDIA L4
- Controlled joint set: `joint1`, `joint2`, `joint3`, `joint4`; these are the
  four actuator-backed arm joints with recorded finite limits
- Maximum command: `±5°` (`±0.0872665 rad`) around each recorded default
- Required target-to-limit margin: at least `10°`; the recorded contract leaves
  approximately `85°` from each extreme target to the corresponding limit
- Sequence: default hold, one six-second sinusoid and one-second settle per
  joint, eight-second multi-joint wave, three-second reset hold
- Headless duration: `41` seconds; Viewer mode adds a 30-second connection hold
  and repeats complete cycles so the user cannot miss the motion
- Fail-closed local checks: missing/renamed joints, sentinel limits, insufficient
  range, command above `5°`, unaccepted/nonofficial Goal 1 input, live-contract
  drift, non-finite samples, limit margin, single-joint isolation,
  inactive-joint drift, bidirectional excursion, and final reset error
- Machine thresholds: at least `±2.5°` observed excursion, at most `1°`
  inactive-joint error, at most `1°` active-joint overshoot, at least 90%
  command/observation sign agreement, at least `1°` per joint in the
  simultaneous wave, and at most `1°` final reset error
- Compatibility: one-robot articulation/physics targets used CPU because the
  installed Isaac runtime exited during the first step with CUDA targets; the
  L4 still rendered the secure Viewer
- Machine acceptance: passed; all 11 contract checks are true
- Sign agreement: `40/40` samples (`1.0`) for each of the four joints
- Observed single-joint deltas:
  - `joint1`: `[-5.00°, 5.00°]`
  - `joint2`: `[-5.34°, 5.40°]`
  - `joint3`: `[-5.56°, 5.87°]`
  - `joint4`: `[-5.07°, 5.33°]`
- Maximum inactive-joint error: below `1°`; maximum reset error:
  approximately `0.16°`
- Machine-readable evidence: `artifacts/dofbot/motion_contract.json`
- Motion contract SHA-256:
  `6107ea36dd81c848889c05a6413196d4e873f0cd44f407415bb82302c60d3cab`
- Viewer acceptance: six complete cycles reported `machine_passed=True`; the
  stop request interrupted cycle seven
- User visual result: passed at 2026-07-27 19:54 PDT; the user confirmed
  visible small-amplitude movement and rocking/wave behavior. The subtle
  appearance is expected from the intentional `±5°` safety limit.
- Local visual evidence: the supplied 8.875-second screen recording was
  reviewed but not committed
- Scope audit: no camera tensor, policy, checkpoint, PPO, SFT, CV pipeline,
  or real hardware command was used
- Compute lifecycle: stop requested immediately after the user visual gate;
  terminal `STOPPED` verified at 20:04:45 PDT. The instance and persistent disk
  were retained.
- Goal 2 status: complete; machine and visual gates passed

## DOFBOT simulator/hardware API bridge

- Public compatibility API: Yahboom's documented
  `Arm_serial_servo_write(id, angle, time)` and
  `Arm_serial_servo_read(id)`
- Normalized core: named `joint1` through `joint4` positions in radians plus
  `duration_ms`
- Simulator backend: the Goal 2 Isaac runner now calls the vendor-shaped API,
  which delegates through `DofbotArm` before setting articulation targets
- Hardware backend: translates the same command to Yahboom's documented
  `Arm_serial_servo_write(id, angle, time)` and reads with
  `Arm_serial_servo_read(id)`
- Documented candidate mapping: `joint1` through `joint4` map to servo IDs
  `1` through `4`; zero radians maps to the documented 90-degree centered pose
- Local dry-run: 411 trajectory samples at 10 Hz produced 1,644 single-servo
  calls; all mapped angles stayed in `[85°, 95°]`
- Safety boundary: physical direction and per-device offsets are not yet
  calibrated; the real backend refuses reads and writes while
  `hardware_verified` is false
- Runtime scope: local pure Python only; no GPU started and no real hardware
  command sent

## DOFBOT ActionChunk v1 configured-motion result

- Validation source: `main@ce3f8eb438cc6969b61fccfde4f6b648da3a2253`
- Input contract:
  `configs/dofbot/motions/safe_api_wave.json`
- Command schema: complete absolute angles for servo IDs `1` through `4`,
  expressed in integer degrees, plus per-pose movement and hold durations
- Observation rate: `10 Hz`; in the current local revision only pose boundaries
  dispatch `Arm_serial_servo_write(id, angle, time)`, once per controlled servo
- Original remote-tested profile: `[85°, 95°]`, at most `5°` between
  configured poses, 9 seconds, 90 complete-pose samples, and 360 calls
- Original machine result: all six checks passed; maximum checkpoint error
  `0.667°`, maximum observed excursion `5.430°`, and final neutral error
  `0.076°`
- Original visual result: failed. The user saw the repeated motion but judged
  it too subtle and closer to rocking than a clear bend.
- First visible-profile remote result (`83f24c6`): all six machine checks
  passed after reserving one degree for tracking overshoot. The 12.4-second
  sequence recorded 124 samples and made 496 official calls; maximum checkpoint
  error was `0.866°`, maximum observed excursion `15.175°`, and final neutral
  error `0.114°`. Contract SHA-256:
  `2af0a94931ebd8c580611584a91ff4252742953723fc813672a85fc5fe93346b`.
- First visible-profile visual result: failed. The user saw more range, but
  rejected the slow stair-step motion, residual shaking, and insufficiently
  decisive bend. At least cycles 1 through 13 each reported
  `machine_passed=True`; this is still not a visual pass.
- Accepted profile: every pose contains all four servos, stays within
  `[60°, 120°]`, changes no servo by more than `30°`, starts and ends at
  `[90°, 90°, 90°, 90°]`, and completes in 5.6 seconds. The base targets
  `±20°`; the other joints target `±28°`, leaving two configured degrees inside
  the envelope.
- Dispatch model: five poses produce only 20 official calls (one per
  servo per pose), while 56 independent 10 Hz observations remain available.
  The Isaac-only backend models `duration_ms` with a physics-rate smoothstep;
  the application layer no longer replays 100-millisecond waypoint calls.
- Local acceptance: 71 total Python tests, remote-command previews, targeted
  Ruff, shell syntax, and `git diff --check` passed
- Final machine evidence: `artifacts/dofbot/motion_config_contract.json`;
  SHA-256
  `8a9da487d8eae33be56398f17616a1ffa1204ac809f3c6f51d64d68b2f929ea5`
- Final machine result: all six checks true; 56 observations, 20 official API
  calls, maximum checkpoint error `1.243°`, maximum observed excursion
  `29.319°`, and final neutral error `0.141°`
- Viewer result: `Simulation App Startup Complete`; at least 15 complete
  cycles reported `machine_passed=True`, and cycle 16 started before stop
- User visual result: passed at 2026-07-28 19:25 PDT. The user confirmed two
  obvious, substantially larger main motions with much smoother transitions.
  Small motion between the main poses remains noted as neutral-return behavior
  plus possible actuator settling; future task-specific motion may use a larger
  validated workspace.
- Scope: no camera capture, policy, checkpoint, `Arm_Lib` import, or
  real-hardware command
- Current result: complete. The final pose-boundary revision passed both the
  machine and user Viewer gates; earlier failed profiles remain immutable
  historical evidence.
- Final compute lifecycle: paid window started at 19:18:06 PDT; stop requested
  at 19:25:41 PDT after evidence retrieval; terminal `STOPPED` verified at
  19:33 PDT. No instance or disk was deleted.
- 2026-07-28 compute lifecycle: existing instance started at 08:20:57 PDT;
  stop requested immediately after the failed visual gate; terminal `STOPPED`
  verified at 08:40 PDT. No instance or disk was deleted.
- Latest paid window: started at 22:47:04 PDT; stop requested at 23:14:41 PDT
  within the 30-minute cap. Brev remained in `STOPPING` after a second
  idempotent stop request and reached terminal `STOPPED` at 23:23:08 PDT.

### 2026-07-27 remote validation window

- Approved target: reuse only `isaac-launchable-f150a5` (`92xbacz46`), AWS
  `g6.4xlarge`, NVIDIA L4; no instance creation, resize, reset, or deletion
- Paid-window start: 18:06:06 PDT
- Remote source after sync: `main@e7307b8`
- Sync initially stopped on the untracked Goal 1
  `artifacts/dofbot/asset_contract.json`. Its SHA-256 matched the committed
  contract, and a byte-identical backup was retained at
  `/workspace/goal1-evidence/asset_contract.1c0d806e4c61206355bddea738481496c45a98d789b5f64f269ec1d3f574a2b2.json`
  before retrying the sync.
- Safety stop: at 19:05:57 PDT the elapsed paid window was already about
  59 minutes 51 seconds, beyond the approved 30-minute cap. The run was
  stopped immediately before `make dofbot-motion`.
- Machine result: not run; no `motion_contract.json` was produced
- Viewer result: not run; no visual claim was made
- Final resource state: `STOPPED`, verified with `brev ls --json`; instance and
  persistent disk retained
- Next gate: obtain a fresh quote and approval, then run the already-synced
  headless command before opening the Viewer

## Phase 1 result

- Observable remote-command wrapper: implemented and locally tested
- Dry-run previews: `make show-inspect-config`, `make show-train`,
  `make show-eval`
- Fresh training: complete, seed `42`, no resume checkpoint
- Configuration: 4096 environments, rollout 16, 2400 vector steps,
  9,830,400 transitions, learning rate `3e-4`
- Runtime: `68.43` seconds
- Checkpoint:
  `logs/skrl/cartpole/2026-07-26_16-09-30_ppo_torch/checkpoints/best_agent.pt`
- Fixed-seed result: mean reward `4.3805`, mean length `269.44`,
  `time_limit=22`, `out_of_bounds=3`
- Quantitative gate: passed
- User visual confirmation: passed; stable balancing with comparatively sparse,
  anticipatory cart corrections
- Compute price: `$1.59/hour` plus approximately `$0.04/hour` persistent
  storage

## Checkpoint learning curve

- Numbered checkpoints retained remotely: `agent_240.pt` through
  `agent_2400.pt`
- Fixed-seed sweep: complete; 25 episodes per checkpoint using the canonical
  five seeds
- Plot metrics: mean balance seconds and five-second time-limit fraction
- Random policy treatment: horizontal reference baseline, not a synthetic
  step-zero checkpoint
- Learning transition: from 0.935 seconds at 2.95M transitions to 4.491 seconds
  at 4.92M transitions
- Plateau: approximately 4.8 seconds and `24/25` time-limit episodes from
  6.88M transitions onward, with one temporary dip
- Actual sweep JSON:
  `artifacts/evaluations/phase1_learning_curve.json`
- Actual plot: `artifacts/plots/phase1_learning_curve.svg`
- Preserved training logs and configs: `artifacts/training/phase1/`
- GPU requirement now: none; the instance remains stopped

## Phase 2 result

- Study matrix: complete, 9 variants × 3 training seeds = 27 succeeded cells
- Failed/partial formal runs: none
- Factors: observation, cart-velocity reward, action effort scale, and training
  out-of-bounds threshold
- Evaluation: 25 fixed parallel environment IDs under deterministic seed 101;
  final common 30-second stress profile
- Final episode rows: 675; screening checkpoint evaluations: 90
- Baseline robust 30-second success: `100% ± 0%`
- Position-only robust success: `1.3% ± 2.3%`
- Four-frame history robust success: `66.7% ± 57.7%`; two seeds succeeded and
  one failed
- Reward variants: `100%` mean robust success at all three levels, with
  control-style differences
- Wide-boundary result: `65.3% ± 56.6%`, driven by one catastrophic seed
- Local evidence: 27 manifests, screening/final JSON, 7 CSV datasets, 5 SVG
  figures, and a paper-style report under `artifacts/phase2/`
- Local archive checksums:
  - data: `932d4b3dfae43e58ffc44f9c57f19e112f085744acd373a333660538aec73c59`
  - 27 checkpoints:
    `de37fa34962c20fa421917e9adb9e7a99af407bea91fb41a0d733c71949362b5`
- Validation: 18 unit tests, targeted Ruff, 27/27 manifest status, 9/9
  screening files, 9/9 final files, per-file episode counts, matching local and
  remote archive checksums, and browser-rendered SVG QA passed

## Phase 0 acceptance

- Hardware: AWS `g6.4xlarge`, 1x NVIDIA L4, 16 vCPU, 64 GiB RAM
- Canonical accepted task: `Isaac-Cartpole-v0` (manager-based)
- RL backend and algorithm: skrl PPO
- Policy provenance: official pretrained checkpoint, not locally trained
- Random evaluation: mean reward `-12.534867067337036`, mean length `188.44`,
  `out_of_bounds=25`
- Official checkpoint evaluation: mean reward `3.8110712456703184`, mean
  length `268.88`, `time_limit=22`, `out_of_bounds=3`
- Evaluation protocol: 25 episodes using seeds `101, 202, 303, 404, 505`
- User visual confirmation: complete; official PPO policy almost continuously
  balanced the pole
- Summary artifact:
  `artifacts/evaluations/phase0_acceptance_summary.json`

## Honest training status

- Local Direct skrl PPO, 150 iterations: did not beat random
- Resumed Direct skrl PPO, 600 more iterations: did not pass evaluation
- Direct RL-Games PPO, 150 epochs: did not establish fixed-seed convergence
- Official legacy Direct checkpoint: loaded with compatibility handling but did
  not produce the expected behavior
- Locally trained manager-based checkpoint: produced and passed the independent
  fixed-seed quantitative gates

## Persistent remote artifacts

- Official accepted checkpoint:
  `/workspace/isaaclab/.pretrained_checkpoints/skrl/Isaac-Cartpole-v0/Assets/Isaac/6.0/Isaac/IsaacLab/PretrainedCheckpoints/skrl/Isaac-Cartpole-v0/checkpoint.pt`
- Direct skrl logs/checkpoints: `/workspace/isaaclab/logs/skrl/cartpole_direct/`
- Direct RL-Games logs/checkpoints:
  `/workspace/isaaclab/logs/rl_games/cartpole_direct/`
- Phase 0 logs: `/workspace/phase0/artifacts/logs/`
- Phase 1 training log:
  `/workspace/phase1/artifacts/logs/train_cartpole_manager.log`

## DOFBOT bounded gravity feed-forward preparation

- Branch: `codex/dofbot-gravity-feed-forward`
- Scope: local implementation, deterministic plan generation, fail-closed
  tests, and remote-command preview only; no paid instance start, remote Isaac
  execution, Viewer, pre-grasp, contact, gripper, hardware, policy, or
  checkpoint
- Single-factor cases: stable force `1048/53/100` with feed-forward disabled,
  then the identical case with feed-forward enabled; both retain gravity,
  external-force iteration, safe poses, Yahboom API calls, and the `<=1°` gate
- Runtime safety: require gravity-compensation, external-DOF-actuation, and
  incoming-joint-force APIs before motion; clamp only joints 1-4 to `±5.2`;
  write zero to all other DOFs; record raw/applied effort and controlled-child
  incoming 6D forces every physics step
- Evidence: `artifacts/dofbot/gravity_feed_forward_plan.json`
- Local acceptance: **passed**; `200/200` repository tests, eight focused
  tests, targeted Ruff, Python compilation, shell syntax, JSON parsing,
  deterministic generation, Git LFS checks, and remote-command previews pass
- Resource state: `brev ls --json` reconfirmed
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4, as
  explicit `STOPPED` at 2026-07-30 21:53 PDT; no resource mutation occurred
- Current acceptance: **local passed / isolated machine calibration pending /
  pre-grasp and Viewer blocked**

## DOFBOT bounded gravity feed-forward machine result

- Branch: `codex/dofbot-gravity-ff-warp-compat`; repaired machine commit
  `1cf25a0`; merged preparation base `7539585`
- Initial result: fail closed before any pose command. The installed raw PhysX
  view used `FrontendWarp`, while the runner supplied Torch actuation data and
  indices; both cases raised `TypeError: issubclass() arg 1 must be a class`,
  no case artifact was written, and the matrix selected
  `incomplete_case_matrix`
- Failure record:
  `artifacts/dofbot/gravity_feed_forward_runtime_failure_2026-07-31.json`
- Minimal repair: use non-deprecated `root_view` and native Warp `float32`
  actuation data plus `int32` indices; no controller, bound, pose, or gate
  changed
- Repaired result: `[MATRIX_EXIT_CODE] 0`, matrix complete, decision
  `bounded_gravity_feed_forward_resolves_tracking`
- Baseline: `1.73936°` worst settled error, `1.74808°` overshoot, `0 N`
  monitored contact, tracking gate failed
- Treatment: `0.002391°` worst settled error, `0.03611°` overshoot, `0 N`
  contact, tracking gate passed
- Gravity telemetry: 645 finite treatment samples; maximum raw/applied effort
  `0.363701`; configured bound `5.2`; zero clipped samples; every uncontrolled
  DOF remained at zero external actuation
- Success record:
  `artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json`
- Local validation: `201/201` repository tests, nine focused tests, Ruff,
  Python compilation, deterministic plan generation, JSON, Git LFS, remote
  preview, and `git diff --check` passed
- Current acceptance: **isolated actuator tracking passed / pre-grasp runtime
  integration passed locally / pre-grasp machine gate and Viewer blocked**
- Integrated runtime: the pre-grasp runner now reuses the exact force
  `1048/53/100`, external-force iteration, native-Warp bounded gravity FF,
  API probe, effort isolation, live-drive readback, per-step telemetry, and
  failure-classification contract.
- Scope remains no gripper command, target motion, contact task, grasp, lift,
  place, hardware, policy, checkpoint, PPO, SFT, or VLA.
- Resource lifecycle: artifacts were retrieved before stop; standard
  `brev ls --json` reached explicit `STOPPED` at 2026-07-31 09:15:35 PDT.
  The instance and persistent disk were retained; no resource was created,
  resized, reset, or deleted.

## DOFBOT pre-grasp actuator-runtime integration

- Branch: `codex/dofbot-pregrasp-actuator-runtime`
- Scope: GPU-free integration and regression testing only; no Brev start,
  Isaac execution, Viewer, contact, gripper, hardware, policy, or checkpoint
- Evidence binding: the runner parses the accepted calibration config and the
  promoted machine result before Kit launch, requires the successful matrix
  decision and treatment metrics, cross-checks force `1048/53/100`, and records
  both source SHA-256 values
- Shared runtime: calibration and pre-grasp now import the same native-Warp
  `BoundedGravityFeedForward`; the probe writes zero before the first Yahboom
  pose, and every physics step preserves PD-write, bounded feed-forward,
  simulation-step, incoming-force-read order
- Machine fail-closed additions: read back every controlled USD drive, require
  the selected drive/gain/limit values, retain the `5.2` bound and zero
  uncontrolled-DOF effort, record all feed-forward samples, and classify failed
  checks as actuator, tracking, contact, API-accounting, reset, or task-space
- Local evidence: `artifacts/dofbot/pregrasp_command_space_contract.json`
  passes `27/27` checks and binds the runner plus shared-runtime SHA-256 values
- Validation: `205/205` repository tests, changed-file Ruff, Python
  compilation, shell syntax, remote-command previews, deterministic JSON,
  Git LFS, and `git diff --check` pass. Full-repository Ruff still reports the
  pre-existing unrelated long line in `tools/collect_environment_info.py:47`.
- Known remaining integration bugs: none from static and GPU-free tests.
  Installed Isaac task-scene behavior is still unverified and cannot be
  converted into a finite bug count before the headless machine gate.
- Current acceptance: **local runtime integration passed / headless pre-grasp
  machine pending / Viewer blocked**
- Resource state: `brev ls --json` re-verified the retained `g6.4xlarge` L4
  instance as explicit `STOPPED` at 11:21 PDT; no remote resource was started,
  created, resized, stopped, or deleted in this integration step.

## DOFBOT integrated pre-grasp headless result and settle repair

- Paid scope: one approved headless window on retained instance
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4. Live
  compute quote was `$1.58784/hour`; the existing disk remained approximately
  `$0.04/hour`. No Viewer, contact, gripper, target motion, grasp, hardware,
  policy, or checkpoint ran.
- Initial merged commit: `main@56fddc5`. The first probe failed before pose
  motion because it equated official USD `maxForce=5.199999809` with Isaac's
  runtime implicit-actuator effort limit `100`.
- Layer-correct repair: commit `7ce2276` separately verifies composed USD
  drive type/stiffness/damping and the live articulation effort-limit buffer.
  All four drives read `force/1048/53/5.199999809`; all four runtime limits read
  `100`. Both independent gates passed on the repaired run.
- Evidence-preservation repair: commit `fc48a2c` prevents the top-level runtime
  handler from replacing a complete expected machine-failure artifact. The
  retrieved full payload is 2,237,400 bytes, SHA-256
  `b970b2e90c90274c86e334a392c15f58fe4de1bd497f410887e38c090230f57b`.
- Machine outcome: failed only
  `grasp_origin_reached_pregrasp_position` and
  `final_api_joint_tracking_within_tolerance`. Position improved
  `0.255729 -> 0.0318076 m` against a `0.025 m` gate. The exact final API target
  `[90,66,66,66] deg` produced observed
  `[90.0083,68.5085,70.1658,67.2060] deg`, maximum tracking error
  `4.16578 deg` against `1 deg`.
- Passed evidence: approach `7.88737 deg`, closing `0.339104 deg`, contact
  `0 N`, neutral reset `0.002216 deg`, 248/248 API calls, all live actuator and
  gravity-runtime checks, static target, collision clearances, and 900 finite
  gravity samples with maximum effort `0.330320` and zero clipping.
- Next root cause: once the candidate command stopped at step 8, the runner
  reissued the same four servo calls every `0.2 s` through step 60 because the
  measured pose had not passed. Every reissue restarted smoothstep from the
  loaded position. The accepted calibration instead issued the candidate once,
  held it, and reached `0.001261 deg` error after `2.65 s`.
- Local repair: after the exact stopped candidate command, retain the existing
  target and advance physics without another API write. Continue all safety
  checks and the unchanged timeout/gates; count only actual API calls.
- Promoted result:
  `artifacts/dofbot/pregrasp_live_actuator_gate_result_2026-07-31.json`.
- Validation: 205/205 repository tests, 45 focused tests, changed-file Ruff,
  Python compilation, deterministic 27/27 preparation regeneration, remote
  previews, Git LFS, JSON, and `git diff --check` pass.
- Resource lifecycle: evidence was retrieved before stop. The ordinary list
  temporarily remained at `STOPPING`; a repeat stop reported that the backend
  was already stopped, and `brev ls --all --json` then confirmed explicit
  `STOPPED` at 11:56:36 PDT. The existing instance and disk were retained.
- Current acceptance: **actuator runtime passed remotely / first pre-grasp
  classified / candidate settle repair passed locally / repaired headless
  gate pending / Viewer blocked**.

## DOFBOT no-reissue headless rerun and local audit

- Remote commit: merged `main@4b4fc8a`; branch for the free follow-up:
  `codex/dofbot-pregrasp-machine-rerun-audit`
- The candidate controller issued 40/40 expected API calls. It completed the
  `[90,66,66,66]` trajectory at step 8, then steps 9-60 performed 52 physics
  settle observations without another API write.
- No-reissue was insufficient: final observed angles were
  `[89.999642,68.493213,70.177019,67.221305]°`; maximum tracking error was
  `4.177019° > 1°` and final position error was `0.0318089 m > 0.025 m`.
- All actuator, gravity, safe-envelope, collision, contact, static-target,
  API-accounting, and neutral-reset checks passed. Contact remained `0 N`;
  feed-forward peaked at `0.330318` with zero clipping at `5.2`.
- Raw evidence: 2,231,658 bytes, SHA-256
  `4674c83d58f187363720741a71b933a205f99c87951191eeb4ca44ce02cd0c3f`;
  promoted evidence:
  `artifacts/dofbot/pregrasp_no_reissue_machine_result_2026-07-31.json`.
- Exit audit: Python raised `PregraspMachineAcceptanceError`, but
  `isaaclab.sh`, the sentinel, and outer Make all returned zero. The local
  follow-up removes the prior output and verifies fresh artifact commit,
  `machine_passed=true`, and empty failed checks before emitting a zero
  sentinel.
- Missing discriminator: the failed artifact did not record the backend
  interpolated target or Isaac `joint_pos_target`. The local follow-up records
  and gates those two buffers plus computed/applied torque, separating command
  propagation failure from a post-write actuator residual on the next run.
- Local validation: the real failed artifact makes the new semantic verifier
  return nonzero; focused verifier/runner tests pass 14/14, all repository
  Python tests pass 210/210, and changed-file Ruff, Python compilation, shell
  syntax, remote preview, deterministic 27/27 contract regeneration, JSON,
  Git LFS, and `git diff --check` pass.
- Resource lifecycle: artifact retrieval completed before stop;
  `brev ls --all --json` confirmed explicit `STOPPED` at 21:23 PDT. No
  instance or disk was created, resized, reset, or deleted.
- Current acceptance: **no-reissue behavior proven / machine failed and
  classified / local discriminator prepared / Viewer blocked**.

## DOFBOT failure ledger and anti-loop gate

- Branch: `codex/dofbot-failure-ledger`, based on merged PR #41 at
  `origin/main@75201a0`.
- Scope: local evidence consolidation, operating rules, and regression tests
  only. No Brev start, Isaac runtime, Viewer, contact, gripper, target motion,
  hardware, policy, or checkpoint command ran.
- Canonical index: `experiments/02_dofbot/FAILURE_LEDGER.md` backfills 28
  chronological cases: 12 resolved defects, 8 falsified hypotheses/fixes, 5
  partial findings, 2 operational failures, and 1 open discriminator.
- Historical preservation: later evidence adds a new ID instead of rewriting
  an old conclusion. `DF-026` records API reissue as a real defect;
  `DF-028` records the later machine proof that no-reissue was insufficient.
- Future gate: `AGENTS.md`, the stage README, experiment hierarchy, lessons,
  decisions, and artifact index all require a ledger update in the same pull
  request. Another paid run must cite one unresolved ID, name a new
  discriminator, state exact evidence fields, and explain why it does not
  repeat a falsified case.
- Automated guard: `tests/test_dofbot_failure_ledger.py` requires sequential
  IDs, fixed verdict vocabulary, existing referenced artifacts, coverage of
  every tracked `*failure*.json`, the current `DF-028` target/torque
  discriminator, and repository-policy links.
- Validation: focused ledger tests pass `5/5`;
  `UV_CACHE_DIR=/tmp/robotics-isaac-uv-cache make test` passes Git LFS checks,
  remote sentinel/preview checks, and all `215/215` Python tests.
- Resource state: `brev ls --all --json` returned the retained
  `isaac-launchable-f150a5` (`92xbacz46`) L4 as explicit `STOPPED` at 21:50
  PDT. No resource was started, created, resized, reset, stopped, or deleted.
- Acceptance: **historical ledger backfill passed / anti-loop policy and test
  passed / current scientific issue remains `DF-028` open / Viewer blocked**.

## DF-028 target/torque rerun blocked at Brev startup

- Branch: `codex/dofbot-pregrasp-target-telemetry-rerun`, based on merged
  failure-ledger PR #42 at `main@8b59eaa`
- Approved scope: one unchanged headless `make dofbot-pregrasp` discriminator
  on the retained instance; no Viewer, contact, gripper, target motion,
  hardware, policy, or checkpoint
- Preflight: instance identity and live quote matched the approved
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, L4 at
  `$1.58784/hour`; local tests and remote preview had already passed
- Operational result: a foreground start at 09:55:03 PDT and one detached
  retry never moved the instance from `STOPPED`. The shell remained
  `NOT READY`; a host SSH probe timed out; repeated JSON status polls remained
  stopped through 10:03:24; `brev refresh` completed and the final 10:04:53
  poll was still `STOPPED`
- Delayed-start safety audit: a second `brev refresh` plus JSON status poll at
  10:08:11 PDT again returned explicit `STOPPED`; the detached request did not
  start compute later
- Scientific boundary: repository sync, Isaac, `make dofbot-pregrasp`, Viewer,
  and target/torque artifact generation never started. `DF-028` therefore
  remains open; no controller, actuator, task-space, or machine-gate claim is
  changed
- Evidence:
  `artifacts/dofbot/pregrasp_startup_operational_2026-08-01.json`; the new
  ledger entry is `DF-029` with verdict `OPERATIONAL`
- Resource safety: no running compute was observed, no instance/disk was
  created, resized, reset, or deleted, and the retained instance is explicitly
  `STOPPED`. The existing persistent disk remains approximately `$0.04/hour`.

## DF-028 target/torque discriminator completed; PhysX effort is next

- Branch: `codex/dofbot-df028-capacity-retry`, based on merged PR #43 at
  `main@d6f5597`.
- The fresh identity/price gate matched the retained
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, L4 at
  `$1.58784/hour`. One detached start at 21:29:34 UTC reached shell `READY` and
  exposed `NVIDIA L4, 23034 MiB`; the earlier zone-capacity failure was
  transient and no machine, zone, disk, or controller factor changed.
- The exact `[90,66,66,66]°` API target reached the backend with zero error and
  live `joint_pos_target` within `0.000000668°`. Command propagation therefore
  passed, while the unchanged articulation again settled at
  `[89.999642,68.493213,70.177019,67.221305]°`, leaving `4.177019°` joint and
  `0.0318089 m` position error.
- `computed_torque` and `applied_torque` were equal at every observation and
  peaked at `76.4262`, but Isaac Lab defines those ImplicitActuator fields as
  approximate PD torque because PhysX does not expose that torque directly.
  They do not prove physical effort application. `DF-030` records this partial
  localization; the next unchanged discriminator is PhysX
  `get_dof_projected_joint_forces`.
- A separate wrapper defect became visible: `isaaclab.sh` masked the Python
  machine exception, then the verifier called absent `python3` and emitted
  sentinel `127`. `DF-031` records it. The local wrapper now uses the installed
  `./_isaac_sim/python.sh`, and the runner is prepared to capture projected
  PhysX joint effort on the next run.
- Promoted evidence:
  `artifacts/dofbot/pregrasp_target_torque_discriminator_2026-08-01.json`; the
  ignored raw artifact is bound by byte count `2,269,037` and SHA-256
  `d6cf7552bbf50cfeb2bc007bd9eb8ff2f863abf65a93660369e39f0544e5d6ef`.
- Resource lifecycle: artifact retrieval completed before stop;
  `brev ls --all --json` confirmed explicit `STOPPED` at 14:44 PDT. No instance
  or disk was created, resized, reset, or deleted; no Viewer ran.
- Current acceptance: **target propagation proven / physical-effort boundary
  still open / pre-grasp machine failed / Viewer blocked**.

## Exact next action

Keep the Brev instance stopped. `DF-039` now proves that the merged DF-035
single-boundary trajectory does not resolve the loaded residual. The next work
is GPU-free: compare the successful isolated calibration and failed integrated
task contexts, identify the smallest remaining factor or missing observable,
and add one new unresolved ledger discriminator. Only after that local gate,
a fresh quote, and explicit approval may another headless run occur.
`make dofbot-pregrasp-view` remains blocked until every machine gate passes.
Contact, closing, grasping, lifting, and placing remain unauthorized.

## DF-030/DF-032 projected-force local contract hardening

- Branch: `codex/dofbot-physx-effort-audit`, based on merged PR #44 at
  `main@9a64968`.
- Historical boundary: all 31 prior ledger entries were reread. No controller,
  drive, trajectory, scene, safety gate, or acceptance threshold changed.
- Semantic correction: official PhysX defines projected DOF force as the
  active projection of incoming joint force along the motion direction. It is
  a measured joint-force balance, not an isolated implicit-drive torque
  sensor; `DF-032` records this partial boundary.
- Instrumentation: the runner now requires finite, DOF-aligned projected force
  and computed/applied PD estimates at every observation and summarizes each
  controlled joint's final, signed extrema, maximum magnitude, and
  projected-minus-estimate differences.
- Wrapper: missing/non-executable `./_isaac_sim/python.sh` now fails closed
  with sentinel `126` before semantic verification.
- Validation: deterministic 27/27 contract regeneration, 222/222 repository
  tests, targeted Ruff, Python compilation, shell syntax, remote preview, Git
  LFS, and `git diff --check` pass.
- Scope: GPU-free implementation, tests, and remote-command preview only. The
  retained instance remains `STOPPED`; installed Isaac telemetry and semantic
  sentinel behavior are still remote pending, and Viewer remains blocked.

## DF-032 machine result and DF-035 trajectory correction

- Paid run: merged `main@d4da9c0` ran once on the retained
  `isaac-launchable-f150a5` (`92xbacz46`), AWS `g6.4xlarge`, NVIDIA L4, after
  the live quote matched `$1.58784/hour`. The exact command was
  `BREV_INSTANCE_NAME=isaac-launchable-f150a5 make dofbot-pregrasp`; no Viewer
  ran.
- Machine result: only position and final tracking failed. Final position was
  `0.0318089 m > 0.025 m`; `[90,66,66,66]` settled at
  `[89.999642,68.493213,70.177019,67.221305]`, leaving
  `4.177019 degrees > 1 degree`. Approach, closing, all safety/collision,
  zero-contact, static-target, actuator, gravity, target-buffer, API, projected
  force, and reset gates passed.
- Projected force: 61/61 observations were finite and aligned. Per-joint
  maxima were `[0.001136,0.505431,0.342836,0.165914]`, versus approximate PD
  estimate maxima `[0.045059,45.798676,76.426231,22.747814]`. This fulfills
  the telemetry contract but cannot isolate implicit drive torque (`DF-034`).
- Wrapper: installed Isaac Python rejected the failed artifact with sentinel
  1 and outer Make failed, resolving `DF-031` through `DF-033`.
- New local defect: each old 4-degree/200-ms cubic smoothstep actually peaks at
  `30 degrees/s` and `600 degrees/s2`, not the boundary-reported `20/60`.
  The runner now uses the accepted calibration's single 2000-ms pose boundary,
  analytically bounded at `18 degrees/s` and `36 degrees/s2`, records those
  internal derivatives, and expects 12 rather than 40 API calls (`DF-035`).
- Evidence:
  `artifacts/dofbot/pregrasp_projected_force_discriminator_2026-08-01.json`;
  raw artifact 2,283,842 bytes, SHA-256
  `d884465662b2f664619b72b547f101f1409d65a1a4dcd7f785c0203ec47a231c`.
- Resource lifecycle: stop was requested after retrieval; explicit `STOPPED`
  was verified at 16:29:26 PDT. No instance/disk was created, deleted, resized,
  or reset. Viewer remains blocked pending a later machine pass.

## CPU-only GitHub quality gate

- Entry point: `make ci-cpu`, shared by local development and GitHub Actions.
- Trigger: every pull request, every push to `main`, and manual dispatch on a
  standard Ubuntu CPU runner with read-only repository permissions.
- Coverage: pinned Ruff, the complete local test suite, Python compilation,
  Phase 2 config validation, all deterministic DOFBOT previews and offline
  analyses available from the checkout, JSON parsing, and byte-for-byte
  regeneration of the accepted pre-grasp command-space contract. Analyses
  backed by deliberately ignored raw Isaac samples are fully replayed when
  those samples exist; a clean runner instead audits each promoted result's
  config, upstream-result, SHA-256, and byte-count bindings.
- Isolation: generated outputs and caches stay in a temporary directory, so CI
  neither rewrites tracked evidence nor needs Brev credentials.
- Boundary: this gate does not claim Isaac USD loading, PhysX articulation,
  live residual/force behavior, GPU rendering, or Viewer acceptance. Those
  remain remote machine and human-visual gates.

## DF-038 GPU-admission and machine-contract hardening

- The previous final verifier accepted a minimal JSON containing only a
  matching commit, `machine_passed=true`, and an empty failed-check list. It
  did not require the 37 runtime safety/telemetry checks or prove that the
  machine used the CPU-reviewed DF-035 input bundle.
- A new pure-Python GPU preflight verifies seven source-file hashes, all 27
  local checks, the exact single 2000-ms command boundary and derivative
  envelope, actuator settings, collision mutations, and prohibited scope.
- `make dofbot-pregrasp` now executes that verifier with Isaac's installed
  Python before launching Isaac. A mismatch emits the existing nonzero
  sentinel without running the simulator.
- The post-run verifier now requires the exact 37-check set, strict booleans,
  complete and aligned observations/telemetry, 12 API calls, numeric gate
  coherence, source hashes, the exact motion contract, policy-free scope, and
  visual acceptance still pending.
- GitHub CPU coverage also includes mutation tests for every preflight/runtime
  check, a dense cubic-trajectory derivative grid, all shell syntax, and a
  post-generation clean tracked-worktree check. This raises software-admission
  confidence but does not alter or claim the unresolved DF-035 PhysX result.

## DF-035 single-boundary machine result and DF-040 verifier repair

- Merged `main@2e7f7aa` passed the local and remote 27-check GPU admission gate
  on the retained `isaac-launchable-f150a5` L4 at `$1.58784/hour`.
- The single `[90,66,66,66] / 2000 ms` Yahboom candidate boundary executed
  exactly once; total API accounting was 12/12 and recorded motion peaks were
  `18.000943 degrees/s / 36.001886 degrees/s2`, inside the unchanged `20/60`
  envelope.
- Machine outcome: **failed only 2/37 checks**. Final joints were
  `[90.008511,68.467499,70.196145,67.246695] degrees`, leaving
  `4.196145 degrees` tracking and `0.0318115 m` position error. The prior
  values were `4.177019 degrees / 0.0318089 m`, so `DF-039` falsifies the
  trajectory-only hypothesis as a sufficient repair.
- All target-buffer, actuator, gravity, force telemetry, API, collision,
  zero-contact, static-target, approach/closing, and reset gates passed. The
  verifier produced sentinel 1 and blocked Viewer as intended.
- Raw evidence: retained ignored 2,283,434-byte machine artifact, SHA-256
  `62edc78fa2491ac07670222cac093f92e0e0c90e5974743bd627c68d2fdddbd3`;
  tracked promotion:
  `artifacts/dofbot/pregrasp_single_boundary_discriminator_2026-08-01.json`.
- `DF-040` fixes a latent semantic-verifier false reject exposed by the real
  `0.0023-degree` neutral-start noise. The verifier now binds start angles to
  observation zero, recomputes deltas/derivatives, enforces the one-degree
  neutral gate and unchanged `20/60` envelope, and still requires the exact
  goal, duration, API count, and all 37 machine checks.
- Viewer did not start. Artifact retrieval preceded stop; final Brev state is
  explicit `STOPPED`, with the instance and disk retained.
- Exact next action: no paid run is authorized. Compare the successful isolated
  calibration and failed integrated task contexts offline, record the
  differing factors, and select one new falsifiable discriminator before a new
  quote or Viewer attempt.
