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
[[ "$eval_output" == *'--num-envs=5'* ]]
[[ "$eval_output" == *'[dry-run] Command displayed but not executed.'* ]]

variant_train_output="$(
  BREV_INSTANCE_NAME=preview-only \
  ISAAC_VARIANT=A_E50 \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/train_cartpole.sh
)"

[[ "$variant_train_output" == *'env.actions.joint_effort.scale=50.0'* ]]

variant_eval_output="$(
  BREV_INSTANCE_NAME=preview-only \
  ISAAC_CHECKPOINT=/tmp/preview-checkpoint.pt \
  ISAAC_VARIANT=R_CV0 \
  ISAAC_EVAL_PROFILE=stress30 \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/eval_cartpole.sh
)"

[[ "$variant_eval_output" == *'--max-steps-per-seed=3600'* ]]
[[ "$variant_eval_output" == *'env.episode_length_s=30.0'* ]]
[[ "$variant_eval_output" != *'env.rewards.cart_vel.weight=0.0'* ]]

curve_output="$(
  BREV_INSTANCE_NAME=preview-only \
  ISAAC_CHECKPOINT_DIR=/tmp/cartpole/checkpoints \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/eval_learning_curve.sh
)"

[[ "$curve_output" == *'--policy=sweep'* ]]
[[ "$curve_output" == *'--checkpoint-dir=/tmp/cartpole/checkpoints'* ]]
[[ "$curve_output" == *'--include-random-baseline'* ]]
[[ "$curve_output" == *'phase1_learning_curve.json'* ]]
[[ "$curve_output" == *'phase1_learning_curve.svg'* ]]
[[ "$curve_output" == *'[dry-run] Command displayed but not executed.'* ]]

dofbot_inspect_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/inspect_dofbot_asset.sh
)"

[[ "$dofbot_inspect_output" == *'inspect_dofbot_asset.py'* ]]
[[ "$dofbot_inspect_output" == *'asset_contract.json'* ]]
[[ "$dofbot_inspect_output" == *'--max-steps 120'* ]]
[[ "$dofbot_inspect_output" == *'--headless'* ]]
[[ "$dofbot_inspect_output" == *'[dry-run] Command displayed but not executed.'* ]]

dofbot_view_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/view_dofbot_asset.sh
)"

[[ "$dofbot_view_output" == *'inspect_dofbot_asset.py'* ]]
[[ "$dofbot_view_output" == *'--max-steps -1'* ]]
[[ "$dofbot_view_output" == *'--livestream 2'* ]]
[[ "$dofbot_view_output" == *'--viz kit'* ]]
[[ "$dofbot_view_output" == *'[dry-run] Command displayed but not executed.'* ]]

dofbot_motion_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/run_dofbot_motion.sh
)"

[[ "$dofbot_motion_output" == *'move_dofbot_joints.py'* ]]
[[ "$dofbot_motion_output" == *'asset_contract.json'* ]]
[[ "$dofbot_motion_output" == *'motion_contract.json'* ]]
[[ "$dofbot_motion_output" == *'--cycles 1'* ]]
[[ "$dofbot_motion_output" == *'--pre-motion-hold-seconds 2'* ]]
[[ "$dofbot_motion_output" == *'--sample-hz 10'* ]]
[[ "$dofbot_motion_output" == *'--git-commit "$git_commit"'* ]]
[[ "$dofbot_motion_output" == *'--headless'* ]]
[[ "$dofbot_motion_output" == *'[dry-run] Command displayed but not executed.'* ]]

dofbot_motion_view_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/view_dofbot_motion.sh
)"

[[ "$dofbot_motion_view_output" == *'move_dofbot_joints.py'* ]]
[[ "$dofbot_motion_view_output" == *'motion_viewer_contract.json'* ]]
[[ "$dofbot_motion_view_output" == *'motion_viewer.log'* ]]
[[ "$dofbot_motion_view_output" == *'--cycles -1'* ]]
[[ "$dofbot_motion_view_output" == *'--pre-motion-hold-seconds 30'* ]]
[[ "$dofbot_motion_view_output" == *'--livestream 2'* ]]
[[ "$dofbot_motion_view_output" == *'--viz kit'* ]]
[[ "$dofbot_motion_view_output" == *'motion repeats until the process or instance is stopped'* ]]
[[ "$dofbot_motion_view_output" == *'[dry-run] Command displayed but not executed.'* ]]

printf 'remote command preview tests passed\n'
