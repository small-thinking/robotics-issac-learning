#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
camera_config="${DOFBOT_CAMERA_CONFIG:-$project_dir/configs/dofbot/camera/goal3_onboard_rgb.json}"
output="${DOFBOT_CAMERA_CONTRACT:-$project_dir/artifacts/dofbot/camera_contract.json}"
rgb_output="${DOFBOT_CAMERA_RGB:-$project_dir/artifacts/dofbot/camera_rgb.png}"

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_camera_config '%q' "$camera_config"
printf -v quoted_output '%q' "$output"
printf -v quoted_rgb_output '%q' "$rgb_output"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output)\" \"\$(dirname $quoted_rgb_output)\"
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
./isaaclab.sh -p $quoted_project_dir/tools/capture_dofbot_camera.py \
  --asset-contract $quoted_asset_contract \
  --camera-config $quoted_camera_config \
  --output $quoted_output \
  --rgb-output $quoted_rgb_output \
  --git-commit \"\$git_commit\" \
  --device cpu \
  --enable_cameras \
  --headless
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
