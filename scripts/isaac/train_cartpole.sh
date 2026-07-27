#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
task="${ISAAC_TASK:-Isaac-Cartpole-v0}"
rl_library="${ISAAC_RL_LIBRARY:-skrl}"
seed="${ISAAC_TRAIN_SEED:-42}"
num_envs="${ISAAC_NUM_ENVS:-4096}"
max_iterations="${ISAAC_MAX_ITERATIONS:-}"
log_path="${ISAAC_TRAIN_LOG:-/workspace/phase1/artifacts/logs/train_cartpole_manager.log}"
variant="${ISAAC_VARIANT:-B0}"

printf -v quoted_task '%q' "$task"
printf -v quoted_rl_library '%q' "$rl_library"
printf -v quoted_log_path '%q' "$log_path"

max_iterations_arg=""
if [[ -n "$max_iterations" ]]; then
  printf -v quoted_max_iterations '%q' "$max_iterations"
  max_iterations_arg="--max_iterations=$quoted_max_iterations"
fi

variant_hydra_args=""
while IFS= read -r token; do
  [[ -z "$token" ]] && continue
  printf -v quoted_token '%q' "$token"
  variant_hydra_args+=" $quoted_token"
done < <(
  python3 "$repo_root/tools/cartpole_variants.py" hydra-args \
    "$variant" --scope train
)

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
  $variant_hydra_args \
  2>&1 | tee $quoted_log_path
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
