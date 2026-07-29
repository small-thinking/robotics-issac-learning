#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
scene_config="${DOFBOT_PREGRASP_SCENE_CONFIG:-${REACHING:-configs/dofbot/reaching/goal4_pregrasp_scene_candidate.json}}"
pose_config="${DOFBOT_PREGRASP_POSE_CONFIG:-${PREGRASP_POSE:-configs/dofbot/pregrasp/goal5_pose_aware_pregrasp.json}}"
output="${DOFBOT_PREGRASP_CONTRACT:-$project_dir/artifacts/dofbot/pregrasp_machine_contract.json}"

if [[ "$scene_config" != /* ]]; then
  scene_config="$project_dir/$scene_config"
fi
if [[ "$pose_config" != /* ]]; then
  pose_config="$project_dir/$pose_config"
fi

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_scene_config '%q' "$scene_config"
printf -v quoted_pose_config '%q' "$pose_config"
printf -v quoted_output '%q' "$output"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output)\"
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
./isaaclab.sh -p $quoted_project_dir/tools/run_dofbot_pregrasp.py \
  --asset-contract $quoted_asset_contract \
  --scene-config $quoted_scene_config \
  --pose-config $quoted_pose_config \
  --output $quoted_output \
  --cycles 1 \
  --viewer-connection-hold-seconds 0 \
  --git-commit \"\$git_commit\" \
  --device cpu \
  --headless
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
