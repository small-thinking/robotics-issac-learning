#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
reaching_config="${DOFBOT_REACHING_CONFIG:-${REACHING:-configs/dofbot/reaching/goal4_fixed_tabletop.json}}"
output="${DOFBOT_REACHING_VIEW_CONTRACT:-$project_dir/artifacts/dofbot/reaching_viewer_contract.json}"
log_path="${DOFBOT_REACHING_VIEWER_LOG:-$project_dir/artifacts/dofbot/reaching_viewer.log}"
connection_hold="${DOFBOT_REACHING_VIEW_HOLD_SECONDS:-20}"

if [[ "$reaching_config" != /* ]]; then
  reaching_config="$project_dir/$reaching_config"
fi

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_reaching_config '%q' "$reaching_config"
printf -v quoted_output '%q' "$output"
printf -v quoted_log_path '%q' "$log_path"
printf -v quoted_connection_hold '%q' "$connection_hold"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output)\" \"\$(dirname $quoted_log_path)\"
stale_pids=\"\$(ps -eo pid=,comm=,args= | awk '\$2 ~ /^python/ && \$0 ~ /run_dofbot_reaching.py/ {print \$1}')\"
if [[ -n \"\$stale_pids\" ]]; then
  kill \$stale_pids 2>/dev/null || true
fi
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
nohup ./isaaclab.sh -p $quoted_project_dir/tools/run_dofbot_reaching.py \
  --asset-contract $quoted_asset_contract \
  --reaching-config $quoted_reaching_config \
  --output $quoted_output \
  --cycles -1 \
  --viewer-connection-hold-seconds $quoted_connection_hold \
  --git-commit \"\$git_commit\" \
  --device cpu \
  --livestream 2 \
  --viz kit \
  >$quoted_log_path 2>&1 </dev/null &
printf 'dofbot_reaching_viewer_pid=%s\\n' \"\$!\"
printf 'log=%s\\n' $quoted_log_path
printf 'fixed-tabletop reaching repeats until the process or instance is stopped\\n'
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
