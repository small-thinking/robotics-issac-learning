#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
asset_contract="${DOFBOT_ASSET_CONTRACT:-$project_dir/artifacts/dofbot/asset_contract.json}"
calibration_config="${DOFBOT_ACTUATOR_CALIBRATION_CONFIG:-${ACTUATOR_CALIBRATION:-configs/dofbot/calibration/goal5_actuator_diagnostic.json}}"
output_dir="${DOFBOT_ACTUATOR_CALIBRATION_DIR:-$project_dir/artifacts/dofbot/actuator_calibration_cases}"
summary_output="${DOFBOT_ACTUATOR_CALIBRATION_CONTRACT:-$project_dir/artifacts/dofbot/actuator_calibration_contract.json}"
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

remote_command="
set -uo pipefail
mkdir -p $quoted_output_dir
git_commit=\"\$(git -C $quoted_project_dir rev-parse HEAD)\"
run_stamp=\"\$(date -u '+%Y%m%dT%H%M%SZ')\"
archive_dir=$quoted_output_dir/archive-\"\$run_stamp\"
for stale_path in \
  $quoted_output_dir/gravity_on_effort_100.json \
  $quoted_output_dir/gravity_off_effort_100.json \
  $quoted_output_dir/gravity_on_effort_250.json \
  $quoted_output_dir/gravity_on_effort_100.log \
  $quoted_output_dir/gravity_off_effort_100.log \
  $quoted_output_dir/gravity_on_effort_250.log \
  $quoted_summary_output; do
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
run_case gravity_on_effort_100
run_case gravity_off_effort_100
run_case gravity_on_effort_250
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
