#!/usr/bin/env bash
set -euo pipefail

if ! command -v brev >/dev/null 2>&1; then
  printf 'Brev CLI is missing. Install it before continuing.\n' >&2
  exit 2
fi

brev --version

if ! brev ls >/dev/null; then
  printf 'Brev authentication check failed. Run: brev login\n' >&2
  exit 2
fi

printf 'Brev CLI is installed and authenticated.\n'
