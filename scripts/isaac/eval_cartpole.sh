#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
isaaclab_dir="${ISAACLAB_DIR:-/workspace/isaaclab}"
checkpoint="${ISAAC_CHECKPOINT:-}"

if [[ -z "$checkpoint" ]]; then
  printf 'ISAAC_CHECKPOINT must name the exact trained checkpoint for evaluation.\n' >&2
  exit 2
fi

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_isaaclab_dir '%q' "$isaaclab_dir"
printf -v quoted_checkpoint '%q' "$checkpoint"

remote_command="
set -euo pipefail
cd $quoted_isaaclab_dir
./isaaclab.sh -p $quoted_project_dir/tools/evaluate_cartpole.py \
  --policy=random \
  --task=Isaac-Cartpole-Direct-v0 \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=64 \
  --output=$quoted_project_dir/artifacts/evaluations/random_policy.json \
  --viz none
./isaaclab.sh -p $quoted_project_dir/tools/evaluate_cartpole.py \
  --policy=trained \
  --task=Isaac-Cartpole-Direct-v0 \
  --checkpoint=$quoted_checkpoint \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=64 \
  --output=$quoted_project_dir/artifacts/evaluations/trained_policy.json \
  --viz none
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
