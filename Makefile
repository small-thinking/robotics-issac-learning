SHELL := /bin/bash

.PHONY: doctor search provision sync remote-setup smoke train play eval status stop \
	inspect-config show-sync show-remote-setup show-inspect-config show-smoke \
	show-train show-play show-eval test

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

test:
	@./tests/test_remote_command_preview.sh
