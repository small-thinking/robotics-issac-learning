#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
calibration_config="$project_dir/configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json"
scene_config="$project_dir/configs/dofbot/reaching/goal5_angled_pregrasp_scene_candidate.json"
decomposition_config="$project_dir/configs/dofbot/calibration/goal5_scene_decomposition.json"
output_dir="${DOFBOT_SCENE_DECOMPOSITION_CASES:-$project_dir/artifacts/dofbot/scene_decomposition_cases}"
summary_output="${DOFBOT_SCENE_DECOMPOSITION_RESULT:-$project_dir/artifacts/dofbot/scene_decomposition_matrix_contract.json}"
case_timeout_seconds="${DOFBOT_SCENE_DECOMPOSITION_CASE_TIMEOUT_SECONDS:-180}"
matrix_deadline_seconds="${DOFBOT_SCENE_DECOMPOSITION_DEADLINE_SECONDS:-1200}"

if ! [[ "$case_timeout_seconds" =~ ^[0-9]+$ ]] \
  || (( case_timeout_seconds < 60 || case_timeout_seconds > 240 )); then
  printf 'DOFBOT_SCENE_DECOMPOSITION_CASE_TIMEOUT_SECONDS must be in [60, 240]\n' >&2
  exit 2
fi
if ! [[ "$matrix_deadline_seconds" =~ ^[0-9]+$ ]] \
  || (( matrix_deadline_seconds < 600 || matrix_deadline_seconds > 1200 )); then
  printf 'DOFBOT_SCENE_DECOMPOSITION_DEADLINE_SECONDS must be in [600, 1200]\n' >&2
  exit 2
fi
if (( 6 * case_timeout_seconds > matrix_deadline_seconds )); then
  printf 'six case timeouts must fit inside the matrix deadline\n' >&2
  exit 2
fi

printf -v q_project '%q' "$project_dir"
printf -v q_asset '%q' "$asset_contract"
printf -v q_calibration '%q' "$calibration_config"
printf -v q_scene '%q' "$scene_config"
printf -v q_decomposition '%q' "$decomposition_config"
printf -v q_output_dir '%q' "$output_dir"
printf -v q_summary '%q' "$summary_output"
printf -v q_case_timeout '%q' "$case_timeout_seconds"
printf -v q_deadline '%q' "$matrix_deadline_seconds"

remote_command="
set -uo pipefail
mkdir -p $q_output_dir
git_commit=\"\$(git -C $q_project rev-parse HEAD)\"
run_stamp=\"\$(date -u '+%Y%m%dT%H%M%SZ')\"
archive_dir=$q_output_dir/archive-\"\$run_stamp\"
stale_paths=($q_summary)
for cell_id in s0 t1 t0 tf q1 q0 qf p1 p0 pf; do
  stale_paths+=(\"$q_output_dir/cell_\$cell_id.json\")
done
for stale_path in \"\${stale_paths[@]}\"; do
  if [[ -e \"\$stale_path\" ]]; then
    mkdir -p \"\$archive_dir\"
    mv \"\$stale_path\" \"\$archive_dir/\"
  fi
done

matrix_started_epoch=\"\$(date +%s)\"
executed_cell_count=0
cell_tracking_passed=''

run_cell() {
  cell_id=\"\$1\"
  now_epoch=\"\$(date +%s)\"
  elapsed_seconds=\"\$((now_epoch - matrix_started_epoch))\"
  if (( elapsed_seconds >= $q_deadline )); then
    printf '[SCENE MATRIX] deadline reached before cell %s\n' \"\$cell_id\" >&2
    return 1
  fi
  executed_cell_count=\"\$((executed_cell_count + 1))\"
  if (( executed_cell_count > 6 )); then
    printf '[SCENE MATRIX] adaptive cell cap exceeded\n' >&2
    return 1
  fi
  output=$q_output_dir/cell_\"\${cell_id,,}\".json
  log=\"\$(mktemp -t dofbot-scene-\"\${cell_id,,}\".XXXXXX)\"
  timeout $q_case_timeout ./isaaclab.sh -p $q_project/tools/run_dofbot_actuator_calibration.py \\
    --asset-contract $q_asset \\
    --calibration-config $q_calibration \\
    --scene-config $q_scene \\
    --scene-decomposition-config $q_decomposition \\
    --scene-cell \"\$cell_id\" \\
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
  verifier_output=\"\$(./_isaac_sim/python.sh \\
    $q_project/tools/verify_dofbot_scene_decomposition_case.py \\
    --artifact \"\$output\" --cell \"\$cell_id\" \\
    --project-dir $q_project --config $q_decomposition \\
    --expected-git-commit \"\$git_commit\" --allow-sentinel-failure)\"
  verifier_status=\"\$?\"
  printf '%s\\n' \"\$verifier_output\"
  if [[ \"\$verifier_status\" -ne 0 ]]; then
    return 1
  fi
  cell_tracking_passed=\"\$(printf '%s\\n' \"\$verifier_output\" \\
    | sed -n 's/.*tracking_gate_passed=\\(true\\|false\\).*/\\1/p')\"
  [[ \"\$cell_tracking_passed\" == true || \"\$cell_tracking_passed\" == false ]]
}

matrix_status=0
run_cell S0 || matrix_status=1
if [[ \"\$matrix_status\" -eq 0 && \"\$cell_tracking_passed\" == true ]]; then
  run_cell T1 || matrix_status=1
  if [[ \"\$matrix_status\" -eq 0 && \"\$cell_tracking_passed\" == false ]]; then
    run_cell T0 || matrix_status=1
    [[ \"\$matrix_status\" -ne 0 ]] || run_cell TF || matrix_status=1
  elif [[ \"\$matrix_status\" -eq 0 ]]; then
    run_cell Q1 || matrix_status=1
    if [[ \"\$matrix_status\" -eq 0 && \"\$cell_tracking_passed\" == false ]]; then
      run_cell Q0 || matrix_status=1
      [[ \"\$matrix_status\" -ne 0 ]] || run_cell QF || matrix_status=1
    elif [[ \"\$matrix_status\" -eq 0 ]]; then
      run_cell P1 || matrix_status=1
      if [[ \"\$matrix_status\" -eq 0 && \"\$cell_tracking_passed\" == false ]]; then
        run_cell P0 || matrix_status=1
        [[ \"\$matrix_status\" -ne 0 ]] || run_cell PF || matrix_status=1
      fi
    fi
  fi
fi
if [[ \"\$matrix_status\" -eq 0 ]]; then
  ./_isaac_sim/python.sh $q_project/tools/summarize_dofbot_scene_decomposition_matrix.py \\
    --input-dir $q_output_dir --project-dir $q_project \\
    --config $q_decomposition --expected-git-commit \"\$git_commit\" \\
    --output $q_summary
  matrix_status=\"\$?\"
fi
printf '[SCENE_DECOMPOSITION_EXIT_CODE] %s\n' \"\$matrix_status\"
exit 0
"

remote_exec_script="$(dirname "$0")/../brev/remote_exec.sh"
if [[ "${REMOTE_DRY_RUN:-0}" == "1" ]]; then
  exec "$remote_exec_script" "$remote_command"
fi

matrix_log="$(mktemp -t dofbot-scene-decomposition.XXXXXX)"
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
  "$matrix_log" SCENE_DECOMPOSITION_EXIT_CODE
