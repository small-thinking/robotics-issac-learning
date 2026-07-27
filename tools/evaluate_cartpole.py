#!/usr/bin/env python3
"""Evaluate CartPole policies or a checkpoint sweep with fixed seeds."""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import random
import sys
from pathlib import Path

import gymnasium as gym
import isaaclab_tasks  # noqa: F401
import torch
from cartpole_metrics import (
    checkpoint_vector_steps,
    fixed_episode_env_ids,
    summarize_episodes,
)
from isaaclab_tasks.utils import (
    add_launcher_args,
    launch_simulation,
    resolve_task_config,
    setup_preset_cli,
)

with contextlib.suppress(ImportError):
    import isaaclab_tasks_experimental  # noqa: F401


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--policy", choices=("random", "trained", "sweep"), required=True)
parser.add_argument("--task", default="Isaac-Cartpole-v0")
parser.add_argument("--checkpoint", action="append", type=Path)
parser.add_argument(
    "--checkpoint-dir",
    type=Path,
    help="Evaluate every agent_<vector_step>.pt checkpoint in this directory.",
)
parser.add_argument("--training-num-envs", type=int, default=4096)
parser.add_argument(
    "--include-random-baseline",
    action="store_true",
    help="For a sweep, evaluate a uniform-random policy under the same protocol.",
)
parser.add_argument(
    "--legacy-state-preprocessor",
    action="store_true",
    help="Load checkpoints that store skrl's pre-2.1 state_preprocessor module.",
)
parser.add_argument("--seeds", default="101,202,303,404,505")
parser.add_argument("--episodes-per-seed", type=int, default=5)
parser.add_argument("--num-envs", type=int, default=64)
parser.add_argument("--max-steps-per-seed", type=int, default=1000)
parser.add_argument("--upright-threshold-degrees", type=float, default=12.0)
parser.add_argument("--robust-success-upright-fraction", type=float, default=0.95)
parser.add_argument("--action-sign-deadband", type=float, default=0.05)
parser.add_argument("--output", type=Path, required=True)
add_launcher_args(parser)
args_cli, hydra_args = setup_preset_cli(parser)
sys.argv = [sys.argv[0]] + hydra_args


def reset_with_seed(env, seed: int) -> tuple[torch.Tensor, torch.Tensor | None]:
    """Reset skrl's Isaac Lab wrapper with a new seed.

    skrl 2.1.0 intentionally exposes a one-shot reset method. Evaluation needs
    multiple fixed seeds without restarting Kit, so this refreshes the wrapper's
    cached flattened observation after an explicit underlying reset.
    """

    from skrl.utils.spaces.torch import flatten_tensorized_space, tensorize_space

    observations, info = env._env.reset(seed=seed)
    env._info = info
    env._observations = flatten_tensorized_space(
        tensorize_space(env.observation_space, observations["policy"])
    )
    states = observations.get("critic")
    if states is not None:
        env._states = flatten_tensorized_space(tensorize_space(env.state_space, states))
    return env._observations, env.state()


def resolve_checkpoints() -> list[Path]:
    checkpoints = list(args_cli.checkpoint or [])
    if args_cli.checkpoint_dir is not None:
        checkpoints.extend(args_cli.checkpoint_dir.glob("agent_*.pt"))

    unique = {path.resolve(): path.resolve() for path in checkpoints}
    return sorted(
        unique.values(),
        key=lambda path: (
            checkpoint_vector_steps(path) is None,
            checkpoint_vector_steps(path) or 0,
            path.name,
        ),
    )


def collect_episodes(
    env,
    raw_env,
    runner,
    seeds: list[int],
    action_shape: tuple[int, ...],
    control_hz: float,
    effort_scale: float,
) -> list[dict]:
    episodes: list[dict] = []
    device = raw_env.unwrapped.device

    for seed in seeds:
        random.seed(seed)
        torch.manual_seed(seed)
        obs, states = reset_with_seed(env, seed)
        episode_returns = torch.zeros(env.num_envs, device=device)
        episode_lengths = torch.zeros(env.num_envs, dtype=torch.int64, device=device)
        upright_steps = torch.zeros(env.num_envs, dtype=torch.int64, device=device)
        current_upright_steps = torch.zeros(
            env.num_envs, dtype=torch.int64, device=device
        )
        longest_upright_steps = torch.zeros(
            env.num_envs, dtype=torch.int64, device=device
        )
        pole_angle_sq_sum = torch.zeros(env.num_envs, device=device)
        cart_position_sq_sum = torch.zeros(env.num_envs, device=device)
        max_abs_cart_position = torch.zeros(env.num_envs, device=device)
        abs_cart_velocity_sum = torch.zeros(env.num_envs, device=device)
        pole_velocity_sq_sum = torch.zeros(env.num_envs, device=device)
        abs_action_sum = torch.zeros(env.num_envs, device=device)
        abs_requested_effort_sum = torch.zeros(env.num_envs, device=device)
        abs_action_delta_sum = torch.zeros(env.num_envs, device=device)
        action_delta_count = torch.zeros(env.num_envs, dtype=torch.int64, device=device)
        action_sign_changes = torch.zeros(env.num_envs, dtype=torch.int64, device=device)
        action_saturation_steps = torch.zeros(
            env.num_envs, dtype=torch.int64, device=device
        )
        previous_action = torch.zeros(env.num_envs, device=device)
        previous_nonzero_sign = torch.zeros(env.num_envs, device=device)
        has_previous_action = torch.zeros(env.num_envs, dtype=torch.bool, device=device)
        pending_env_ids = set(
            fixed_episode_env_ids(env.num_envs, args_cli.episodes_per_seed)
        )
        robot = raw_env.unwrapped.scene["robot"]
        cart_joint_id = robot.find_joints(["slider_to_cart"])[0][0]
        pole_joint_id = robot.find_joints(["cart_to_pole"])[0][0]
        upright_threshold = math.radians(args_cli.upright_threshold_degrees)

        for _ in range(args_cli.max_steps_per_seed):
            with torch.inference_mode():
                if runner is None:
                    actions = 2 * torch.rand((env.num_envs, *action_shape), device=device) - 1
                else:
                    outputs = runner.agent.act(obs, states, timestep=0, timesteps=0)
                    actions = outputs[-1].get("mean_actions", outputs[0])

                obs, rewards, terminated, truncated, _ = env.step(actions)
                states = env.state()

            scalar_action = actions.reshape(env.num_envs, -1)[:, 0]
            cart_position = robot.data.joint_pos[:, cart_joint_id]
            pole_angle_raw = robot.data.joint_pos[:, pole_joint_id]
            pole_angle = torch.atan2(torch.sin(pole_angle_raw), torch.cos(pole_angle_raw))
            cart_velocity = robot.data.joint_vel[:, cart_joint_id]
            pole_velocity = robot.data.joint_vel[:, pole_joint_id]
            upright = pole_angle.abs() <= upright_threshold
            current_upright_steps = torch.where(
                upright, current_upright_steps + 1, torch.zeros_like(current_upright_steps)
            )
            longest_upright_steps = torch.maximum(
                longest_upright_steps, current_upright_steps
            )
            upright_steps += upright
            pole_angle_sq_sum += pole_angle.square()
            cart_position_sq_sum += cart_position.square()
            max_abs_cart_position = torch.maximum(
                max_abs_cart_position, cart_position.abs()
            )
            abs_cart_velocity_sum += cart_velocity.abs()
            pole_velocity_sq_sum += pole_velocity.square()
            abs_action_sum += scalar_action.abs()
            abs_requested_effort_sum += scalar_action.abs() * effort_scale
            action_delta = (scalar_action - previous_action).abs()
            abs_action_delta_sum += torch.where(
                has_previous_action, action_delta, torch.zeros_like(action_delta)
            )
            action_delta_count += has_previous_action
            current_sign = torch.where(
                scalar_action.abs() > args_cli.action_sign_deadband,
                torch.sign(scalar_action),
                torch.zeros_like(scalar_action),
            )
            action_sign_changes += (
                (current_sign != 0)
                & (previous_nonzero_sign != 0)
                & (current_sign != previous_nonzero_sign)
            )
            previous_nonzero_sign = torch.where(
                current_sign != 0, current_sign, previous_nonzero_sign
            )
            previous_action = scalar_action
            has_previous_action.fill_(True)
            action_saturation_steps += scalar_action.abs() >= 0.999

            rewards = rewards.squeeze(-1)
            terminated = terminated.squeeze(-1)
            truncated = truncated.squeeze(-1)
            episode_returns += rewards
            episode_lengths += 1
            done = terminated | truncated

            for env_index in done.nonzero(as_tuple=False).flatten().tolist():
                if env_index not in pending_env_ids:
                    continue
                length = int(episode_lengths[env_index].item())
                action_deltas = max(1, int(action_delta_count[env_index].item()))
                termination_reason = (
                    "out_of_bounds" if bool(terminated[env_index].item()) else "time_limit"
                )
                upright_fraction = float(upright_steps[env_index].item()) / length
                episodes.append(
                    {
                        "seed": seed,
                        "reward": float(episode_returns[env_index].item()),
                        "length": length,
                        "environment_id": env_index,
                        "termination_reason": termination_reason,
                        "upright_fraction_12deg": upright_fraction,
                        "longest_upright_seconds": (
                            float(longest_upright_steps[env_index].item()) / control_hz
                        ),
                        "pole_angle_rms_radians": math.sqrt(
                            float(pole_angle_sq_sum[env_index].item()) / length
                        ),
                        "cart_position_rms": math.sqrt(
                            float(cart_position_sq_sum[env_index].item()) / length
                        ),
                        "max_abs_cart_position": float(
                            max_abs_cart_position[env_index].item()
                        ),
                        "mean_abs_cart_velocity": (
                            float(abs_cart_velocity_sum[env_index].item()) / length
                        ),
                        "pole_angular_velocity_rms": math.sqrt(
                            float(pole_velocity_sq_sum[env_index].item()) / length
                        ),
                        "mean_abs_normalized_action": (
                            float(abs_action_sum[env_index].item()) / length
                        ),
                        "mean_abs_requested_effort": (
                            float(abs_requested_effort_sum[env_index].item()) / length
                        ),
                        "mean_abs_action_delta": (
                            float(abs_action_delta_sum[env_index].item()) / action_deltas
                        ),
                        "action_total_variation": float(
                            abs_action_delta_sum[env_index].item()
                        ),
                        "action_sign_changes_per_second": (
                            float(action_sign_changes[env_index].item())
                            / (length / control_hz)
                        ),
                        "action_saturation_fraction": (
                            float(action_saturation_steps[env_index].item()) / length
                        ),
                        "robust_success": (
                            termination_reason == "time_limit"
                            and upright_fraction
                            >= args_cli.robust_success_upright_fraction
                        ),
                    }
                )
                pending_env_ids.remove(env_index)

            episode_returns[done] = 0
            episode_lengths[done] = 0
            upright_steps[done] = 0
            current_upright_steps[done] = 0
            longest_upright_steps[done] = 0
            pole_angle_sq_sum[done] = 0
            cart_position_sq_sum[done] = 0
            max_abs_cart_position[done] = 0
            abs_cart_velocity_sum[done] = 0
            pole_velocity_sq_sum[done] = 0
            abs_action_sum[done] = 0
            abs_requested_effort_sum[done] = 0
            abs_action_delta_sum[done] = 0
            action_delta_count[done] = 0
            action_sign_changes[done] = 0
            action_saturation_steps[done] = 0
            previous_action[done] = 0
            previous_nonzero_sign[done] = 0
            has_previous_action[done] = False

            if not pending_env_ids:
                break
        else:
            raise RuntimeError(
                f"seed {seed} did not produce {args_cli.episodes_per_seed} episodes "
                f"within {args_cli.max_steps_per_seed} steps; "
                f"unfinished fixed environment IDs: {sorted(pending_env_ids)}"
            )

    return episodes


def main() -> None:
    checkpoints = resolve_checkpoints()
    if args_cli.policy == "trained" and len(checkpoints) != 1:
        parser.error("exactly one --checkpoint is required for --policy=trained")
    if args_cli.policy == "sweep":
        if not checkpoints:
            parser.error(
                "--checkpoint-dir or at least one --checkpoint is required for --policy=sweep"
            )
        if any(checkpoint_vector_steps(path) is None for path in checkpoints):
            parser.error("sweep checkpoints must use agent_<vector_step>.pt filenames")
    if args_cli.episodes_per_seed <= 0:
        parser.error("--episodes-per-seed must be positive")
    if args_cli.training_num_envs <= 0:
        parser.error("--training-num-envs must be positive")
    if args_cli.num_envs < args_cli.episodes_per_seed:
        parser.error("--num-envs must be at least --episodes-per-seed")

    seeds = [int(seed.strip()) for seed in args_cli.seeds.split(",") if seed.strip()]
    env_cfg, experiment_cfg = resolve_task_config(args_cli.task, "skrl_cfg_entry_point")
    env_cfg.scene.num_envs = args_cli.num_envs
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device
    control_hz = 1.0 / (env_cfg.sim.dt * env_cfg.decimation)

    with launch_simulation(env_cfg, args_cli):
        from isaaclab_rl.skrl import SkrlVecEnvWrapper
        from skrl.utils.runner.torch import Runner

        raw_env = gym.make(args_cli.task, cfg=env_cfg)
        action_shape = raw_env.unwrapped.single_action_space.shape
        effort_scale = float(env_cfg.actions.joint_effort.scale)
        env = SkrlVecEnvWrapper(raw_env, ml_framework="torch")

        runner = None
        if args_cli.policy in {"trained", "sweep"}:
            experiment_cfg["trainer"]["close_environment_at_exit"] = False
            experiment_cfg["agent"]["experiment"]["write_interval"] = 0
            experiment_cfg["agent"]["experiment"]["checkpoint_interval"] = 0
            runner = Runner(env, experiment_cfg)

        if args_cli.policy == "random":
            episodes = collect_episodes(
                env,
                raw_env,
                None,
                seeds,
                action_shape,
                control_hz,
                effort_scale,
            )
            result = summarize_episodes(
                policy="random",
                task=args_cli.task,
                checkpoint=None,
                seeds=seeds,
                episodes=episodes,
                control_hz=control_hz,
            )
        else:
            evaluations = []
            for checkpoint in checkpoints:
                runner.agent.load(str(checkpoint))
                if args_cli.legacy_state_preprocessor:
                    checkpoint_data = torch.load(
                        checkpoint, map_location="cpu", weights_only=False
                    )
                    runner.agent._observation_preprocessor.load_state_dict(
                        checkpoint_data["state_preprocessor"]
                    )
                runner.agent.enable_training_mode(False, apply_to_models=True)
                episodes = collect_episodes(
                    env,
                    raw_env,
                    runner,
                    seeds,
                    action_shape,
                    control_hz,
                    effort_scale,
                )
                evaluations.append(
                    summarize_episodes(
                        policy="trained",
                        task=args_cli.task,
                        checkpoint=checkpoint,
                        seeds=seeds,
                        episodes=episodes,
                        control_hz=control_hz,
                        training_num_envs=args_cli.training_num_envs,
                    )
                )

            if args_cli.policy == "trained":
                result = evaluations[0]
            else:
                random_baseline = None
                if args_cli.include_random_baseline:
                    random_episodes = collect_episodes(
                        env,
                        raw_env,
                        None,
                        seeds,
                        action_shape,
                        control_hz,
                        effort_scale,
                    )
                    random_baseline = summarize_episodes(
                        policy="random",
                        task=args_cli.task,
                        checkpoint=None,
                        seeds=seeds,
                        episodes=random_episodes,
                        control_hz=control_hz,
                    )
                result = {
                    "artifact_type": "checkpoint_learning_curve",
                    "schema_version": 1,
                    "task": args_cli.task,
                    "seeds": seeds,
                    "episodes_per_seed": args_cli.episodes_per_seed,
                    "control_hz": control_hz,
                    "episode_limit_seconds": env_cfg.episode_length_s,
                    "training_num_envs": args_cli.training_num_envs,
                    "random_baseline": random_baseline,
                    "evaluations": evaluations,
                }

        args_cli.output.parent.mkdir(parents=True, exist_ok=True)
        args_cli.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        if args_cli.policy == "sweep":
            printable = {
                **result,
                "random_baseline": (
                    {
                        key: value
                        for key, value in result["random_baseline"].items()
                        if key != "episodes"
                    }
                    if result["random_baseline"]
                    else None
                ),
                "evaluations": [
                    {key: value for key, value in evaluation.items() if key != "episodes"}
                    for evaluation in result["evaluations"]
                ],
            }
        else:
            printable = {key: value for key, value in result.items() if key != "episodes"}
        print(json.dumps(printable, indent=2))
        env.close()


if __name__ == "__main__":
    main()
