#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "Usage: $0 LOG_PATH SENTINEL_NAME" >&2
  exit 2
fi

log_path="$1"
sentinel_name="$2"

if [[ ! -f "$log_path" ]]; then
  echo "Remote execution log does not exist: $log_path" >&2
  exit 1
fi

if [[ ! "$sentinel_name" =~ ^[A-Z][A-Z0-9_]*$ ]]; then
  echo "Invalid sentinel name: $sentinel_name" >&2
  exit 2
fi

candidate_pattern="^\\[$sentinel_name\\]"
sentinel_pattern="^\\[$sentinel_name\\] [0-9]+$"
sentinel_count="$(grep -Ec "$candidate_pattern" "$log_path" || true)"

if [[ "$sentinel_count" -ne 1 ]]; then
  echo "Expected exactly one [$sentinel_name] exit sentinel; found $sentinel_count." >&2
  exit 1
fi

if ! grep -Eq "$sentinel_pattern" "$log_path"; then
  echo "Malformed [$sentinel_name] exit sentinel." >&2
  exit 1
fi

if grep -Fqx "[$sentinel_name] 0" "$log_path"; then
  exit 0
fi

sentinel_line="$(grep -E "$sentinel_pattern" "$log_path")"
echo "Remote command reported failure: $sentinel_line" >&2
exit 1
