#!/usr/bin/env bash
set -euo pipefail

instance_name="${BREV_INSTANCE_NAME:-robotics-isaac-mvp}"

if ! brev ls | awk 'NR > 1 {print $1}' | grep -Fxq "$instance_name"; then
  printf 'Instance not found: %s\n' "$instance_name" >&2
  exit 2
fi

printf 'Stopping instance without deleting storage: %s\n' "$instance_name"
exec brev stop "$instance_name"
