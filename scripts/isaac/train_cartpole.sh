#!/usr/bin/env bash
set -euo pipefail

task="${ISAAC_TASK:-Isaac-Cartpole-v0}"
rl_library="${ISAAC_RL_LIBRARY:-skrl}"
seed="${ISAAC_TRAIN_SEED:-42}"
num_envs="${ISAAC_NUM_ENVS:-4096}"
max_iterations="${ISAAC_MAX_ITERATIONS:-}"
log_path="${ISAAC_TRAIN_LOG:-/workspace/phase1/artifacts/logs/train_cartpole_manager.log}"

printf -v quoted_task '%q' "$task"
printf -v quoted_rl_library '%q' "$rl_library"
printf -v quoted_log_path '%q' "$log_path"

max_iterations_arg=""
if [[ -n "$max_iterations" ]]; then
  printf -v quoted_max_iterations '%q' "$max_iterations"
  max_iterations_arg="--max_iterations=$quoted_max_iterations"
fi

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_log_path)\"
./isaaclab.sh -p scripts/reinforcement_learning/train.py \
  --rl_library=$quoted_rl_library \
  --task=$quoted_task \
  --algorithm=PPO \
  --seed=$seed \
  --num_envs=$num_envs \
  $max_iterations_arg \
  --viz none \
  2>&1 | tee $quoted_log_path
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
