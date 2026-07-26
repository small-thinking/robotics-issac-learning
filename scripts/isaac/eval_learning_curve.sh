#!/usr/bin/env bash
set -euo pipefail

project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
isaaclab_dir="${ISAACLAB_DIR:-/workspace/isaaclab}"
task="${ISAAC_TASK:-Isaac-Cartpole-v0}"
checkpoint_dir="${ISAAC_CHECKPOINT_DIR:-}"
training_num_envs="${ISAAC_NUM_ENVS:-4096}"
curve_json="${ISAAC_CURVE_JSON:-$project_dir/artifacts/evaluations/phase1_learning_curve.json}"
curve_svg="${ISAAC_CURVE_SVG:-$project_dir/artifacts/plots/phase1_learning_curve.svg}"

if [[ -z "$checkpoint_dir" ]]; then
  printf 'ISAAC_CHECKPOINT_DIR must name the exact training run checkpoint directory.\n' >&2
  exit 2
fi

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_isaaclab_dir '%q' "$isaaclab_dir"
printf -v quoted_task '%q' "$task"
printf -v quoted_checkpoint_dir '%q' "$checkpoint_dir"
printf -v quoted_training_num_envs '%q' "$training_num_envs"
printf -v quoted_curve_json '%q' "$curve_json"
printf -v quoted_curve_svg '%q' "$curve_svg"

remote_command="
set -euo pipefail
cd $quoted_isaaclab_dir
./isaaclab.sh -p $quoted_project_dir/tools/evaluate_cartpole.py \
  --policy=sweep \
  --task=$quoted_task \
  --checkpoint-dir=$quoted_checkpoint_dir \
  --training-num-envs=$quoted_training_num_envs \
  --include-random-baseline \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=64 \
  --output=$quoted_curve_json \
  --viz none
./isaaclab.sh -p $quoted_project_dir/tools/render_learning_curve.py \
  $quoted_curve_json \
  $quoted_curve_svg
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
