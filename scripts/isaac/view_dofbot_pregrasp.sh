#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
scene_config="${DOFBOT_PREGRASP_SCENE_CONFIG:-${REACHING:-configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json}}"
pose_config="${DOFBOT_PREGRASP_POSE_CONFIG:-${PREGRASP_POSE:-configs/dofbot/pregrasp/goal5_angled_pregrasp.json}}"
actuator_config="${DOFBOT_PREGRASP_ACTUATOR_CONFIG:-${GRAVITY_FEED_FORWARD_DIAGNOSTIC:-configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json}}"
actuator_result="${DOFBOT_PREGRASP_ACTUATOR_RESULT:-artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json}"
output="${DOFBOT_PREGRASP_VIEW_CONTRACT:-$project_dir/artifacts/dofbot/pregrasp_viewer_contract.json}"
log_path="${DOFBOT_PREGRASP_VIEWER_LOG:-$project_dir/artifacts/dofbot/pregrasp_viewer.log}"
connection_hold="${DOFBOT_PREGRASP_VIEW_HOLD_SECONDS:-20}"

if [[ "$scene_config" != /* ]]; then
  scene_config="$project_dir/$scene_config"
fi
if [[ "$pose_config" != /* ]]; then
  pose_config="$project_dir/$pose_config"
fi
if [[ "$actuator_config" != /* ]]; then
  actuator_config="$project_dir/$actuator_config"
fi
if [[ "$actuator_result" != /* ]]; then
  actuator_result="$project_dir/$actuator_result"
fi

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_scene_config '%q' "$scene_config"
printf -v quoted_pose_config '%q' "$pose_config"
printf -v quoted_actuator_config '%q' "$actuator_config"
printf -v quoted_actuator_result '%q' "$actuator_result"
printf -v quoted_output '%q' "$output"
printf -v quoted_log_path '%q' "$log_path"
printf -v quoted_connection_hold '%q' "$connection_hold"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output)\" \"\$(dirname $quoted_log_path)\"
stale_pids=\"\$(ps -eo pid=,comm=,args= | awk '\$2 ~ /^python/ && \$0 ~ /run_dofbot_pregrasp.py/ {print \$1}')\"
if [[ -n \"\$stale_pids\" ]]; then
  kill \$stale_pids 2>/dev/null || true
fi
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
nohup ./isaaclab.sh -p $quoted_project_dir/tools/run_dofbot_pregrasp.py \
  --asset-contract $quoted_asset_contract \
  --scene-config $quoted_scene_config \
  --pose-config $quoted_pose_config \
  --actuator-config $quoted_actuator_config \
  --actuator-result $quoted_actuator_result \
  --output $quoted_output \
  --cycles -1 \
  --viewer-connection-hold-seconds $quoted_connection_hold \
  --git-commit \"\$git_commit\" \
  --device cpu \
  --livestream 2 \
  --viz kit \
  >$quoted_log_path 2>&1 </dev/null &
printf 'dofbot_pregrasp_viewer_pid=%s\\n' \"\$!\"
printf 'log=%s\\n' $quoted_log_path
printf 'pose-aware pre-grasp repeats until the process or instance is stopped\\n'
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
