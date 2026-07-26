#!/usr/bin/env bash
set -euo pipefail

instance_name="${BREV_INSTANCE_NAME:-robotics-isaac-mvp}"
container_name="${ISAAC_CONTAINER_NAME:-vscode}"
container_user="${ISAAC_CONTAINER_USER:-ubuntu:ubuntu}"
isaaclab_dir="${ISAACLAB_DIR:-/workspace/isaaclab}"

if (( $# == 0 )); then
  printf 'Usage: %s <command>\n' "$0" >&2
  exit 2
fi

remote_command="$*"
printf -v quoted_remote_command '%q' "$remote_command"

exec brev exec "$instance_name" --host \
  "docker exec -u $container_user -w $isaaclab_dir $container_name bash -lc $quoted_remote_command"
