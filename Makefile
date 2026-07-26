SHELL := /bin/bash

.PHONY: doctor search provision status stop

doctor:
	@./scripts/local/doctor.sh

search:
	@./scripts/brev/search.sh

provision:
	@./scripts/brev/provision.sh

status:
	@./scripts/brev/status.sh

stop:
	@./scripts/brev/stop.sh
