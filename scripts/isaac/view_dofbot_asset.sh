#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
output_path="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
log_path="${DOFBOT_VIEWER_LOG:-$project_dir/artifacts/dofbot/viewer.log}"

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_output_path '%q' "$output_path"
printf -v quoted_log_path '%q' "$log_path"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output_path)\" \"\$(dirname $quoted_log_path)\"
stale_pids=\"\$(ps -eo pid=,comm=,args= | awk '\$2 ~ /^python/ && \$0 ~ /inspect_dofbot_asset.py/ {print \$1}')\"
if [[ -n \"\$stale_pids\" ]]; then
  kill \$stale_pids 2>/dev/null || true
fi
nohup ./isaaclab.sh -p $quoted_project_dir/tools/inspect_dofbot_asset.py \
  --output $quoted_output_path \
  --max-steps -1 \
  --livestream 2 \
  --viz kit \
  >$quoted_log_path 2>&1 </dev/null &
printf 'dofbot_viewer_pid=%s\\n' \"\$!\"
printf 'log=%s\\n' $quoted_log_path
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
