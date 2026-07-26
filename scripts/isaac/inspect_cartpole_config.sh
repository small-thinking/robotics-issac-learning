#!/usr/bin/env bash
set -euo pipefail

task="${ISAAC_TASK:-Isaac-Cartpole-v0}"
config_path="${ISAAC_SKRL_CONFIG_PATH:-source/isaaclab_tasks/isaaclab_tasks/manager_based/classic/cartpole/agents/skrl_ppo_cfg.yaml}"
registration_path="${ISAAC_TASK_REGISTRATION_PATH:-source/isaaclab_tasks/isaaclab_tasks/manager_based/classic/cartpole/__init__.py}"

printf -v quoted_task '%q' "$task"
printf -v quoted_config_path '%q' "$config_path"
printf -v quoted_registration_path '%q' "$registration_path"

remote_command="
set -euo pipefail
printf 'task=%s\\n' $quoted_task
printf 'isaaclab_commit=%s\\n' \"\$(git rev-parse HEAD)\"
printf 'config_path=%s\\n' $quoted_config_path
printf 'config_sha256=%s\\n' \"\$(sha256sum $quoted_config_path | awk '{print \$1}')\"
printf '%s\\n' '--- task registration ---'
sed -n '1,220p' $quoted_registration_path
printf '%s\\n' '--- resolved source config ---'
sed -n '1,260p' $quoted_config_path
"

exec "$(dirname "$0")/../brev/remote_exec.sh" "$remote_command"
