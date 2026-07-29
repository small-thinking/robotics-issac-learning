#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
reaching_config="${DOFBOT_REACHING_CONFIG:-${REACHING:-configs/dofbot/reaching/goal4_fixed_tabletop.json}}"
output="${DOFBOT_REACHING_CONTRACT:-$project_dir/artifacts/dofbot/reaching_contract.json}"

if [[ "$reaching_config" != /* ]]; then
  reaching_config="$project_dir/$reaching_config"
fi

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_reaching_config '%q' "$reaching_config"
printf -v quoted_output '%q' "$output"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output)\"
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
./isaaclab.sh -p $quoted_project_dir/tools/run_dofbot_reaching.py \
  --asset-contract $quoted_asset_contract \
  --reaching-config $quoted_reaching_config \
  --output $quoted_output \
  --cycles 1 \
  --viewer-connection-hold-seconds 0 \
  --git-commit \"\$git_commit\" \
  --device cpu \
  --headless
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
