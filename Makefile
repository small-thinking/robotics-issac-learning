SHELL := /bin/bash

.PHONY: doctor search provision sync remote-setup smoke train play eval learning-curve status stop \
	dofbot-inspect dofbot-view dofbot-motion dofbot-motion-view \
	dofbot-api-dry-run dofbot-motion-config-dry-run \
	dofbot-motion-config dofbot-motion-config-view \
	dofbot-camera dofbot-camera-view \
	dofbot-reach-dry-run dofbot-pregrasp-dry-run dofbot-reach dofbot-reach-view \
	show-dofbot-inspect show-dofbot-view show-dofbot-motion show-dofbot-motion-view \
	show-dofbot-motion-config show-dofbot-motion-config-view \
	show-dofbot-camera show-dofbot-camera-view \
	show-dofbot-reach show-dofbot-reach-view \
	inspect-config show-sync show-remote-setup show-inspect-config show-smoke \
	show-train show-play show-eval show-learning-curve study-validate study-matrix \
	show-variant show-manifest show-study-run test

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
	@./tests/test_remote_command_preview.sh
	@UV_CACHE_DIR="$${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}" \
	 uv run --python 3.12 python -m unittest discover -s tests -p "test_*.py"
