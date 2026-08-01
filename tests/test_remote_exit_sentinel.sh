#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
checker="$repo_root/scripts/brev/require_zero_exit_sentinel.sh"
fixture_dir="$(mktemp -d -t remote-exit-sentinel.XXXXXX)"
trap 'rm -rf "$fixture_dir"' EXIT

expect_failure() {
  local fixture_path="$1"
  if "$checker" "$fixture_path" PREGRASP_EXIT_CODE >/dev/null 2>&1; then
    echo "Expected sentinel validation to fail: $fixture_path" >&2
    exit 1
  fi
}

printf 'remote output\n[PREGRASP_EXIT_CODE] 0\n' >"$fixture_dir/zero.log"
"$checker" "$fixture_dir/zero.log" PREGRASP_EXIT_CODE

printf 'remote output\n[PREGRASP_EXIT_CODE] 7\n' >"$fixture_dir/nonzero.log"
expect_failure "$fixture_dir/nonzero.log"

printf 'remote output without sentinel\n' >"$fixture_dir/missing.log"
expect_failure "$fixture_dir/missing.log"

printf '[PREGRASP_EXIT_CODE] 0\n[PREGRASP_EXIT_CODE] 0\n' >"$fixture_dir/duplicate.log"
expect_failure "$fixture_dir/duplicate.log"

printf '[PREGRASP_EXIT_CODE] nope\n' >"$fixture_dir/malformed.log"
expect_failure "$fixture_dir/malformed.log"

printf '[PREGRASP_EXIT_CODE] 0\n[PREGRASP_EXIT_CODE] nope\n' >"$fixture_dir/mixed.log"
expect_failure "$fixture_dir/mixed.log"

echo "Remote exit sentinel tests passed."
