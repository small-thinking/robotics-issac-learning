#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
motion_config="${DOFBOT_MOTION_CONFIG:-${MOTION:-configs/dofbot/motions/safe_api_wave.json}}"
output="${DOFBOT_MOTION_CONFIG_CONTRACT:-$project_dir/artifacts/dofbot/motion_config_contract.json}"

if [[ "$motion_config" != /* ]]; then
  motion_config="$project_dir/$motion_config"
fi

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_motion_config '%q' "$motion_config"
printf -v quoted_output '%q' "$output"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output)\"
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
./isaaclab.sh -p $quoted_project_dir/tools/run_dofbot_motion_config.py \
  --asset-contract $quoted_asset_contract \
  --motion-config $quoted_motion_config \
  --output $quoted_output \
  --cycles 1 \
  --viewer-connection-hold-seconds 0 \
  --git-commit \"\$git_commit\" \
  --device cpu \
  --headless
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
