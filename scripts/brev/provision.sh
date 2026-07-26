#!/usr/bin/env bash
set -euo pipefail

instance_name="${BREV_INSTANCE_NAME:-robotics-isaac-mvp}"
launchable_id="${BREV_LAUNCHABLE_ID:-env-35JP2ywERLgqtD0b0MIeK1HnF46}"
instance_type="${BREV_INSTANCE_TYPE:-g6.4xlarge}"

if [[ "${BREV_COST_APPROVED:-}" != "YES" ]]; then
  printf 'Refusing to provision: set BREV_COST_APPROVED=YES only after explicit user approval.\n' >&2
  exit 2
fi

if [[ -z "${BREV_REGION_CONFIRMED:-}" ]]; then
  printf 'Refusing to provision: set BREV_REGION_CONFIRMED after verifying the deployment region.\n' >&2
  exit 2
fi

if [[ "$instance_type" != "g6.4xlarge" ]]; then
  printf 'Refusing unreviewed Phase 0 instance type: %s\n' "$instance_type" >&2
  exit 2
fi

if brev ls | awk 'NR > 1 {print $1}' | grep -Fxq "$instance_name"; then
  printf 'Refusing to create duplicate instance: %s\n' "$instance_name" >&2
  exit 2
fi

printf 'Creating one approved instance: %s (%s, region confirmation: %s)\n' \
  "$instance_name" "$instance_type" "$BREV_REGION_CONFIRMED"

exec brev create "$instance_name" \
  --launchable "$launchable_id" \
  --type "$instance_type"
