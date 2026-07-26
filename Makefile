SHELL := /bin/bash

.PHONY: doctor search provision sync remote-setup smoke train play eval status stop

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
