#!/usr/bin/env bash
set -euo pipefail

task="${ISAAC_TASK:-Isaac-Cartpole-Direct-v0}"
num_envs="${ISAAC_PLAY_NUM_ENVS:-1}"
log_path="${ISAAC_RANDOM_LOG:-/workspace/phase0/artifacts/logs/random_cartpole.log}"

printf -v quoted_task '%q' "$task"
printf -v quoted_log_path '%q' "$log_path"

remote_command="
set -euo pipefail
mkdir -p \"\$(dirname $quoted_log_path)\"
stale_pids=\"\$(ps -eo pid=,comm=,args= | awk '\$2 ~ /^python/ && (\$0 ~ /random_agent.py/ || \$0 ~ /reinforcement_learning\\/play.py/) {print \$1}')\"
if [[ -n \"\$stale_pids\" ]]; then
  kill \$stale_pids 2>/dev/null || true
fi
nohup ./isaaclab.sh -p scripts/environments/random_agent.py \
  --task=$quoted_task \
  --num_envs=$num_envs \
  --livestream 2 \
  --viz kit \
  >$quoted_log_path 2>&1 </dev/null &
printf 'random_cartpole_pid=%s\\n' \"\$!\"
printf 'log=%s\\n' $quoted_log_path
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
