#!/usr/bin/env python3
"""Evaluate random or trained CartPole policies with fixed seeds."""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

import gymnasium as gym
import skrl
import torch

import isaaclab_tasks  # noqa: F401
from isaaclab_tasks.utils import add_launcher_args, launch_simulation, resolve_task_config, setup_preset_cli

with contextlib.suppress(ImportError):
    import isaaclab_tasks_experimental  # noqa: F401


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--policy", choices=("random", "trained"), required=True)
parser.add_argument("--task", default="Isaac-Cartpole-v0")
parser.add_argument("--checkpoint", type=Path)
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


def summarize(policy: str, task: str, checkpoint: Path | None, seeds: list[int], episodes: list[dict]) -> dict:
    rewards = [float(episode["reward"]) for episode in episodes]
    lengths = [float(episode["length"]) for episode in episodes]
    reasons = Counter(episode["termination_reason"] for episode in episodes)
    return {
        "policy": policy,
        "task": task,
        "checkpoint": str(checkpoint.resolve()) if checkpoint else None,
        "episode_count": len(episodes),
        "seeds": seeds,
        "mean_episode_reward": statistics.fmean(rewards),
        "std_episode_reward": statistics.pstdev(rewards),
        "mean_episode_length": statistics.fmean(lengths),
        "std_episode_length": statistics.pstdev(lengths),
        "termination_reason_counts": dict(sorted(reasons.items())),
        "episodes": episodes,
    }


def main() -> None:
    if args_cli.policy == "trained" and args_cli.checkpoint is None:
        parser.error("--checkpoint is required for --policy=trained")
    if args_cli.episodes_per_seed <= 0:
        parser.error("--episodes-per-seed must be positive")

    seeds = [int(seed.strip()) for seed in args_cli.seeds.split(",") if seed.strip()]
    env_cfg, experiment_cfg = resolve_task_config(args_cli.task, "skrl_cfg_entry_point")
    env_cfg.scene.num_envs = args_cli.num_envs
    env_cfg.sim.device = args_cli.device if args_cli.device is not None else env_cfg.sim.device

    with launch_simulation(env_cfg, args_cli):
        from isaaclab_rl.skrl import SkrlVecEnvWrapper
        from skrl.utils.runner.torch import Runner

        raw_env = gym.make(args_cli.task, cfg=env_cfg)
        action_shape = raw_env.unwrapped.single_action_space.shape
        env = SkrlVecEnvWrapper(raw_env, ml_framework="torch")

        runner = None
        if args_cli.policy == "trained":
            experiment_cfg["trainer"]["close_environment_at_exit"] = False
            experiment_cfg["agent"]["experiment"]["write_interval"] = 0
            experiment_cfg["agent"]["experiment"]["checkpoint_interval"] = 0
            runner = Runner(env, experiment_cfg)
            runner.agent.load(str(args_cli.checkpoint.resolve()))
            if args_cli.legacy_state_preprocessor:
                checkpoint_data = torch.load(
                    args_cli.checkpoint.resolve(), map_location="cpu", weights_only=False
                )
                runner.agent._observation_preprocessor.load_state_dict(
                    checkpoint_data["state_preprocessor"]
                )
            runner.agent.enable_training_mode(False, apply_to_models=True)

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

        result = summarize(args_cli.policy, args_cli.task, args_cli.checkpoint, seeds, episodes)
        args_cli.output.parent.mkdir(parents=True, exist_ok=True)
        args_cli.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({key: value for key, value in result.items() if key != "episodes"}, indent=2))
        env.close()


if __name__ == "__main__":
    main()
