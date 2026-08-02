SHELL := /bin/bash

.PHONY: doctor search provision sync remote-setup smoke train play eval learning-curve status stop \
	dofbot-inspect dofbot-view dofbot-motion dofbot-motion-view \
	dofbot-api-dry-run dofbot-motion-config-dry-run \
	dofbot-motion-config dofbot-motion-config-view \
	dofbot-camera dofbot-camera-view \
	dofbot-reach-dry-run dofbot-pregrasp-dry-run dofbot-reach dofbot-reach-view \
	dofbot-pregrasp-pose-dry-run dofbot-pregrasp-reachability \
	dofbot-gpu-preflight \
	dofbot-pregrasp-taskspace dofbot-actuator-calibration-dry-run \
	dofbot-actuator-calibration dofbot-solver-drive-dry-run \
	dofbot-solver-drive dofbot-drive-model-dry-run dofbot-drive-model \
	dofbot-actuator-velocity-reanalysis dofbot-residual-force-audit \
	dofbot-actuator-velocity-evidence-audit \
	dofbot-residual-force-evidence-audit \
	dofbot-gravity-feed-forward-dry-run dofbot-gravity-feed-forward \
	dofbot-pregrasp dofbot-pregrasp-view \
	show-dofbot-inspect show-dofbot-view show-dofbot-motion show-dofbot-motion-view \
	show-dofbot-motion-config show-dofbot-motion-config-view \
	show-dofbot-camera show-dofbot-camera-view \
	show-dofbot-reach show-dofbot-reach-view \
	show-dofbot-pregrasp show-dofbot-pregrasp-view \
	show-dofbot-actuator-calibration \
	show-dofbot-solver-drive show-dofbot-drive-model \
	show-dofbot-gravity-feed-forward \
	inspect-config show-sync show-remote-setup show-inspect-config show-smoke \
	show-train show-play show-eval show-learning-curve study-validate study-matrix \
	show-variant show-manifest show-study-run test ci-cpu

doctor:
	@./scripts/local/doctor.sh

search:
	@./scripts/brev/search.sh

provision:
	@./scripts/brev/provision.sh

sync:
	@./scripts/brev/sync.sh

remote-setup:
	@./scripts/brev/remote_setup.sh

inspect-config:
	@./scripts/isaac/inspect_cartpole_config.sh

smoke:
	@./scripts/isaac/random_cartpole.sh

train:
	@./scripts/isaac/train_cartpole.sh

play:
	@./scripts/isaac/play_cartpole.sh

eval:
	@./scripts/isaac/eval_cartpole.sh

learning-curve:
	@./scripts/isaac/eval_learning_curve.sh

dofbot-inspect:
	@./scripts/isaac/inspect_dofbot_asset.sh

dofbot-view:
	@./scripts/isaac/view_dofbot_asset.sh

dofbot-motion:
	@./scripts/isaac/run_dofbot_motion.sh

dofbot-motion-view:
	@./scripts/isaac/view_dofbot_motion.sh

dofbot-api-dry-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/preview_dofbot_yahboom_api.py \
	 --output "$${DOFBOT_API_PREVIEW_OUTPUT:-/tmp/dofbot-yahboom-api-preview.json}"

dofbot-motion-config-dry-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/preview_dofbot_motion_config.py \
	 --motion-config "$${MOTION:-configs/dofbot/motions/safe_api_wave.json}" \
	 --output "$${DOFBOT_MOTION_CONFIG_PREVIEW_OUTPUT:-/tmp/dofbot-motion-config-preview.json}"

dofbot-motion-config:
	@./scripts/isaac/run_dofbot_motion_config.sh

dofbot-motion-config-view:
	@./scripts/isaac/view_dofbot_motion_config.sh

dofbot-camera:
	@./scripts/isaac/capture_dofbot_camera.sh

dofbot-camera-view:
	@./scripts/isaac/view_dofbot_camera.sh

dofbot-reach-dry-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/preview_dofbot_reaching.py \
	 --reaching-config "$${REACHING:-configs/dofbot/reaching/goal4_fixed_tabletop.json}" \
	 --output "$${DOFBOT_REACHING_PREVIEW_OUTPUT:-/tmp/dofbot-reaching-preview.json}"

dofbot-pregrasp-dry-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/calibrate_dofbot_pregrasp_scene.py \
	 --baseline-config "$${BASELINE_REACHING:-configs/dofbot/reaching/goal4_fixed_tabletop.json}" \
	 --candidate-config "$${REACHING:-configs/dofbot/reaching/goal4_pregrasp_scene_candidate.json}" \
	 --isaac-artifact "$${REACHING_ARTIFACT:-artifacts/dofbot/reaching_viewer_contract.json}" \
	 --output-json "$${DOFBOT_PREGRASP_JSON:-/tmp/dofbot-pregrasp-scene-calibration.json}" \
	 --output-svg "$${DOFBOT_PREGRASP_SVG:-/tmp/dofbot-pregrasp-scene-calibration.svg}"

dofbot-pregrasp-pose-dry-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/preview_dofbot_pregrasp_pose.py \
	 --pose-config "$${PREGRASP_POSE:-configs/dofbot/pregrasp/goal5_angled_pregrasp.json}" \
	 --scene-config "$${REACHING:-configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json}" \
	 --asset-contract "$${DOFBOT_ASSET_CONTRACT:-artifacts/dofbot/asset_contract.json}" \
	 --actuator-config "$${DOFBOT_PREGRASP_ACTUATOR_CONFIG:-configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json}" \
	 --actuator-result "$${DOFBOT_PREGRASP_ACTUATOR_RESULT:-artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json}" \
	 --output "$${DOFBOT_PREGRASP_POSE_OUTPUT:-/tmp/dofbot-pregrasp-pose-contract.json}"

dofbot-gpu-preflight:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/verify_dofbot_pregrasp_gpu_preflight.py \
	 --contract "$${DOFBOT_PREGRASP_PREFLIGHT_CONTRACT:-artifacts/dofbot/pregrasp_command_space_contract.json}" \
	 --project-dir .

dofbot-pregrasp-reachability:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/search_dofbot_pregrasp_reachability.py \
	 --reachability-config "$${PREGRASP_REACHABILITY:-configs/dofbot/pregrasp/goal5_planar_reachability.json}" \
	 --pose-config "$${PREGRASP_POSE:-configs/dofbot/pregrasp/goal5_pose_aware_pregrasp.json}" \
	 --failure-summary "$${PREGRASP_FAILURE:-artifacts/dofbot/pregrasp_machine_failure_2026-07-29.json}" \
	 --output "$${DOFBOT_PREGRASP_REACHABILITY_OUTPUT:-/tmp/dofbot-pregrasp-reachability.json}"

dofbot-pregrasp-taskspace:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/design_dofbot_pregrasp_taskspace.py \
	 --output "$${DOFBOT_PREGRASP_TASKSPACE_OUTPUT:-artifacts/dofbot/pregrasp_taskspace_candidate.json}"

dofbot-actuator-calibration-dry-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/preview_dofbot_actuator_calibration.py \
	 --config "$${ACTUATOR_CALIBRATION:-configs/dofbot/calibration/goal5_actuator_diagnostic.json}" \
	 --tracking-failure "$${PREGRASP_TRACKING_FAILURE:-artifacts/dofbot/pregrasp_joint_tracking_failure_2026-07-29.json}" \
	 --output "$${DOFBOT_ACTUATOR_CALIBRATION_PLAN:-artifacts/dofbot/actuator_calibration_plan.json}"

dofbot-actuator-calibration:
	@./scripts/isaac/run_dofbot_actuator_calibration.sh

dofbot-solver-drive-dry-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/preview_dofbot_solver_drive_diagnostic.py \
	 --config "$${SOLVER_DRIVE_DIAGNOSTIC:-configs/dofbot/calibration/goal5_solver_drive_diagnostic.json}" \
	 --remote-result "$${ACTUATOR_CALIBRATION_RESULT:-artifacts/dofbot/actuator_calibration_result_2026-07-30.json}" \
	 --output "$${DOFBOT_SOLVER_DRIVE_PLAN:-artifacts/dofbot/solver_drive_diagnostic_plan.json}"

dofbot-solver-drive:
	@./scripts/isaac/run_dofbot_solver_drive_diagnostic.sh

dofbot-drive-model-dry-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/preview_dofbot_drive_model_diagnostic.py \
	 --config "$${DRIVE_MODEL_DIAGNOSTIC:-configs/dofbot/calibration/goal5_drive_model_diagnostic.json}" \
	 --asset-audit "$${DOFBOT_ASSET_DRIVE_AUDIT:-artifacts/dofbot/asset_drive_audit_2026-07-30.json}" \
	 --solver-result "$${SOLVER_DRIVE_RESULT:-artifacts/dofbot/solver_drive_diagnostic_result_2026-07-30.json}" \
	 --output "$${DOFBOT_DRIVE_MODEL_PLAN:-artifacts/dofbot/drive_model_diagnostic_plan.json}"

dofbot-drive-model:
	@./scripts/isaac/run_dofbot_drive_model_diagnostic.sh

dofbot-actuator-velocity-reanalysis:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/reanalyze_dofbot_velocity_signals.py \
	 --config "$${SOLVER_DRIVE_DIAGNOSTIC:-configs/dofbot/calibration/goal5_solver_drive_diagnostic.json}" \
	 --remote-result "$${ACTUATOR_CALIBRATION_RESULT:-artifacts/dofbot/actuator_calibration_result_2026-07-30.json}" \
	 --input-dir "$${ACTUATOR_CALIBRATION_CASES:-artifacts/dofbot/actuator_calibration_cases}" \
	 --output "$${DOFBOT_VELOCITY_REANALYSIS:-artifacts/dofbot/actuator_velocity_reanalysis_2026-07-30.json}"

dofbot-actuator-velocity-evidence-audit:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/audit_dofbot_velocity_reanalysis_evidence.py \
	 --config "$${SOLVER_DRIVE_DIAGNOSTIC:-configs/dofbot/calibration/goal5_solver_drive_diagnostic.json}" \
	 --remote-result "$${ACTUATOR_CALIBRATION_RESULT:-artifacts/dofbot/actuator_calibration_result_2026-07-30.json}" \
	 --reanalysis "$${DOFBOT_VELOCITY_EVIDENCE_INPUT:-artifacts/dofbot/actuator_velocity_reanalysis_2026-07-30.json}" \
	 --output "$${DOFBOT_VELOCITY_EVIDENCE_AUDIT:-/tmp/dofbot-velocity-evidence-audit.json}"

dofbot-residual-force-audit:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/audit_dofbot_residual_force.py \
	 --output "$${DOFBOT_RESIDUAL_FORCE_AUDIT:-artifacts/dofbot/residual_force_audit_2026-07-30.json}"

dofbot-residual-force-evidence-audit:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/audit_dofbot_residual_force_evidence.py \
	 --drive-result "$${DRIVE_MODEL_RESULT:-artifacts/dofbot/drive_model_diagnostic_result_2026-07-30.json}" \
	 --actuator-result "$${ACTUATOR_CALIBRATION_RESULT:-artifacts/dofbot/actuator_calibration_result_2026-07-30.json}" \
	 --asset-audit "$${DOFBOT_ASSET_DRIVE_AUDIT:-artifacts/dofbot/asset_drive_audit_2026-07-30.json}" \
	 --residual-audit "$${DOFBOT_RESIDUAL_FORCE_EVIDENCE_INPUT:-artifacts/dofbot/residual_force_audit_2026-07-30.json}" \
	 --output "$${DOFBOT_RESIDUAL_FORCE_EVIDENCE_AUDIT:-/tmp/dofbot-residual-force-evidence-audit.json}"

dofbot-gravity-feed-forward-dry-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/preview_dofbot_gravity_feed_forward.py \
	 --config "$${GRAVITY_FEED_FORWARD_DIAGNOSTIC:-configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json}" \
	 --residual-force-audit "$${DOFBOT_RESIDUAL_FORCE_AUDIT:-artifacts/dofbot/residual_force_audit_2026-07-30.json}" \
	 --output "$${DOFBOT_GRAVITY_FEED_FORWARD_PLAN:-artifacts/dofbot/gravity_feed_forward_plan.json}"

dofbot-gravity-feed-forward:
	@./scripts/isaac/run_dofbot_gravity_feed_forward_diagnostic.sh

dofbot-pregrasp:
	@./scripts/isaac/run_dofbot_pregrasp.sh

dofbot-pregrasp-view:
	@./scripts/isaac/view_dofbot_pregrasp.sh

dofbot-reach:
	@./scripts/isaac/run_dofbot_reaching.sh

dofbot-reach-view:
	@./scripts/isaac/view_dofbot_reaching.sh

status:
	@./scripts/brev/status.sh

stop:
	@./scripts/brev/stop.sh

show-sync:
	@REMOTE_DRY_RUN=1 ./scripts/brev/sync.sh

show-remote-setup:
	@REMOTE_DRY_RUN=1 ./scripts/brev/remote_setup.sh

show-inspect-config:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/inspect_cartpole_config.sh

show-smoke:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/random_cartpole.sh

show-train:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/train_cartpole.sh

show-play:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/play_cartpole.sh

show-eval:
	@REMOTE_DRY_RUN=1 \
	 ISAAC_CHECKPOINT="$${ISAAC_CHECKPOINT:-/absolute/remote/checkpoint.pt}" \
	 ./scripts/isaac/eval_cartpole.sh

show-learning-curve:
	@REMOTE_DRY_RUN=1 \
	 ISAAC_CHECKPOINT_DIR="$${ISAAC_CHECKPOINT_DIR:-/absolute/remote/checkpoints}" \
	 ./scripts/isaac/eval_learning_curve.sh

show-dofbot-inspect:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/inspect_dofbot_asset.sh

show-dofbot-view:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/view_dofbot_asset.sh

show-dofbot-motion:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/run_dofbot_motion.sh

show-dofbot-motion-view:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/view_dofbot_motion.sh

show-dofbot-motion-config:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/run_dofbot_motion_config.sh

show-dofbot-motion-config-view:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/view_dofbot_motion_config.sh

show-dofbot-camera:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/capture_dofbot_camera.sh

show-dofbot-camera-view:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/view_dofbot_camera.sh

show-dofbot-reach:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/run_dofbot_reaching.sh

show-dofbot-reach-view:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/view_dofbot_reaching.sh

show-dofbot-pregrasp:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/run_dofbot_pregrasp.sh

show-dofbot-pregrasp-view:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/view_dofbot_pregrasp.sh

show-dofbot-actuator-calibration:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/run_dofbot_actuator_calibration.sh

show-dofbot-solver-drive:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/run_dofbot_solver_drive_diagnostic.sh

show-dofbot-drive-model:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/run_dofbot_drive_model_diagnostic.sh

show-dofbot-gravity-feed-forward:
	@REMOTE_DRY_RUN=1 ./scripts/isaac/run_dofbot_gravity_feed_forward_diagnostic.sh

study-validate:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/cartpole_variants.py validate

study-matrix:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/cartpole_variants.py matrix

show-variant:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/cartpole_variants.py show \
	 "$${VARIANT:-B0}" --scope "$${SCOPE:-train}" $${PROFILE:+--profile "$${PROFILE}"}

show-manifest:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/cartpole_variants.py manifest \
	 "$${VARIANT:-B0}" --training-seed "$${TRAINING_SEED:-42}"

show-study-run:
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python tools/run_phase2_study.py \
	 --study-dir /tmp/phase2-study-preview \
	 --phase "$${PHASE:-train}" \
	 --variants "$${VARIANTS:-O_POS}" \
	 --training-seeds "$${TRAINING_SEEDS:-42}" \
	 --dry-run

test:
	@bash ./tests/test_git_lfs_attributes.sh
	@bash ./tests/test_remote_exit_sentinel.sh
	@./tests/test_remote_command_preview.sh
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python -m unittest discover -s tests -p "test_*.py"

ci-cpu:
	@./scripts/local/run_cpu_ci.sh
