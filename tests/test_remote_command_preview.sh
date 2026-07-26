#!/usr/bin/env bash
set -euo pipefail

train_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/train_cartpole.sh
)"

[[ "$train_output" == *'[local -> VM]'* ]]
[[ "$train_output" == *'[Isaac container: vscode'* ]]
[[ "$train_output" == *'--task=Isaac-Cartpole-v0'* ]]
[[ "$train_output" == *'--num_envs=4096'* ]]
[[ "$train_output" == *'[dry-run] Command displayed but not executed.'* ]]

eval_output="$(
  BREV_INSTANCE_NAME=preview-only \
  ISAAC_CHECKPOINT=/tmp/preview-checkpoint.pt \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/eval_cartpole.sh
)"

[[ "$eval_output" == *'--policy=random'* ]]
[[ "$eval_output" == *'--policy=trained'* ]]
[[ "$eval_output" == *'--checkpoint=/tmp/preview-checkpoint.pt'* ]]
[[ "$eval_output" == *'[dry-run] Command displayed but not executed.'* ]]

printf 'remote command preview tests passed\n'
