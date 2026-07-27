SHELL := /bin/bash

.PHONY: doctor search provision sync remote-setup smoke train play eval learning-curve status stop \
	dofbot-inspect dofbot-view show-dofbot-inspect show-dofbot-view \
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
