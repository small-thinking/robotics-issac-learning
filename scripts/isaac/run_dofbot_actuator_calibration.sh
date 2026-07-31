#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
matrix_profile="${DOFBOT_ACTUATOR_MATRIX_PROFILE:-actuator}"
if [[ "$matrix_profile" == "actuator" ]]; then
  default_config="configs/dofbot/calibration/goal5_actuator_diagnostic.json"
  default_output_dir="$project_dir/artifacts/dofbot/actuator_calibration_cases"
  default_summary="$project_dir/artifacts/dofbot/actuator_calibration_contract.json"
  case_names=(
    gravity_on_effort_100
    gravity_off_effort_100
    gravity_on_effort_250
  )
elif [[ "$matrix_profile" == "solver_drive" ]]; then
  default_config="configs/dofbot/calibration/goal5_solver_drive_diagnostic.json"
  default_output_dir="$project_dir/artifacts/dofbot/solver_drive_diagnostic_cases"
  default_summary="$project_dir/artifacts/dofbot/solver_drive_diagnostic_contract.json"
  case_names=(
    baseline_tgs
    external_forces_each_iteration
    velocity_iterations_2
    reduced_damping_50
  )
elif [[ "$matrix_profile" == "drive_model" ]]; then
  default_config="configs/dofbot/calibration/goal5_drive_model_diagnostic.json"
  default_output_dir="$project_dir/artifacts/dofbot/drive_model_diagnostic_cases"
  default_summary="$project_dir/artifacts/dofbot/drive_model_diagnostic_contract.json"
  case_names=(
    acceleration_runtime_tuning
    force_runtime_tuning
    force_stiffness_1048
    force_damping_53
    force_authored_tuning
  )
elif [[ "$matrix_profile" == "gravity_feed_forward" ]]; then
  default_config="configs/dofbot/calibration/goal5_gravity_feed_forward_diagnostic.json"
  default_output_dir="$project_dir/artifacts/dofbot/gravity_feed_forward_cases"
  default_summary="$project_dir/artifacts/dofbot/gravity_feed_forward_contract.json"
  case_names=(
    force_damping_53_baseline
    bounded_gravity_feed_forward
  )
else
  printf 'DOFBOT_ACTUATOR_MATRIX_PROFILE must be actuator, solver_drive, drive_model, or gravity_feed_forward\n' >&2
  exit 2
fi
calibration_config="${DOFBOT_ACTUATOR_CALIBRATION_CONFIG:-${ACTUATOR_CALIBRATION:-$default_config}}"
output_dir="${DOFBOT_ACTUATOR_CALIBRATION_DIR:-$default_output_dir}"
summary_output="${DOFBOT_ACTUATOR_CALIBRATION_CONTRACT:-$default_summary}"
case_timeout_seconds="${DOFBOT_ACTUATOR_CASE_TIMEOUT_SECONDS:-300}"

if ! [[ "$case_timeout_seconds" =~ ^[0-9]+$ ]] \
  || (( case_timeout_seconds < 60 || case_timeout_seconds > 600 )); then
  printf 'DOFBOT_ACTUATOR_CASE_TIMEOUT_SECONDS must be an integer in [60, 600]\n' >&2
  exit 2
fi

if [[ "$calibration_config" != /* ]]; then
  calibration_config="$project_dir/$calibration_config"
fi

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_asset_contract '%q' "$asset_contract"
printf -v quoted_calibration_config '%q' "$calibration_config"
printf -v quoted_output_dir '%q' "$output_dir"
printf -v quoted_summary_output '%q' "$summary_output"
printf -v quoted_case_timeout_seconds '%q' "$case_timeout_seconds"
quoted_case_names=""
for case_name in "${case_names[@]}"; do
  printf -v quoted_case_name '%q' "$case_name"
  quoted_case_names+="$quoted_case_name "
done

remote_command="
set -uo pipefail
mkdir -p $quoted_output_dir
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
run_stamp=\"\$(date -u '+%Y%m%dT%H%M%SZ')\"
archive_dir=$quoted_output_dir/archive-\"\$run_stamp\"
case_names=($quoted_case_names)
stale_paths=($quoted_summary_output)
for case_name in \"\${case_names[@]}\"; do
  stale_paths+=( \
    $quoted_output_dir/\"\${case_name}.json\" \
    $quoted_output_dir/\"\${case_name}.log\" \
  )
done
for stale_path in \"\${stale_paths[@]}\"; do
  if [[ -e \"\$stale_path\" ]]; then
    mkdir -p \"\$archive_dir\"
    mv \"\$stale_path\" \"\$archive_dir/\"
  fi
done
matrix_exit_code=0
run_case() {
  case_name=\"\$1\"
  case_output=$quoted_output_dir/\"\${case_name}.json\"
  case_log=$quoted_output_dir/\"\${case_name}.log\"
  case_failed=0
  if ! timeout $quoted_case_timeout_seconds \
    ./isaaclab.sh -p $quoted_project_dir/tools/run_dofbot_actuator_calibration.py \
    --asset-contract $quoted_asset_contract \
    --calibration-config $quoted_calibration_config \
    --case-name \"\$case_name\" \
    --output \"\$case_output\" \
    --git-commit \"\$git_commit\" \
    --device cpu \
    --headless >\"\$case_log\" 2>&1; then
    case_failed=1
  fi
  if [[ ! -s \"\$case_output\" ]]; then
    printf '[ACTUATOR MATRIX] missing_case_artifact=%s\n' \"\$case_output\" >&2
    case_failed=1
  fi
  if (( case_failed != 0 )); then
    printf '[ACTUATOR MATRIX] case_failed=%s log=%s\n' \
      \"\$case_name\" \"\$case_log\" >&2
    tail -80 \"\$case_log\" >&2 || true
    matrix_exit_code=1
  else
    grep -E '^\[ACTUATOR CALIBRATION\]' \"\$case_log\" || true
  fi
}
for case_name in \"\${case_names[@]}\"; do
  run_case \"\$case_name\"
done
if ! timeout 60 \
  ./isaaclab.sh -p $quoted_project_dir/tools/summarize_dofbot_actuator_calibration.py \
  --config $quoted_calibration_config \
  --input-dir $quoted_output_dir \
  --output $quoted_summary_output \
  --git-commit \"\$git_commit\"; then
  matrix_exit_code=1
fi
printf '[MATRIX_EXIT_CODE] %s\n' \"\$matrix_exit_code\"
exit 0
"

remote_exec_script="$(dirname "$0")/../brev/remote_exec.sh"
if [[ "${REMOTE_DRY_RUN:-0}" == "1" ]]; then
  exec "$remote_exec_script" "$remote_command"
fi

matrix_log="$(mktemp -t dofbot-actuator-matrix.XXXXXX)"
trap 'rm -f "$matrix_log"' EXIT
set +e
"$remote_exec_script" "$remote_command" | tee "$matrix_log"
transport_exit_code="${PIPESTATUS[0]}"
set -e
if (( transport_exit_code != 0 )); then
  printf 'Brev transport failed with exit code %s\n' "$transport_exit_code" >&2
  exit "$transport_exit_code"
fi
if ! grep -Fqx '[MATRIX_EXIT_CODE] 0' "$matrix_log"; then
  printf 'DOFBOT actuator matrix did not report a zero internal exit code\n' >&2
  exit 1
fi
