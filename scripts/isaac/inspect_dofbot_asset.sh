#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
output_path="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
max_steps="${DOFBOT_MAX_STEPS:-120}"

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_output_path '%q' "$output_path"
printf -v quoted_max_steps '%q' "$max_steps"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output_path)\"
./isaaclab.sh -p $quoted_project_dir/tools/inspect_dofbot_asset.py \
  --output $quoted_output_path \
  --max-steps $quoted_max_steps \
  --headless
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
