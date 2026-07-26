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

if [[ "${REMOTE_TRACE:-0}" == "1" ]]; then
  remote_command=$'set -x\n'"$remote_command"
fi

printf -v quoted_remote_command '%q' "$remote_command"
host_command="docker exec -u $container_user -w $isaaclab_dir $container_name bash -lc $quoted_remote_command"

timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
printf -v rendered_local_command 'brev exec %q --host %q' "$instance_name" "$host_command"

command_display="$(
  printf '=== Remote command %s ===\n' "$timestamp"
  printf '[local -> VM]\n$ %s\n\n' "$rendered_local_command"
  printf '[Isaac container: %s, cwd: %s, user: %s]\n' \
    "$container_name" "$isaaclab_dir" "$container_user"
  printf '$ %s\n' "$remote_command"
  printf '=== End command ===\n'
)"

printf '%s\n' "$command_display"

if [[ -n "${REMOTE_COMMAND_LOG:-}" ]]; then
  mkdir -p "$(dirname "$REMOTE_COMMAND_LOG")"
  printf '%s\n\n' "$command_display" >>"$REMOTE_COMMAND_LOG"
  printf '[transcript] %s\n' "$REMOTE_COMMAND_LOG"
fi

if [[ "${REMOTE_DRY_RUN:-0}" == "1" ]]; then
  printf '[dry-run] Command displayed but not executed.\n'
  exit 0
fi

exec brev exec "$instance_name" --host \
  "$host_command"
