#!/usr/bin/env bash
set -euo pipefail

assert_contains() {
  local output="$1"
  local expected="$2"
  if [[ "$output" != *"$expected"* ]]; then
    printf 'expected remote preview to contain: %s\n' "$expected" >&2
    exit 1
  fi
}

assert_not_contains() {
  local output="$1"
  local unexpected="$2"
  if [[ "$output" == *"$unexpected"* ]]; then
    printf 'expected remote preview not to contain: %s\n' "$unexpected" >&2
    exit 1
  fi
}

train_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/train_cartpole.sh
)"

assert_contains "$train_output" '[local -> VM]'
assert_contains "$train_output" '[Isaac container: vscode'
assert_contains "$train_output" '--task=Isaac-Cartpole-v0'
assert_contains "$train_output" '--num_envs=4096'
assert_contains "$train_output" '[dry-run] Command displayed but not executed.'

eval_output="$(
  BREV_INSTANCE_NAME=preview-only \
  ISAAC_CHECKPOINT=/tmp/preview-checkpoint.pt \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/eval_cartpole.sh
)"

assert_contains "$eval_output" '--policy=random'
assert_contains "$eval_output" '--policy=trained'
assert_contains "$eval_output" '--checkpoint=/tmp/preview-checkpoint.pt'
assert_contains "$eval_output" '--num-envs=5'
assert_contains "$eval_output" '[dry-run] Command displayed but not executed.'

variant_train_output="$(
  BREV_INSTANCE_NAME=preview-only \
  ISAAC_VARIANT=A_E50 \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/train_cartpole.sh
)"

assert_contains "$variant_train_output" 'env.actions.joint_effort.scale=50.0'

variant_eval_output="$(
  BREV_INSTANCE_NAME=preview-only \
  ISAAC_CHECKPOINT=/tmp/preview-checkpoint.pt \
  ISAAC_VARIANT=R_CV0 \
  ISAAC_EVAL_PROFILE=stress30 \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/eval_cartpole.sh
)"

assert_contains "$variant_eval_output" '--max-steps-per-seed=3600'
assert_contains "$variant_eval_output" 'env.episode_length_s=30.0'
assert_not_contains "$variant_eval_output" 'env.rewards.cart_vel.weight=0.0'

curve_output="$(
  BREV_INSTANCE_NAME=preview-only \
  ISAAC_CHECKPOINT_DIR=/tmp/cartpole/checkpoints \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/eval_learning_curve.sh
)"

assert_contains "$curve_output" '--policy=sweep'
assert_contains "$curve_output" '--checkpoint-dir=/tmp/cartpole/checkpoints'
assert_contains "$curve_output" '--include-random-baseline'
assert_contains "$curve_output" 'phase1_learning_curve.json'
assert_contains "$curve_output" 'phase1_learning_curve.svg'
assert_contains "$curve_output" '[dry-run] Command displayed but not executed.'

dofbot_inspect_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/inspect_dofbot_asset.sh
)"

assert_contains "$dofbot_inspect_output" 'inspect_dofbot_asset.py'
assert_contains "$dofbot_inspect_output" 'asset_contract.json'
assert_contains "$dofbot_inspect_output" '--max-steps 120'
assert_contains "$dofbot_inspect_output" '--headless'
assert_contains "$dofbot_inspect_output" '[dry-run] Command displayed but not executed.'

dofbot_view_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/view_dofbot_asset.sh
)"

assert_contains "$dofbot_view_output" 'inspect_dofbot_asset.py'
assert_contains "$dofbot_view_output" '--max-steps -1'
assert_contains "$dofbot_view_output" '--livestream 2'
assert_contains "$dofbot_view_output" '--viz kit'
assert_contains "$dofbot_view_output" '[dry-run] Command displayed but not executed.'

dofbot_motion_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/run_dofbot_motion.sh
)"

assert_contains "$dofbot_motion_output" 'move_dofbot_joints.py'
assert_contains "$dofbot_motion_output" 'asset_contract.json'
assert_contains "$dofbot_motion_output" 'motion_contract.json'
assert_contains "$dofbot_motion_output" '--cycles 1'
assert_contains "$dofbot_motion_output" '--pre-motion-hold-seconds 2'
assert_contains "$dofbot_motion_output" '--sample-hz 10'
assert_contains "$dofbot_motion_output" '--git-commit "$git_commit"'
assert_contains "$dofbot_motion_output" '--headless'
assert_contains "$dofbot_motion_output" '[dry-run] Command displayed but not executed.'

dofbot_motion_view_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/view_dofbot_motion.sh
)"

assert_contains "$dofbot_motion_view_output" 'move_dofbot_joints.py'
assert_contains "$dofbot_motion_view_output" 'motion_viewer_contract.json'
assert_contains "$dofbot_motion_view_output" 'motion_viewer.log'
assert_contains "$dofbot_motion_view_output" '--cycles -1'
assert_contains "$dofbot_motion_view_output" '--pre-motion-hold-seconds 30'
assert_contains "$dofbot_motion_view_output" '--livestream 2'
assert_contains "$dofbot_motion_view_output" '--viz kit'
assert_contains "$dofbot_motion_view_output" 'motion repeats until the process or instance is stopped'
assert_contains "$dofbot_motion_view_output" '[dry-run] Command displayed but not executed.'

dofbot_motion_config_output="$(
  BREV_INSTANCE_NAME=preview-only \
  MOTION=configs/dofbot/motions/safe_api_wave.json \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/run_dofbot_motion_config.sh
)"

assert_contains "$dofbot_motion_config_output" 'run_dofbot_motion_config.py'
assert_contains "$dofbot_motion_config_output" '/workspace/robotics-issac-learning/configs/dofbot/motions/safe_api_wave.json'
assert_contains "$dofbot_motion_config_output" 'motion_config_contract.json'
assert_contains "$dofbot_motion_config_output" '--cycles 1'
assert_contains "$dofbot_motion_config_output" '--viewer-connection-hold-seconds 0'
assert_contains "$dofbot_motion_config_output" '--device cpu'
assert_contains "$dofbot_motion_config_output" '--headless'
assert_contains "$dofbot_motion_config_output" '[dry-run] Command displayed but not executed.'

dofbot_motion_config_view_output="$(
  BREV_INSTANCE_NAME=preview-only \
  MOTION=configs/dofbot/motions/safe_api_wave.json \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/view_dofbot_motion_config.sh
)"

assert_contains "$dofbot_motion_config_view_output" 'run_dofbot_motion_config.py'
assert_contains "$dofbot_motion_config_view_output" 'motion_config_viewer_contract.json'
assert_contains "$dofbot_motion_config_view_output" 'motion_config_viewer.log'
assert_contains "$dofbot_motion_config_view_output" '--cycles -1'
assert_contains "$dofbot_motion_config_view_output" '--viewer-connection-hold-seconds 30'
assert_contains "$dofbot_motion_config_view_output" '--livestream 2'
assert_contains "$dofbot_motion_config_view_output" '--viz kit'
assert_contains "$dofbot_motion_config_view_output" 'configured motion repeats until the process or instance is stopped'
assert_contains "$dofbot_motion_config_view_output" '[dry-run] Command displayed but not executed.'

dofbot_camera_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/capture_dofbot_camera.sh
)"

assert_contains "$dofbot_camera_output" 'capture_dofbot_camera.py'
assert_contains "$dofbot_camera_output" 'goal3_onboard_rgb.json'
assert_contains "$dofbot_camera_output" 'camera_contract.json'
assert_contains "$dofbot_camera_output" 'camera_rgb.png'
assert_contains "$dofbot_camera_output" '--enable_cameras'
assert_contains "$dofbot_camera_output" '--headless'
assert_not_contains "$dofbot_camera_output" '--keep-alive'
assert_contains "$dofbot_camera_output" '[dry-run] Command displayed but not executed.'

dofbot_camera_view_output="$(
  BREV_INSTANCE_NAME=preview-only \
  REMOTE_DRY_RUN=1 \
  ./scripts/isaac/view_dofbot_camera.sh
)"

assert_contains "$dofbot_camera_view_output" 'capture_dofbot_camera.py'
assert_contains "$dofbot_camera_view_output" 'camera_viewer_contract.json'
assert_contains "$dofbot_camera_view_output" 'camera_viewer_rgb.png'
assert_contains "$dofbot_camera_view_output" '--keep-alive'
assert_contains "$dofbot_camera_view_output" '--enable_cameras'
assert_contains "$dofbot_camera_view_output" '--livestream 2'
assert_contains "$dofbot_camera_view_output" '--viz kit'
assert_contains "$dofbot_camera_view_output" 'Viewer uses the onboard camera and stays static until stopped'
assert_contains "$dofbot_camera_view_output" '[dry-run] Command displayed but not executed.'

printf 'remote command preview tests passed\n'
