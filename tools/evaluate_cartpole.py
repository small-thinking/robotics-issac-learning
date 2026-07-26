#!/usr/bin/env python3
"""Evaluate CartPole policies or a checkpoint sweep with fixed seeds."""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import sys
from pathlib import Path

import gymnasium as gym
import isaaclab_tasks  # noqa: F401
import torch
from cartpole_metrics import checkpoint_vector_steps, summarize_episodes
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
) -> list[dict]:
    episodes: list[dict] = []
    device = raw_env.unwrapped.device

    for seed in seeds:
        random.seed(seed)
        torch.manual_seed(seed)
        obs, states = reset_with_seed(env, seed)
        episode_returns = torch.zeros(env.num_envs, device=device)
        episode_lengths = torch.zeros(env.num_envs, dtype=torch.int64, device=device)
        collected_for_seed = 0

        for _ in range(args_cli.max_steps_per_seed):
            with torch.inference_mode():
                if runner is None:
                    actions = 2 * torch.rand((env.num_envs, *action_shape), device=device) - 1
                else:
                    outputs = runner.agent.act(obs, states, timestep=0, timesteps=0)
                    actions = outputs[-1].get("mean_actions", outputs[0])

                obs, rewards, terminated, truncated, _ = env.step(actions)
                states = env.state()

            rewards = rewards.squeeze(-1)
            terminated = terminated.squeeze(-1)
            truncated = truncated.squeeze(-1)
            episode_returns += rewards
            episode_lengths += 1
            done = terminated | truncated

            for env_index in done.nonzero(as_tuple=False).flatten().tolist():
                if collected_for_seed >= args_cli.episodes_per_seed:
                    break
                episodes.append(
                    {
                        "seed": seed,
                        "reward": float(episode_returns[env_index].item()),
                        "length": int(episode_lengths[env_index].item()),
                        "termination_reason": (
                            "out_of_bounds" if bool(terminated[env_index].item()) else "time_limit"
                        ),
                    }
                )
                collected_for_seed += 1

            episode_returns[done] = 0
            episode_lengths[done] = 0

            if collected_for_seed >= args_cli.episodes_per_seed:
                break
        else:
            raise RuntimeError(
                f"seed {seed} did not produce {args_cli.episodes_per_seed} episodes "
                f"within {args_cli.max_steps_per_seed} steps"
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
        env = SkrlVecEnvWrapper(raw_env, ml_framework="torch")

        runner = None
        if args_cli.policy in {"trained", "sweep"}:
            experiment_cfg["trainer"]["close_environment_at_exit"] = False
            experiment_cfg["agent"]["experiment"]["write_interval"] = 0
            experiment_cfg["agent"]["experiment"]["checkpoint_interval"] = 0
            runner = Runner(env, experiment_cfg)

        if args_cli.policy == "random":
            episodes = collect_episodes(env, raw_env, None, seeds, action_shape)
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
                episodes = collect_episodes(env, raw_env, runner, seeds, action_shape)
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
                    random_episodes = collect_episodes(env, raw_env, None, seeds, action_shape)
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
