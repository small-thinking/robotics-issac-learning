#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
motion_contract="${DOFBOT_MOTION_CONTRACT:-$project_dir/artifacts/dofbot/motion_contract.json}"
cycles="${DOFBOT_MOTION_CYCLES:-1}"
pre_motion_hold="${DOFBOT_PRE_MOTION_HOLD_SECONDS:-2}"
sample_hz="${DOFBOT_MOTION_SAMPLE_HZ:-10}"

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_motion_contract '%q' "$motion_contract"
printf -v quoted_cycles '%q' "$cycles"
printf -v quoted_pre_motion_hold '%q' "$pre_motion_hold"
printf -v quoted_sample_hz '%q' "$sample_hz"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_motion_contract)\"
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
./isaaclab.sh -p $quoted_project_dir/tools/move_dofbot_joints.py \
  --asset-contract $quoted_asset_contract \
  --output $quoted_motion_contract \
  --cycles $quoted_cycles \
  --pre-motion-hold-seconds $quoted_pre_motion_hold \
  --sample-hz $quoted_sample_hz \
  --git-commit \"\$git_commit\" \
  --device cpu \
  --headless
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
