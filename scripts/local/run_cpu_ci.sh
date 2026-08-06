#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_root"

ci_tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/robotics-cpu-ci.XXXXXX")"
trap 'rm -rf "$ci_tmp_dir"' EXIT

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/robotics-isaac-uv-cache}"
export UV_TOOL_DIR="${UV_TOOL_DIR:-$ci_tmp_dir/uv-tools}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-$ci_tmp_dir/python-cache}"

export DOFBOT_API_PREVIEW_OUTPUT="$ci_tmp_dir/dofbot-yahboom-api-preview.json"
export DOFBOT_MOTION_CONFIG_PREVIEW_OUTPUT="$ci_tmp_dir/dofbot-motion-config-preview.json"
export DOFBOT_REACHING_PREVIEW_OUTPUT="$ci_tmp_dir/dofbot-reaching-preview.json"
export DOFBOT_PREGRASP_JSON="$ci_tmp_dir/dofbot-pregrasp-scene-calibration.json"
export DOFBOT_PREGRASP_SVG="$ci_tmp_dir/dofbot-pregrasp-scene-calibration.svg"
export DOFBOT_PREGRASP_POSE_OUTPUT="$ci_tmp_dir/dofbot-pregrasp-pose-contract.json"
export DOFBOT_PREGRASP_REACHABILITY_OUTPUT="$ci_tmp_dir/dofbot-pregrasp-reachability.json"
export DOFBOT_PREGRASP_TASKSPACE_OUTPUT="$ci_tmp_dir/dofbot-pregrasp-taskspace.json"
export DOFBOT_ACTUATOR_CALIBRATION_PLAN="$ci_tmp_dir/dofbot-actuator-calibration-plan.json"
export DOFBOT_SOLVER_DRIVE_PLAN="$ci_tmp_dir/dofbot-solver-drive-plan.json"
export DOFBOT_DRIVE_MODEL_PLAN="$ci_tmp_dir/dofbot-drive-model-plan.json"
export DOFBOT_VELOCITY_REANALYSIS="$ci_tmp_dir/dofbot-velocity-reanalysis.json"
export DOFBOT_VELOCITY_EVIDENCE_AUDIT="$ci_tmp_dir/dofbot-velocity-evidence-audit.json"
export DOFBOT_RESIDUAL_FORCE_AUDIT="$ci_tmp_dir/dofbot-residual-force-audit.json"
export DOFBOT_RESIDUAL_FORCE_EVIDENCE_AUDIT="$ci_tmp_dir/dofbot-residual-force-evidence-audit.json"
export DOFBOT_GRAVITY_FEED_FORWARD_PLAN="$ci_tmp_dir/dofbot-gravity-feed-forward-plan.json"
dofbot_context_transfer_audit="$ci_tmp_dir/dofbot-context-transfer-audit.json"
export DOFBOT_SCENE_DECOMPOSITION_PLAN="$ci_tmp_dir/dofbot-scene-decomposition-plan.json"

printf '[cpu-ci] Ruff\n'
if command -v ruff >/dev/null 2>&1 && [[ "$(ruff --version)" == "ruff 0.15.0" ]]; then
  ruff check .
else
  uvx --from ruff==0.15.0 ruff check .
fi

printf '[cpu-ci] Repository tests\n'
make test

printf '[cpu-ci] Python compilation\n'
uv run --python 3.12 python -m compileall -q tools tests

printf '[cpu-ci] Shell syntax\n'
while IFS= read -r script; do
  bash -n "$script"
done < <(find scripts tests -type f -name '*.sh' -print | sort)

printf '[cpu-ci] Phase 2 deterministic contracts\n'
make study-validate
make study-matrix >"$ci_tmp_dir/phase2-matrix.txt"
make show-variant >"$ci_tmp_dir/phase2-variant.txt"
make show-manifest >"$ci_tmp_dir/phase2-manifest.txt"
make show-study-run >"$ci_tmp_dir/phase2-study-run.txt"

printf '[cpu-ci] DOFBOT deterministic previews and offline analyses\n'
make dofbot-api-dry-run
make dofbot-motion-config-dry-run
make dofbot-reach-dry-run
make dofbot-pregrasp-dry-run
make dofbot-pregrasp-pose-dry-run
make dofbot-gpu-preflight
make dofbot-pregrasp-reachability
make dofbot-pregrasp-taskspace
make dofbot-actuator-calibration-dry-run
make dofbot-solver-drive-dry-run
make dofbot-drive-model-dry-run
velocity_input_dir="${ACTUATOR_CALIBRATION_CASES:-artifacts/dofbot/actuator_calibration_cases}"
velocity_sources=(
  "$velocity_input_dir/gravity_off_effort_100.json"
  "$velocity_input_dir/gravity_on_effort_100.json"
  "$velocity_input_dir/gravity_on_effort_250.json"
)
velocity_sources_available=true
for source in "${velocity_sources[@]}"; do
  if [[ ! -f "$source" ]]; then
    velocity_sources_available=false
  fi
done
if [[ "$velocity_sources_available" == true ]]; then
  make dofbot-actuator-velocity-reanalysis
else
  printf '[cpu-ci] Raw velocity payloads are intentionally untracked; full replay skipped\n'
fi
make dofbot-actuator-velocity-evidence-audit
residual_input_dir="${DRIVE_MODEL_DIAGNOSTIC_CASES:-artifacts/dofbot/drive_model_diagnostic_cases}"
residual_sources=(
  "$residual_input_dir/force_damping_53.json"
  "$residual_input_dir/force_authored_tuning.json"
)
residual_sources_available=true
for source in "${residual_sources[@]}"; do
  if [[ ! -f "$source" ]]; then
    residual_sources_available=false
  fi
done
if [[ "$residual_sources_available" == true ]]; then
  make dofbot-residual-force-audit
else
  printf '[cpu-ci] Raw residual-force payloads are intentionally untracked; full replay skipped\n'
fi
make dofbot-residual-force-evidence-audit
if [[ "$residual_sources_available" != true ]]; then
  export DOFBOT_RESIDUAL_FORCE_AUDIT="artifacts/dofbot/residual_force_audit_2026-07-30.json"
fi
make dofbot-gravity-feed-forward-dry-run
DOFBOT_CONTEXT_TRANSFER_AUDIT="$dofbot_context_transfer_audit" \
  DOFBOT_CONTEXT_TRANSFER_EXPECTED=artifacts/dofbot/pregrasp_context_transfer_audit.json \
  make dofbot-context-transfer-audit
make dofbot-scene-decomposition-dry-run

printf '[cpu-ci] Generated artifact validation\n'
while IFS= read -r -d '' artifact; do
  uv run --python 3.12 python -m json.tool "$artifact" >/dev/null
done < <(find "$ci_tmp_dir" -type f -name '*.json' -print0)

cmp "$DOFBOT_PREGRASP_POSE_OUTPUT" \
  artifacts/dofbot/pregrasp_command_space_contract.json

printf '[cpu-ci] PASS: CPU-only repository and deterministic contract gates\n'
printf '[cpu-ci] NOTE: Isaac/PhysX/GPU/Viewer gates were intentionally not run\n'
