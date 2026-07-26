#!/usr/bin/env bash
set -euo pipefail

# Phase 0 cost-conscious target:
# one AWS L4, at least 64 GiB RAM, stoppable, and configurable ports.
exec brev search gpu \
  --gpu-name L4 \
  --provider aws \
  --min-ram 64 \
  --min-disk 256 \
  --stoppable \
  --flex-ports \
  --sort price \
  --wide
