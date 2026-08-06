#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
calibration_config="$project_dir/configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json"
scene_config="$project_dir/configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json"
decomposition_config="$project_dir/configs/dofbot/calibration/goal5_scene_decomposition.json"
collider_config="$project_dir/configs/dofbot/calibration/goal5_collider_audit.json"
output_dir="${DOFBOT_COLLIDER_AUDIT_CASES:-$project_dir/artifacts/dofbot/collider_audit_cases}"
summary_output="${DOFBOT_COLLIDER_AUDIT_RESULT:-$project_dir/artifacts/dofbot/collider_audit_result.json}"
case_timeout_seconds="${DOFBOT_COLLIDER_AUDIT_CASE_TIMEOUT_SECONDS:-180}"
deadline_seconds="${DOFBOT_COLLIDER_AUDIT_DEADLINE_SECONDS:-480}"

if ! [[ "$case_timeout_seconds" =~ ^[0-9]+$ ]] \
  || (( case_timeout_seconds < 60 || case_timeout_seconds > 180 )); then
  printf 'DOFBOT_COLLIDER_AUDIT_CASE_TIMEOUT_SECONDS must be in [60, 180]\n' >&2
  exit 2
fi
if ! [[ "$deadline_seconds" =~ ^[0-9]+$ ]] \
  || (( deadline_seconds < 360 || deadline_seconds > 480 )); then
  printf 'DOFBOT_COLLIDER_AUDIT_DEADLINE_SECONDS must be in [360, 480]\n' >&2
  exit 2
fi
if (( 2 * case_timeout_seconds > deadline_seconds )); then
  printf 'two case timeouts must fit inside the collider-audit deadline\n' >&2
  exit 2
fi

printf -v q_project '%q' "$project_dir"
printf -v q_asset '%q' "$asset_contract"
printf -v q_calibration '%q' "$calibration_config"
printf -v q_scene '%q' "$scene_config"
printf -v q_decomposition '%q' "$decomposition_config"
printf -v q_collider '%q' "$collider_config"
printf -v q_output_dir '%q' "$output_dir"
printf -v q_summary '%q' "$summary_output"
printf -v q_case_timeout '%q' "$case_timeout_seconds"
printf -v q_deadline '%q' "$deadline_seconds"

remote_command="
set -uo pipefail
mkdir -p $q_output_dir
git_commit=\"\$(git -C $q_project rev-parse HEAD)\"
run_stamp=\"\$(date -u '+%Y%m%dT%H%M%SZ')\"
archive_dir=$q_output_dir/archive-\"\$run_stamp\"
for stale_path in $q_output_dir/cell_s0.json $q_output_dir/cell_t1.json $q_summary; do
  if [[ -e \"\$stale_path\" ]]; then
    mkdir -p \"\$archive_dir\"
    mv \"\$stale_path\" \"\$archive_dir/\"
  fi
done

audit_started_epoch=\"\$(date +%s)\"
run_cell() {
  cell_id=\"\$1\"
  now_epoch=\"\$(date +%s)\"
  if (( now_epoch - audit_started_epoch >= $q_deadline )); then
    printf '[COLLIDER AUDIT] deadline reached before cell %s\n' \"\$cell_id\" >&2
    return 1
  fi
  output=$q_output_dir/cell_\"\${cell_id,,}\".json
  log=\"\$(mktemp -t dofbot-collider-\"\${cell_id,,}\".XXXXXX)\"
  timeout $q_case_timeout ./isaaclab.sh -p $q_project/tools/run_dofbot_actuator_calibration.py \\
    --asset-contract $q_asset \\
    --calibration-config $q_calibration \\
    --scene-config $q_scene \\
    --scene-decomposition-config $q_decomposition \\
    --scene-cell \"\$cell_id\" \\
    --collider-audit-config $q_collider \\
    --case-name bounded_gravity_feed_forward \\
    --output \"\$output\" \\
    --git-commit \"\$git_commit\" \\
    --device cpu --headless >\"\$log\" 2>&1
  runner_status=\"\$?\"
  grep -E '^\\[ACTUATOR CALIBRATION\\]|^\\[ERROR\\]' \"\$log\" || true
  if [[ \"\$runner_status\" -ne 0 || ! -s \"\$output\" ]]; then
    tail -80 \"\$log\" >&2 || true
    return 1
  fi
  ./_isaac_sim/python.sh $q_project/tools/verify_dofbot_collider_audit_case.py \\
    --artifact \"\$output\" --cell \"\$cell_id\" \\
    --project-dir $q_project --scene-config $q_decomposition \\
    --collider-config $q_collider --expected-git-commit \"\$git_commit\"
}

audit_status=0
run_cell S0 || audit_status=1
if [[ \"\$audit_status\" -eq 0 ]]; then
  run_cell T1 || audit_status=1
fi
if [[ \"\$audit_status\" -eq 0 ]]; then
  ./_isaac_sim/python.sh $q_project/tools/summarize_dofbot_collider_audit.py \\
    --input-dir $q_output_dir --project-dir $q_project \\
    --scene-config $q_decomposition --collider-config $q_collider \\
    --expected-git-commit \"\$git_commit\" --output $q_summary
  audit_status=\"\$?\"
fi
printf '[COLLIDER_AUDIT_EXIT_CODE] %s\n' \"\$audit_status\"
exit 0
"

remote_exec_script="$(dirname "$0")/../brev/remote_exec.sh"
if [[ "${REMOTE_DRY_RUN:-0}" == "1" ]]; then
  exec "$remote_exec_script" "$remote_command"
fi

audit_log="$(mktemp -t dofbot-collider-audit.XXXXXX)"
trap 'rm -f "$audit_log"' EXIT
set +e
"$remote_exec_script" "$remote_command" | tee "$audit_log"
transport_exit_code="${PIPESTATUS[0]}"
set -e
if (( transport_exit_code != 0 )); then
  printf 'Brev transport failed with exit code %s\n' "$transport_exit_code" >&2
  exit "$transport_exit_code"
fi
"$(dirname "$0")/../brev/require_zero_exit_sentinel.sh" \
  "$audit_log" COLLIDER_AUDIT_EXIT_CODE
