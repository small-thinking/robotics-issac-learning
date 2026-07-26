#!/usr/bin/env bash
set -euo pipefail

task="${ISAAC_TASK:-Isaac-Cartpole-Direct-v0}"
rl_library="${ISAAC_RL_LIBRARY:-skrl}"
checkpoint="${ISAAC_CHECKPOINT:-}"
log_path="${ISAAC_PLAY_LOG:-/workspace/phase0/artifacts/logs/trained_cartpole.log}"

printf -v quoted_task '%q' "$task"
printf -v quoted_rl_library '%q' "$rl_library"
printf -v quoted_log_path '%q' "$log_path"

checkpoint_arg=""
if [[ -n "$checkpoint" ]]; then
  printf -v quoted_checkpoint '%q' "$checkpoint"
  checkpoint_arg="--checkpoint=$quoted_checkpoint"
fi

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_log_path)\"
stale_pids=\"\$(ps -eo pid=,comm=,args= | awk '\$2 ~ /^python/ && (\$0 ~ /random_agent.py/ || \$0 ~ /reinforcement_learning\\/play.py/) {print \$1}')\"
if [[ -n \"\$stale_pids\" ]]; then
  kill \$stale_pids 2>/dev/null || true
fi
nohup ./isaaclab.sh -p scripts/reinforcement_learning/play.py \
  --rl_library=$quoted_rl_library \
  --task=$quoted_task \
  --algorithm=PPO \
  --num_envs=1 \
  --livestream 2 \
  --viz kit \
  $checkpoint_arg \
  >$quoted_log_path 2>&1 </dev/null &
printf 'trained_cartpole_pid=%s\\n' \"\$!\"
printf 'log=%s\\n' $quoted_log_path
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
