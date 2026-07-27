#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
motion_contract="${DOFBOT_MOTION_VIEW_CONTRACT:-$project_dir/artifacts/dofbot/motion_viewer_contract.json}"
log_path="${DOFBOT_MOTION_VIEWER_LOG:-$project_dir/artifacts/dofbot/motion_viewer.log}"
pre_motion_hold="${DOFBOT_VIEW_PRE_MOTION_HOLD_SECONDS:-30}"
sample_hz="${DOFBOT_MOTION_SAMPLE_HZ:-10}"

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_motion_contract '%q' "$motion_contract"
printf -v quoted_log_path '%q' "$log_path"
printf -v quoted_pre_motion_hold '%q' "$pre_motion_hold"
printf -v quoted_sample_hz '%q' "$sample_hz"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_motion_contract)\" \"\$(dirname $quoted_log_path)\"
stale_pids=\"\$(ps -eo pid=,comm=,args= | awk '\$2 ~ /^python/ && \$0 ~ /move_dofbot_joints.py/ {print \$1}')\"
if [[ -n \"\$stale_pids\" ]]; then
  kill \$stale_pids 2>/dev/null || true
fi
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
nohup ./isaaclab.sh -p $quoted_project_dir/tools/move_dofbot_joints.py \
  --asset-contract $quoted_asset_contract \
  --output $quoted_motion_contract \
  --cycles -1 \
  --pre-motion-hold-seconds $quoted_pre_motion_hold \
  --sample-hz $quoted_sample_hz \
  --git-commit \"\$git_commit\" \
  --livestream 2 \
  --viz kit \
  >$quoted_log_path 2>&1 </dev/null &
printf 'dofbot_motion_viewer_pid=%s\\n' \"\$!\"
printf 'log=%s\\n' $quoted_log_path
printf 'motion repeats until the process or instance is stopped\\n'
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
