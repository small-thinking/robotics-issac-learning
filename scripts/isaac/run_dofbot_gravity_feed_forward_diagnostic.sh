#!/usr/bin/env bash
set -euo pipefail

export DOFBOT_ACTUATOR_MATRIX_PROFILE=gravity_feed_forward
exec "$(dirname "$0")/run_dofbot_actuator_calibration.sh"
