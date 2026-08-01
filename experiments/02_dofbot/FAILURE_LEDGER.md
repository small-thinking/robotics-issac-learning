# DOFBOT failure and falsification ledger

This is the canonical index of DOFBOT failures, rejected fixes, superseded
diagnoses, and operational mistakes. Detailed chronological narratives remain
append-only in `docs/EXPERIMENTS.md`; generated machine evidence remains under
`artifacts/dofbot/`. This ledger connects those records so a later iteration
cannot silently repeat an already rejected experiment.

## Required update contract

Read this ledger before changing a DOFBOT controller, simulator setting,
measurement, scene, or remote wrapper. Update it in the same pull request when
any of the following occurs:

- a local, machine, or visual gate fails;
- a proposed root cause or correction is falsified or only partly supported;
- new evidence supersedes an earlier explanation;
- a runtime, telemetry, artifact, transport, cost-window, or safety failure is
  found or repaired.

Each new row must identify the tested claim, evidence boundary, verdict, and a
specific do-not-repeat rule or next discriminator. Never rewrite an old verdict
to make it look correct in hindsight. Add a later row and name the superseded
entry. A failed paid run must be recorded here before another paid run is
authorized.

Verdicts have fixed meanings:

- `RESOLVED`: the defect was reproduced and its correction passed the relevant
  later gate.
- `FALSIFIED`: machine or bounded analytical evidence rejected the hypothesis
  or proposed correction.
- `PARTIAL`: the effect is real, but it does not explain or fix the full
  failure.
- `OPEN`: the available artifact cannot yet distinguish the remaining causes.
- `OPERATIONAL`: infrastructure or process failed; the scientific gate either
  did not run or must be interpreted separately.

## Pre-run anti-loop gate

Before another paid DOFBOT command, the experiment must name one unresolved
ledger ID and state:

1. the new observation that distinguishes the remaining hypotheses;
2. the single factor being changed, or why a multi-factor change is required;
3. the exact artifact and pass/fail fields that will be retrieved;
4. why the run does not repeat a `FALSIFIED` case;
5. the stop deadline and the machine gate that blocks Viewer launch.

The target-buffer part of **DF-028** is now resolved by **DF-030**: the exact
API target reached both the backend and live `joint_pos_target` buffer, while
the loaded residual remained unchanged. Isaac Lab documents the recorded
implicit-actuator torque fields as approximate PD estimates, not measured
PhysX effort. **DF-032** refines the current scientific item after checking the
official tensor API semantics: `get_dof_projected_joint_forces` measures the
active projection of incoming joint force, not isolated implicit-drive torque.
The next run must collect that value for every observation beside the gravity
feed-forward and approximate PD buffers without changing the pose, gains,
effort limit, solver settings, feed-forward, or acceptance thresholds.
**DF-031** is the separate wrapper prerequisite: its Isaac-Python correction
has passed local tests but must prove that a failed semantic contract produces
a nonzero remote sentinel. Viewer remains blocked.

## Consolidated ledger

| ID | Date | Area | Tested claim or observed failure | Verdict | Durable evidence | Do-not-repeat rule or next discriminator |
| --- | --- | --- | --- | --- | --- | --- |
| DF-001 | 2026-07-27 | Paid-window control | Goal 2 sync consumed about 59m51s, exceeding the 30-minute cap before motion ran. | OPERATIONAL | `docs/EXPERIMENTS.md` section "DOFBOT Goal 2 remote window stopped before motion" | Start the paid timer at instance start, preserve conflicting evidence by hash, and stop before the cap even when the scientific command never ran. |
| DF-002 | 2026-07-27 | Isaac compatibility | A one-robot CUDA articulation/physics target exited on the first step; CPU targets then passed while the L4 still rendered Viewer. | RESOLVED | `artifacts/dofbot/motion_contract.json` | Keep this installed-runtime device boundary explicit; do not infer that a local CUDA-shaped mock proves Isaac stepping. |
| DF-003 | 2026-07-27 | ActionChunk visual quality | The original plus/minus 5-degree profile passed all machine checks but failed the user's amplitude gate. | FALSIFIED | `artifacts/dofbot/motion_config_small_amplitude_2026-07-27.json` | Machine tracking does not imply useful visible motion; keep machine and human gates separate. |
| DF-004 | 2026-07-28 | ActionChunk envelope | The first exact plus/minus 15-degree profile exceeded the observation envelope on joint 3 at 16.293 degrees. | RESOLVED | `docs/EXPERIMENTS.md` section "visible profile passed machine gate but failed motion-quality gate" | Reduce the command while retaining the gate; never loosen a safety envelope to make the same run pass. |
| DF-005 | 2026-07-28 | ActionChunk semantics | A larger profile passed machine checks but looked slow, stair-stepped, and shaky because API calls were replayed at the 10 Hz observation cadence. | RESOLVED | `artifacts/dofbot/motion_config_contract.json` | Dispatch once per servo per pose and model duration inside the backend; observation frequency is not command frequency. |
| DF-006 | 2026-07-28 | Camera binding | The official camera sensor stayed at its neutral pose while PhysX moved `link4`; waiting another sensor period did not repair it. | RESOLVED | `artifacts/dofbot/camera_contract.json` | Preserve the official prim/optics and explicitly apply the fixed `T_link4_camera` transform from live link state before capture and Viewer steps. |
| DF-007 | 2026-07-28 | Camera orientation | A 180-degree optical flip put projected targets in bounds but produced five all-zero frames because the camera looked into the robot. | FALSIFIED | `docs/EXPERIMENTS.md` section "onboard RGB remote gate found dynamic-pose blocker" | Geometric projection alone is not camera acceptance; require non-constant RGB and a physically interpretable view. |
| DF-008 | 2026-07-28 | Workspace frame | Goal 4 passed machine metrics but failed the human front/back gate because camera optical forward was reused as physical workspace front. | RESOLVED | `artifacts/dofbot/reaching_viewer_contract.json` | Optical, robot-base, and task frames are separate contracts; never infer a physical work side from a diagnostic camera fixture. |
| DF-009 | 2026-07-29 | First pre-grasp pose | The lower/farther world-down candidate safely improved position but failed at 0.07212 m and 103.21 degrees approach error. | FALSIFIED | `artifacts/dofbot/pregrasp_machine_failure_2026-07-29.json` | Do not rerun this candidate unchanged; machine failure is not yet global infeasibility. |
| DF-010 | 2026-07-29 | Reachability | Exhaustive calibrated searches proved the world-down pose infeasible inside both physical and API-margin envelopes. | FALSIFIED | `artifacts/dofbot/pregrasp_reachability.json` | Do not spend GPU on this target again unless the scene, approach, or separately calibrated safety envelope changes. |
| DF-011 | 2026-07-29 | IK branch | Cartesian DLS drifted from the sole safe angled posture and missed the position/approach gates despite passing safety checks. | RESOLVED | `artifacts/dofbot/pregrasp_angled_machine_failure_2026-07-29.json` | A task-space target derived from a joint branch must preserve that branch explicitly; tighter margins are invalid when they leave zero candidates. |
| DF-012 | 2026-07-29 | Paid-window control | The angled pre-grasp window ran roughly 75 minutes before the overrun was detected. | OPERATIONAL | `docs/EXPERIMENTS.md` section "Angled candidate failed narrowly; direct joint-candidate correction prepared" | Maintain a monotonic deadline outside the remote command and stop GPU before doing local diagnosis or PR work. |
| DF-013 | 2026-07-29 | Controller state | Direct-candidate deltas used observed joints while braking/quantization used the previous API command, so the endpoint was not the configured candidate. | RESOLVED | `artifacts/dofbot/pregrasp_joint_candidate_machine_failure_2026-07-29.json` | Keep command-space trajectory state and observation-space safety feedback separate; test the complete stopped sequence, not one float step. |
| DF-014 | 2026-07-29 | Loaded tracking | The corrected API path reached exact `[90,66,66,66]` but the loaded articulation settled 4.641 degrees away. | PARTIAL | `artifacts/dofbot/pregrasp_joint_tracking_failure_2026-07-29.json` | Treat this as actuator/load evidence, not another task-space or API-endpoint bug; isolate the actuator before task retry. |
| DF-015 | 2026-07-30 | Artifact serialization | Optional PhysX arrays were not JSON serializable after poses ran, while the Isaac launcher still returned zero. | RESOLVED | `artifacts/dofbot/actuator_calibration_result_2026-07-30.json` | Normalize optional tensors/arrays, persist per-case logs, and require non-empty artifacts independently of launcher status. |
| DF-016 | 2026-07-30 | Effort limit | Gravity-on effort 100 and 250 produced identical target, position, and velocity sequences with the same 4.97619-degree error. | FALSIFIED | `artifacts/dofbot/actuator_calibration_result_2026-07-30.json` | Do not repeat effort-limit-only increases as a tracking fix in this runtime. |
| DF-017 | 2026-07-30 | Velocity telemetry | Nearly stationary joint positions coexisted with raw `joint_vel` near 16.344 degrees/s under TGS. | FALSIFIED | `artifacts/dofbot/actuator_velocity_reanalysis_2026-07-30.json` | Raw TGS velocity cannot be the sole settling signal; retain it as compatibility telemetry beside position-derived velocity. |
| DF-018 | 2026-07-30 | Solver settings | External-force iteration repaired raw/derived velocity mismatch, but two velocity iterations and damping 50 left 4.883-5.041-degree tracking error. | PARTIAL | `artifacts/dofbot/solver_drive_diagnostic_result_2026-07-30.json` | Retain the telemetry repair, but do not present it, extra velocity iterations, or damping 50 as a tracking correction. |
| DF-019 | 2026-07-30 | Force drive stability | Force drive with the previous 10000/100 gains diverged to 221160.35 degrees. | FALSIFIED | `artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json` | Never rerun the rejected high-gain force configuration except as an explicitly labeled regression fixture. |
| DF-020 | 2026-07-30 | Force drive tuning | Official-scale 1048/53 force tuning improved error to 1.73936 degrees but still failed the unchanged one-degree gate. | PARTIAL | `artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json` | Preserve the useful direction without calling it a passing controller or opening the task Viewer. |
| DF-021 | 2026-07-30 | Drive maximum force | Changing runtime maximum force from 100 to 5.2 changed readback/clips but left all 647 selected physical samples identical. | FALSIFIED | `artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json` | Do not select 5.2 versus 100 as a physical correction without a new force-limit discriminator. |
| DF-022 | 2026-07-30 | Residual-force semantics | Gravity-off success rejected a static joint-frame/sign error as the primary cause; impulse-limit semantics explain max-force invariance at high confidence but were not directly read back. | PARTIAL | `artifacts/dofbot/residual_force_audit_2026-07-30.json` | Preserve inference boundaries: do not claim direct runtime-flag proof, and do not revisit joint-frame correction without contradictory machine evidence. |
| DF-023 | 2026-07-31 | Tensor frontend | The raw Warp articulation setter rejected Torch force data before any pose command. | RESOLVED | `artifacts/dofbot/gravity_feed_forward_runtime_failure_2026-07-31.json`, `artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json` | Probe installed raw APIs before motion and use the native frontend type for data and indices; a local type-shaped mock is insufficient. |
| DF-024 | 2026-07-31 | Actuator layers | Integrated pre-grasp incorrectly equated USD drive `maxForce=5.2` with Isaac implicit-actuator `effort_limit_sim=100`. | RESOLVED | `artifacts/dofbot/pregrasp_live_actuator_gate_result_2026-07-31.json` | Gate composed USD drive properties and runtime articulation effort buffers independently. |
| DF-025 | 2026-07-31 | Artifact preservation | An expected machine-gate exception overwrote the already-written full failure artifact with a short runtime error. | RESOLVED | `artifacts/dofbot/pregrasp_live_actuator_gate_result_2026-07-31.json` | Preserve complete acceptance-failure payloads; exception routing must not replace stronger evidence. |
| DF-026 | 2026-07-31 | API reissue | Reissuing the stopped candidate every 0.2 s restarted smoothstep and created real lag; the repair reduced API calls from 248 to 40. | PARTIAL | `artifacts/dofbot/pregrasp_live_actuator_gate_result_2026-07-31.json`, `artifacts/dofbot/pregrasp_no_reissue_machine_result_2026-07-31.json` | Keep no-reissue behavior, but DF-028 supersedes it as a sufficient explanation of the loaded residual. |
| DF-027 | 2026-07-31 | Exit propagation | Python raised an acceptance error while `isaaclab.sh`, the sentinel, and outer Make still returned zero; sentinel-only hardening was insufficient. | RESOLVED | `artifacts/dofbot/pregrasp_no_reissue_machine_result_2026-07-31.json` | Remove stale output first and semantically verify a fresh commit-bound passing artifact; process status alone cannot authorize success. |
| DF-028 | 2026-07-31 | Current pre-grasp residual | With no reissue, `[90,66,66,66]` still settled at 4.177019-degree joint error and 0.0318089 m position error; the artifact lacked backend/live target and torque discriminators. | OPEN | `artifacts/dofbot/pregrasp_no_reissue_machine_result_2026-07-31.json` | Next run records backend target, live `joint_pos_target`, `computed_torque`, and `applied_torque` without changing pose/gains/limits/gates; Viewer remains blocked. |
| DF-029 | 2026-08-01 | Brev startup | The approved target/torque run never reached compute: normal and detached start requests plus `brev refresh` left the retained instance `STOPPED`, shell `NOT READY`, and SSH timed out before sync or Isaac. | OPERATIONAL | `artifacts/dofbot/pregrasp_startup_operational_2026-08-01.json` | Do not interpret this as controller evidence or rerun Isaac/change parameters. After fresh quote and approval, require one detached start to reach `RUNNING` and shell `READY`, refresh stale CLI state, then sync and run only the unchanged DF-028 discriminator. |
| DF-030 | 2026-08-01 | Actuation boundary | The unchanged DF-028 run propagated `[90,66,66,66]` exactly to the backend and within 0.000000668 degrees to live `joint_pos_target`, yet retained 4.177019 degrees joint error and 0.0318089 m position error. The equal `computed_torque` and `applied_torque` buffers are only ImplicitActuator PD estimates, not measured PhysX effort. | PARTIAL | `artifacts/dofbot/pregrasp_target_torque_discriminator_2026-08-01.json` | Do not revisit API write loss or claim that the approximate torque buffers prove physical application. Keep every control factor fixed and record PhysX `get_dof_projected_joint_forces` as the next discriminator before changing the drive or controller. |
| DF-031 | 2026-08-01 | Remote semantic verifier | `isaaclab.sh` again masked the Python acceptance exception, then the semantic verifier called absent container command `python3`, overwriting the scientific result with sentinel 127 even though a fresh failed artifact existed. | OPERATIONAL | `artifacts/dofbot/pregrasp_target_torque_discriminator_2026-08-01.json` | Use the installed `./_isaac_sim/python.sh` for the verifier and retain artifact-first interpretation. Local preview/tests pass; a future remote run must still prove the failing semantic contract emits a reliable nonzero sentinel. |
| DF-032 | 2026-08-01 | Projected-force semantics | Official PhysX tensor semantics define `get_dof_projected_joint_forces` as the active component obtained by projecting each link incoming joint force onto its DOF motion direction. This is measured joint-force balance, but it is not an isolated implicit-drive torque sensor. The previous final-sample-only gate also did not summarize whether projected force and PD estimates were finite and aligned for every observation. | PARTIAL | `docs/EXPERIMENTS.md` section "DF-030 projected-force local contract hardening" | Keep the unchanged DF-030 run, but do not interpret projected force alone as proof of drive application. Require every observation to contain finite DOF-aligned projected force plus computed/applied PD estimates; retrieve per-joint final, extrema, and difference summaries beside gravity feed-forward before choosing the next controller change. |

## Current evidence boundary

The ledger does not claim that every historical raw log is committed. Large
runtime payloads and logs may remain ignored, but promoted artifacts bind them
by byte count and SHA-256. Human screenshots and recordings remain supporting
visual evidence unless repository policy explicitly promotes them. A ledger
row is an index and conclusion, not a replacement for the underlying machine
artifact or the append-only experiment narrative.
