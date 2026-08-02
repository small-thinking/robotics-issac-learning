#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
split_config="$project_dir/configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json"
direct_config="$project_dir/configs/dofbot/calibration/goal5_gravity_feed_forward_direct_diagnostic.json"
scene_config="$project_dir/configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json"
failed_direct_reference="$project_dir/artifacts/dofbot/pregrasp_single_boundary_discriminator_2026-08-01.json"
output_dir="${DOFBOT_CONTEXT_TRANSFER_CASES:-$project_dir/artifacts/dofbot/context_transfer_cases}"
summary_output="${DOFBOT_CONTEXT_TRANSFER_RESULT:-$project_dir/artifacts/dofbot/context_transfer_matrix_contract.json}"
case_timeout_seconds="${DOFBOT_CONTEXT_TRANSFER_TIMEOUT_SECONDS:-300}"

if ! [[ "$case_timeout_seconds" =~ ^[0-9]+$ ]] \
  || (( case_timeout_seconds < 60 || case_timeout_seconds > 600 )); then
  printf 'DOFBOT_CONTEXT_TRANSFER_TIMEOUT_SECONDS must be in [60, 600]\n' >&2
  exit 2
fi

printf -v q_project '%q' "$project_dir"
printf -v q_asset '%q' "$asset_contract"
printf -v q_split '%q' "$split_config"
printf -v q_direct '%q' "$direct_config"
printf -v q_scene '%q' "$scene_config"
printf -v q_reference '%q' "$failed_direct_reference"
printf -v q_output_dir '%q' "$output_dir"
printf -v q_summary '%q' "$summary_output"
printf -v q_timeout '%q' "$case_timeout_seconds"

remote_command="
set -uo pipefail
mkdir -p $q_output_dir
git_commit=\"\$(git -C $q_project rev-parse HEAD)\"
run_stamp=\"\$(date -u '+%Y%m%dT%H%M%SZ')\"
archive_dir=$q_output_dir/archive-\"\$run_stamp\"
stale_paths=($q_summary $q_output_dir/cell_a.json $q_output_dir/cell_b.json $q_output_dir/cell_c.json)
for stale_path in \"\${stale_paths[@]}\"; do
  if [[ -e \"\$stale_path\" ]]; then
    mkdir -p \"\$archive_dir\"
    mv \"\$stale_path\" \"\$archive_dir/\"
  fi
done

run_cell() {
  cell_id=\"\$1\"
  config=\"\$2\"
  scene=\"\$3\"
  output=$q_output_dir/cell_\"\${cell_id,,}\".json
  log=\"\$(mktemp -t dofbot-context-\"\${cell_id,,}\".XXXXXX)\"
  scene_args=()
  if [[ -n \"\$scene\" ]]; then
    scene_args=(--scene-config \"\$scene\")
  fi
  timeout $q_timeout ./isaaclab.sh -p $q_project/tools/run_dofbot_actuator_calibration.py \\
    --asset-contract $q_asset \\
    --calibration-config \"\$config\" \\
    \"\${scene_args[@]}\" \\
    --case-name bounded_gravity_feed_forward \\
    --output \"\$output\" \\
    --git-commit \"\$git_commit\" \\
    --device cpu --headless >\"\$log\" 2>&1
  runner_status=\"\$?\"
  grep -E '^\[ACTUATOR CALIBRATION\]|^\[ERROR\]' \"\$log\" || true
  if [[ \"\$runner_status\" -ne 0 || ! -s \"\$output\" ]]; then
    tail -80 \"\$log\" >&2 || true
    return 1
  fi
  ./_isaac_sim/python.sh $q_project/tools/verify_dofbot_context_transfer_case.py \\
    --artifact \"\$output\" --cell \"\$cell_id\" \\
    --project-dir $q_project --expected-git-commit \"\$git_commit\"
}

matrix_status=0
run_cell A $q_split ''
a_status=\"\$?\"
if [[ \"\$a_status\" -ne 0 ]]; then
  ./_isaac_sim/python.sh $q_project/tools/summarize_dofbot_context_transfer_matrix.py \\
    --input-dir $q_output_dir --project-dir $q_project \\
    --expected-git-commit \"\$git_commit\" \\
    --failed-direct-reference $q_reference --output $q_summary
  matrix_status=\"\$?\"
else
  run_cell B $q_direct '' || matrix_status=1
  run_cell C $q_split $q_scene || matrix_status=1
  if [[ \"\$matrix_status\" -eq 0 ]]; then
    ./_isaac_sim/python.sh $q_project/tools/summarize_dofbot_context_transfer_matrix.py \\
      --input-dir $q_output_dir --project-dir $q_project \\
      --expected-git-commit \"\$git_commit\" \\
      --failed-direct-reference $q_reference --output $q_summary
    matrix_status=\"\$?\"
  fi
fi
printf '[CONTEXT_TRANSFER_EXIT_CODE] %s\n' \"\$matrix_status\"
exit 0
"

remote_exec_script="$(dirname "$0")/../brev/remote_exec.sh"
if [[ "${REMOTE_DRY_RUN:-0}" == "1" ]]; then
  exec "$remote_exec_script" "$remote_command"
fi

matrix_log="$(mktemp -t dofbot-context-transfer.XXXXXX)"
trap 'rm -f "$matrix_log"' EXIT
set +e
"$remote_exec_script" "$remote_command" | tee "$matrix_log"
transport_exit_code="${PIPESTATUS[0]}"
set -e
if (( transport_exit_code != 0 )); then
  printf 'Brev transport failed with exit code %s\n' "$transport_exit_code" >&2
  exit "$transport_exit_code"
fi
"$(dirname "$0")/../brev/require_zero_exit_sentinel.sh" \
  "$matrix_log" CONTEXT_TRANSFER_EXIT_CODE
