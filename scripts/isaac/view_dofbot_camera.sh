#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
camera_config="${DOFBOT_CAMERA_CONFIG:-$project_dir/configs/dofbot/camera/goal3_onboard_rgb.json}"
motion_config="${DOFBOT_MOTION_CONFIG:-$project_dir/configs/dofbot/motions/safe_api_wave.json}"
output="${DOFBOT_CAMERA_VIEW_CONTRACT:-$project_dir/artifacts/dofbot/camera_viewer_contract.json}"
rgb_output="${DOFBOT_CAMERA_VIEW_RGB:-$project_dir/artifacts/dofbot/camera_viewer_rgb.png}"
log_path="${DOFBOT_CAMERA_VIEWER_LOG:-$project_dir/artifacts/dofbot/camera_viewer.log}"

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_camera_config '%q' "$camera_config"
printf -v quoted_motion_config '%q' "$motion_config"
printf -v quoted_output '%q' "$output"
printf -v quoted_rgb_output '%q' "$rgb_output"
printf -v quoted_log_path '%q' "$log_path"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output)\" \"\$(dirname $quoted_rgb_output)\" \"\$(dirname $quoted_log_path)\"
stale_pids=\"\$(ps -eo pid=,comm=,args= | awk '\$2 ~ /^python/ && \$0 ~ /capture_dofbot_camera.py/ {print \$1}')\"
if [[ -n \"\$stale_pids\" ]]; then
  kill \$stale_pids 2>/dev/null || true
fi
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
nohup ./isaaclab.sh -p $quoted_project_dir/tools/capture_dofbot_camera.py \
  --asset-contract $quoted_asset_contract \
  --camera-config $quoted_camera_config \
  --motion-config $quoted_motion_config \
  --output $quoted_output \
  --rgb-output $quoted_rgb_output \
  --keep-alive \
  --git-commit \"\$git_commit\" \
  --device cpu \
  --enable_cameras \
  --livestream 2 \
  --viz kit \
  >$quoted_log_path 2>&1 </dev/null &
printf 'dofbot_camera_viewer_pid=%s\\n' \"\$!\"
printf 'log=%s\\n' $quoted_log_path
printf 'Viewer uses the onboard camera while the accepted safe motion repeats until stopped\\n'
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
