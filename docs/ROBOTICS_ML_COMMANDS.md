# Transferable Robotics-ML Commands

This is the learning-oriented command record. It intentionally omits Brev,
Docker, repository sync, secure-link, and cloud lifecycle plumbing.

The syntax below is Isaac Lab-specific, but the workflow transfers to other
simulators and real-robot systems:

```text
inspect MDP -> random baseline -> train -> select checkpoint
            -> fixed-seed evaluation -> play and diagnose
```

## 1. Inspect the task contract

Before training, identify the observation, action, reward, termination, episode
horizon, control frequency, and agent configuration.

```bash
./isaaclab.sh -p scripts/environments/list_envs.py --keyword Cartpole
```

Phase 1 then prints the exact registered task and PPO YAML with:

```bash
make inspect-config
```

Transferable question: *What MDP and optimization contract is this checkpoint
supposed to solve?*

## 2. Establish a random baseline

```bash
./isaaclab.sh -p scripts/environments/random_agent.py \
  --task=Isaac-Cartpole-v0 \
  --num_envs=1
```

The random policy validates reset, observation, action, reward, termination,
and rendering plumbing. It also supplies a minimum behavioral baseline.

Transferable question: *Does the environment behave sensibly before learning?*

## 3. Train PPO from scratch

```bash
./isaaclab.sh -p scripts/reinforcement_learning/train.py \
  --rl_library=skrl \
  --task=Isaac-Cartpole-v0 \
  --algorithm=PPO \
  --seed=42 \
  --num_envs=4096 \
  --viz none
```

Important semantics:

- `--task` selects the complete MDP contract, not merely a scene name.
- `--seed` identifies training stochasticity and checkpoint provenance.
- `--num_envs=4096` means 4096 simulator states sharing one policy.
- `--viz none` removes rendering work during training.
- no resume/checkpoint argument means the model starts from scratch.
- no horizon override means the installed official task config controls PPO.

Transferable question: *Can the canonical algorithm reproduce a known baseline
without changing multiple variables at once?*

## 4. Select a checkpoint by provenance and evaluation

```bash
find logs/skrl/cartpole -type f -name '*.pt' -print
```

Do not select a checkpoint only because it is newest or because its training
reward looks high. Record:

- training task and seed;
- Git commit and resolved config;
- whether it is fresh, resumed, or pretrained;
- independent evaluation result.

Transferable question: *Exactly which policy am I evaluating, and how was it
produced?*

## 5. Run fixed-seed evaluation

```bash
./isaaclab.sh -p \
  /workspace/robotics-issac-learning/tools/evaluate_cartpole.py \
  --policy=trained \
  --task=Isaac-Cartpole-v0 \
  --checkpoint=/absolute/path/to/local_checkpoint.pt \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=64 \
  --output=/workspace/robotics-issac-learning/artifacts/evaluations/trained_policy.json \
  --viz none
```

Compare against a random policy on the same task, seeds, episode count, and
termination definitions.

Transferable question: *Does behavior improve under a controlled evaluation
contract rather than only in the training log?*

## 6. Evaluate the learning curve

Evaluate every numbered checkpoint under the same fixed seeds:

```bash
./isaaclab.sh -p \
  /workspace/robotics-issac-learning/tools/evaluate_cartpole.py \
  --policy=sweep \
  --task=Isaac-Cartpole-v0 \
  --checkpoint-dir=logs/skrl/cartpole/<run>/checkpoints \
  --training-num-envs=4096 \
  --include-random-baseline \
  --seeds=101,202,303,404,505 \
  --episodes-per-seed=5 \
  --num-envs=64 \
  --output=/workspace/robotics-issac-learning/artifacts/evaluations/phase1_learning_curve.json \
  --viz none
```

The curve reports mean balance seconds and time-limit success against collected
training transitions. It is more trustworthy than connecting trainer-console
metrics because every checkpoint sees the same evaluation contract.

Transferable question: *How much independent behavioral improvement did each
additional unit of training data buy?*

## 7. Play the evaluated policy

```bash
./isaaclab.sh -p scripts/reinforcement_learning/play.py \
  --rl_library=skrl \
  --task=Isaac-Cartpole-v0 \
  --algorithm=PPO \
  --num_envs=1 \
  --checkpoint=/absolute/path/to/local_checkpoint.pt \
  --viz kit
```

Visual inspection checks corrective actions, resets, oscillation, saturation,
and failure modes that one aggregate score may hide.

Transferable question: *How does the policy fail, and what data, reward, model,
or evaluation change should that failure motivate?*

## Phase 1 acceptance

The locally trained policy passes when all of these hold:

- mean episode length is at least 250;
- at least 20/25 episodes reach the time limit;
- mean reward is positive;
- checkpoint provenance is `local_trained`;
- stable corrective behavior is visually confirmed.

## Phase 1 worked result

The first clean run of this workflow needed no tuning:

- seed: `42`
- parallel environments: `4096`
- vector steps: `2400`
- collected transitions: `9,830,400`
- wall-clock training time on one L4: `68.43` seconds
- fixed-seed mean episode length: `269.44`
- time-limit episodes: `22/25`
- official-checkpoint comparison: `268.88` mean length and `22/25`
  time-limit episodes

The useful lesson is not that these numbers transfer to every robot. The
transferable part is the experimental sequence: lock one task/config contract,
train without hidden resume state, evaluate the exact checkpoint under fixed
seeds, and only then use visual behavior to diagnose what metrics conceal.
