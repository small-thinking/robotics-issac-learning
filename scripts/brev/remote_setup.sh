#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="${REMOTE_PROJECT_DIR:-/workspace/robotics-issac-learning}"
isaaclab_dir="${ISAACLAB_DIR:-/workspace/isaaclab}"

"$script_dir/sync.sh"

printf -v quoted_project_dir '%q' "$project_dir"
printf -v quoted_isaaclab_dir '%q' "$isaaclab_dir"
remote_command="
set -euo pipefail
mkdir -p $quoted_project_dir/artifacts/environment
mkdir -p $quoted_project_dir/artifacts/logs
mkdir -p $quoted_project_dir/artifacts/evaluations
cd $quoted_isaaclab_dir
./isaaclab.sh -p $quoted_project_dir/tools/collect_environment_info.py \
  --output $quoted_project_dir/artifacts/environment/container.json
"

exec "$script_dir/remote_exec.sh" "$remote_command"
