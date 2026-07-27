#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
isaaclab_dir="${ISAACLAB_DIR:-/workspace/isaaclab}"
task="${ISAAC_TASK:-Isaac-Cartpole-v0}"
checkpoint="${ISAAC_CHECKPOINT:-}"
variant="${ISAAC_VARIANT:-B0}"
profile="${ISAAC_EVAL_PROFILE:-canonical5}"
num_envs="${ISAAC_EVAL_NUM_ENVS:-5}"
max_steps_per_seed="${ISAAC_EVAL_MAX_STEPS:-}"

if [[ -z "$checkpoint" ]]; then
  printf 'ISAAC_CHECKPOINT must name the exact trained checkpoint for evaluation.\n' >&2
  exit 2
fi

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_isaaclab_dir '%q' "$isaaclab_dir"
printf -v quoted_task '%q' "$task"
printf -v quoted_checkpoint '%q' "$checkpoint"

if [[ -z "$max_steps_per_seed" ]]; then
  if [[ "$profile" == "stress30" ]]; then
    max_steps_per_seed=3600
  else
    max_steps_per_seed=1000
  fi
fi

variant_hydra_args=""
while IFS= read -r token; do
  [[ -z "$token" ]] && continue
  printf -v quoted_token '%q' "$token"
  variant_hydra_args+=" $quoted_token"
done < <(
  python3 "$repo_root/tools/cartpole_variants.py" hydra-args \
    "$variant" --scope eval --profile "$profile"
)

remote_command="
set -euo pipefail
cd $quoted_isaaclab_dir
./isaaclab.sh -p $quoted_project_dir/tools/evaluate_cartpole.py \
  --policy=random \
  --task=$quoted_task \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=$num_envs \
  --max-steps-per-seed=$max_steps_per_seed \
  --output=$quoted_project_dir/artifacts/evaluations/random_policy.json \
  --viz none \
  $variant_hydra_args
./isaaclab.sh -p $quoted_project_dir/tools/evaluate_cartpole.py \
  --policy=trained \
  --task=$quoted_task \
  --checkpoint=$quoted_checkpoint \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=$num_envs \
  --max-steps-per-seed=$max_steps_per_seed \
  --output=$quoted_project_dir/artifacts/evaluations/trained_policy.json \
  --viz none \
  $variant_hydra_args
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
