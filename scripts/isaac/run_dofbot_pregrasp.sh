#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
scene_config="${DOFBOT_PREGRASP_SCENE_CONFIG:-${REACHING:-configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json}}"
pose_config="${DOFBOT_PREGRASP_POSE_CONFIG:-${PREGRASP_POSE:-configs/dofbot/pregrasp/goal5_angled_pregrasp.json}}"
actuator_config="${DOFBOT_PREGRASP_ACTUATOR_CONFIG:-${GRAVITY_FEED_FORWARD_DIAGNOSTIC:-configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json}}"
actuator_result="${DOFBOT_PREGRASP_ACTUATOR_RESULT:-artifacts/dofbot/gravity_feed_forward_result_2026-07-31.json}"
preflight_contract="${DOFBOT_PREGRASP_PREFLIGHT_CONTRACT:-$project_dir/artifacts/dofbot/pregrasp_command_space_contract.json}"
output="${DOFBOT_PREGRASP_CONTRACT:-$project_dir/artifacts/dofbot/pregrasp_machine_contract.json}"
isaac_python="${ISAAC_PYTHON_EXE:-./_isaac_sim/python.sh}"

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
printf -v quoted_preflight_contract '%q' "$preflight_contract"
printf -v quoted_output '%q' "$output"
printf -v quoted_isaac_python '%q' "$isaac_python"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_output)\"
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
rm -f $quoted_output
set +e
pregrasp_exit_code=0
if [[ ! -x $quoted_isaac_python ]]; then
  printf '[PREGRASP GPU PREFLIGHT] FAIL: Isaac Python is not executable: %s\n' \
    $quoted_isaac_python >&2
  pregrasp_exit_code=126
else
  $quoted_isaac_python $quoted_project_dir/tools/verify_dofbot_pregrasp_gpu_preflight.py \
    --contract $quoted_preflight_contract \
    --project-dir $quoted_project_dir
  pregrasp_exit_code=\"\$?\"
fi
if [[ \"\$pregrasp_exit_code\" -eq 0 ]]; then
./isaaclab.sh -p $quoted_project_dir/tools/run_dofbot_pregrasp.py \
  --asset-contract $quoted_asset_contract \
  --scene-config $quoted_scene_config \
  --pose-config $quoted_pose_config \
  --actuator-config $quoted_actuator_config \
  --actuator-result $quoted_actuator_result \
  --output $quoted_output \
  --cycles 1 \
  --viewer-connection-hold-seconds 0 \
  --git-commit \"\$git_commit\" \
  --device cpu \
  --headless
pregrasp_exit_code=\"\$?\"
fi
if [[ \"\$pregrasp_exit_code\" -eq 0 ]]; then
  $quoted_isaac_python $quoted_project_dir/tools/verify_dofbot_pregrasp_machine_contract.py \
    --contract $quoted_output \
    --expected-git-commit \"\$git_commit\" \
    --preflight-contract $quoted_preflight_contract \
    --project-dir $quoted_project_dir
  pregrasp_exit_code=\"\$?\"
fi
set -e
printf '[PREGRASP_EXIT_CODE] %s\\n' \"\$pregrasp_exit_code\"
exit 0
"

remote_exec_script="$(dirname "$0")/../brev/remote_exec.sh"

if [[ "${REMOTE_DRY_RUN:-0}" == "1" ]]; then
  exec "$remote_exec_script" "$remote_command"
fi

pregrasp_log="$(mktemp -t dofbot-pregrasp.XXXXXX)"
trap 'rm -f "$pregrasp_log"' EXIT

set +e
"$remote_exec_script" "$remote_command" | tee "$pregrasp_log"
transport_exit_code="${PIPESTATUS[0]}"
set -e

if [[ "$transport_exit_code" -ne 0 ]]; then
  echo "Brev transport failed with exit code $transport_exit_code." >&2
  exit "$transport_exit_code"
fi

"$(dirname "$0")/../brev/require_zero_exit_sentinel.sh" \
  "$pregrasp_log" PREGRASP_EXIT_CODE
