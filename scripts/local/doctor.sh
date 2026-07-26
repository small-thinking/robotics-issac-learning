#!/usr/bin/env bash
set -euo pipefail

required_tools=(git gh brew brev codex)
failed=0

for tool in "${required_tools[@]}"; do
  if command -v "$tool" >/dev/null 2>&1; then
    printf '[ok] %s: %s\n' "$tool" "$(command -v "$tool")"
  else
    printf '[missing] %s\n' "$tool"
    failed=1
  fi
done

printf '\nGit repository\n'
git status --short --branch
git remote -v

printf '\nGitHub authentication\n'
if ! gh auth status; then
  failed=1
fi

printf '\nBrev version\n'
brev --version

printf '\nBrev instances\n'
if ! brev ls; then
  printf '[error] Brev authentication or network check failed\n' >&2
  failed=1
fi

exit "$failed"
