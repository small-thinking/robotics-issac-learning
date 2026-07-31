#!/usr/bin/env bash
set -euo pipefail

export DOFBOT_ACTUATOR_MATRIX_PROFILE=solver_drive
exec "$(dirname "$0")/run_dofbot_actuator_calibration.sh"
