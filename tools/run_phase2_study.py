#!/usr/bin/env python3
"""Run the preregistered Phase 2 CartPole study with resumable manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .cartpole_variants import (
        build_planned_manifest,
        build_run_matrix,
        canonical_sha256,
        hydra_tokens,
        load_registry,
    )
except ImportError:
    from cartpole_variants import (  # type: ignore[no-redef]
        build_planned_manifest,
        build_run_matrix,
        canonical_sha256,
        hydra_tokens,
        load_registry,
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


class StudyRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.registry = load_registry(args.registry)
        self.repo_root = args.registry.resolve().parents[2]
        self.study_dir = args.study_dir.resolve()
        self.manifest_dir = self.study_dir / "manifests"
        self.evaluation_dir = self.study_dir / "evaluations"
        self.started = time.monotonic()
        self.git_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.git_dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        self.selected_variants = (
            set(args.variants.split(",")) if args.variants else None
        )
        self.selected_seeds = (
            {int(seed) for seed in args.training_seeds.split(",")}
            if args.training_seeds
            else None
        )
        known_variants = {variant["id"] for variant in self.registry["variants"]}
        if self.selected_variants is not None:
            unknown = self.selected_variants - known_variants
            if unknown:
                raise ValueError(f"unknown selected variants: {sorted(unknown)}")
        known_seeds = set(self.registry["training_seeds"])
        if self.selected_seeds is not None:
            unknown = self.selected_seeds - known_seeds
            if unknown:
                raise ValueError(f"unknown selected training seeds: {sorted(unknown)}")

    def check_budget(self, stage: str) -> None:
        elapsed_minutes = (time.monotonic() - self.started) / 60
        if elapsed_minutes >= self.args.time_budget_minutes:
            raise RuntimeError(
                f"time budget reached before {stage}: "
                f"{elapsed_minutes:.1f} >= {self.args.time_budget_minutes:.1f} minutes"
            )

    def manifest_path(self, variant_id: str, seed: int) -> Path:
        run_id = f"{self.registry['study_id']}__{variant_id}__seed{seed}"
        return self.manifest_dir / f"{run_id}.json"

    def initialize_manifest(self, variant_id: str, seed: int) -> dict[str, Any]:
        path = self.manifest_path(variant_id, seed)
        if path.exists():
            return read_json(path)
        manifest = build_planned_manifest(
            self.registry,
            variant_id,
            seed,
            git_commit=self.git_commit,
            git_dirty=self.git_dirty,
        )
        manifest["status"] = "planned"
        write_json(path, manifest)
        return manifest

    def save_manifest(self, manifest: dict[str, Any]) -> None:
        variant_id = manifest["variant"]["id"]
        seed = manifest["training"]["seed"]
        write_json(self.manifest_path(variant_id, seed), manifest)

    def fail_manifest(
        self, manifest: dict[str, Any], *, stage: str, message: str
    ) -> None:
        manifest["status"] = "failed"
        manifest["failure"] = {
            "stage": stage,
            "message": message,
            "last_completed_step": self.registry["primary_checkpoint_vector_step"]
            if any(
                item["kind"] == "primary_checkpoint"
                for item in manifest["artifacts"]
            )
            else None,
        }
        self.save_manifest(manifest)

    def append_artifact(
        self, manifest: dict[str, Any], kind: str, path: Path
    ) -> None:
        resolved = path.resolve()
        record = {
            "kind": kind,
            "path_or_uri": str(resolved),
            "sha256": sha256_file(resolved) if resolved.is_file() else None,
        }
        manifest["artifacts"] = [
            item
            for item in manifest["artifacts"]
            if not (item["kind"] == kind and item["path_or_uri"] == str(resolved))
        ]
        manifest["artifacts"].append(record)

    def run_command(
        self,
        command: list[str],
        *,
        stage: str,
        log_path: Path,
        manifest: dict[str, Any] | None = None,
    ) -> None:
        self.check_budget(stage)
        rendered = shlex.join(command)
        print(f"\n=== {stage} ===\n$ {rendered}", flush=True)
        if self.args.dry_run:
            return

        log_path.parent.mkdir(parents=True, exist_ok=True)
        command_record = {
            "stage": stage,
            "command": rendered,
            "started_at": utc_now(),
            "ended_at": None,
            "wall_seconds": None,
            "exit_code": None,
        }
        if manifest is not None:
            manifest["commands"].append(command_record)
            manifest["status"] = "running"
            self.save_manifest(manifest)

        started = time.monotonic()
        with log_path.open("w") as log:
            process = subprocess.Popen(
                command,
                cwd=self.args.isaaclab_dir,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                sys.stdout.write(line)
                log.write(line)
            exit_code = process.wait()

        command_record["ended_at"] = utc_now()
        command_record["wall_seconds"] = time.monotonic() - started
        command_record["exit_code"] = exit_code
        if manifest is not None:
            self.append_artifact(manifest, f"{stage}_console", log_path)
            self.save_manifest(manifest)
        if exit_code != 0:
            if manifest is not None:
                manifest["status"] = "failed"
                manifest["failure"] = {
                    "stage": stage,
                    "message": f"command exited with code {exit_code}",
                    "last_completed_step": None,
                }
                self.save_manifest(manifest)
            raise RuntimeError(f"{stage} exited with code {exit_code}")

    def register_reused_baseline(self) -> None:
        if self.args.reuse_baseline_run is None:
            return
        manifest = self.initialize_manifest("B0", 42)
        run_dir = self.args.reuse_baseline_run.resolve()
        checkpoint = run_dir / "checkpoints" / "agent_2400.pt"
        if not checkpoint.is_file():
            raise FileNotFoundError(f"missing reused baseline checkpoint: {checkpoint}")
        manifest["status"] = "partial"
        manifest["provenance"]["git_commit"] = "historical-phase1-run"
        self.append_artifact(manifest, "training_run_directory", run_dir)
        self.append_artifact(manifest, "primary_checkpoint", checkpoint)
        for filename, kind in (("env.yaml", "resolved_env"), ("agent.yaml", "resolved_agent")):
            path = run_dir / filename
            if path.is_file():
                self.append_artifact(manifest, kind, path)
                manifest["provenance"][f"{kind}_sha256"] = sha256_file(path)
        self.save_manifest(manifest)

    def train_one(self, variant_id: str, seed: int) -> None:
        manifest = self.initialize_manifest(variant_id, seed)
        checkpoints = [
            Path(item["path_or_uri"])
            for item in manifest["artifacts"]
            if item["kind"] == "primary_checkpoint"
        ]
        if checkpoints and checkpoints[0].is_file():
            print(f"[skip] {variant_id} seed {seed} already trained", flush=True)
            return

        log_root = self.args.isaaclab_dir / "logs/skrl/cartpole"
        before = {path.resolve() for path in log_root.iterdir()} if log_root.exists() else set()
        command = [
            str(self.args.isaaclab_dir / "isaaclab.sh"),
            "-p",
            "scripts/reinforcement_learning/train.py",
            "--rl_library=skrl",
            f"--task={self.registry['task']}",
            "--algorithm=PPO",
            f"--seed={seed}",
            f"--num_envs={self.registry['training_num_envs']}",
            "--viz",
            "none",
            *hydra_tokens(self.registry, variant_id, scope="train"),
        ]
        log_path = self.study_dir / "training_logs" / f"{variant_id}__seed{seed}.log"
        self.run_command(
            command,
            stage=f"train_{variant_id}_seed{seed}",
            log_path=log_path,
            manifest=manifest,
        )
        if self.args.dry_run:
            return

        after = {path.resolve() for path in log_root.iterdir() if path.is_dir()}
        created = sorted(after - before, key=lambda path: path.stat().st_mtime)
        if len(created) != 1:
            raise RuntimeError(
                f"expected one new training directory for {variant_id} seed {seed}, "
                f"found {len(created)}: {created}"
            )
        run_dir = created[0]
        checkpoint = run_dir / "checkpoints" / "agent_2400.pt"
        if not checkpoint.is_file():
            raise FileNotFoundError(f"missing primary checkpoint: {checkpoint}")

        self.append_artifact(manifest, "training_run_directory", run_dir)
        self.append_artifact(manifest, "primary_checkpoint", checkpoint)
        for filename, kind in (("env.yaml", "resolved_env"), ("agent.yaml", "resolved_agent")):
            path = run_dir / filename
            if path.is_file():
                self.append_artifact(manifest, kind, path)
                manifest["provenance"][f"{kind}_sha256"] = sha256_file(path)
        manifest["status"] = "partial"
        self.save_manifest(manifest)

    def checkpoint_for(self, variant_id: str, seed: int) -> Path:
        manifest = read_json(self.manifest_path(variant_id, seed))
        paths = [
            Path(item["path_or_uri"])
            for item in manifest["artifacts"]
            if item["kind"] == "primary_checkpoint"
        ]
        if len(paths) != 1 or not paths[0].is_file():
            raise RuntimeError(f"no usable checkpoint for {variant_id} seed {seed}")
        return paths[0]

    def training_run_for(self, variant_id: str, seed: int) -> Path:
        manifest = read_json(self.manifest_path(variant_id, seed))
        paths = [
            Path(item["path_or_uri"])
            for item in manifest["artifacts"]
            if item["kind"] == "training_run_directory"
        ]
        if len(paths) != 1 or not paths[0].is_dir():
            raise RuntimeError(f"no usable training directory for {variant_id} seed {seed}")
        return paths[0]

    def evaluate_screening(self, variant_id: str) -> None:
        output = self.evaluation_dir / "screening" / f"{variant_id}.json"
        if output.is_file():
            print(f"[skip] screening evaluation exists for {variant_id}", flush=True)
            return
        manifest = read_json(self.manifest_path(variant_id, 42))
        checkpoint_dir = self.training_run_for(variant_id, 42) / "checkpoints"
        command = [
            str(self.args.isaaclab_dir / "isaaclab.sh"),
            "-p",
            str(self.repo_root / "tools/evaluate_cartpole.py"),
            "--policy=sweep",
            f"--task={self.registry['task']}",
            f"--checkpoint-dir={checkpoint_dir}",
            f"--training-num-envs={self.registry['training_num_envs']}",
            "--seeds=" + ",".join(str(seed) for seed in self.registry["evaluation_seeds"]),
            f"--episodes-per-seed={self.registry['episodes_per_evaluation_seed']}",
            "--num-envs=5",
            "--max-steps-per-seed=1000",
            f"--upright-threshold-degrees={self.registry['upright_threshold_degrees']}",
            "--robust-success-upright-fraction="
            + str(self.registry["robust_success_upright_fraction"]),
            f"--action-sign-deadband={self.registry['action_sign_deadband']}",
            f"--output={output}",
            "--viz",
            "none",
            *hydra_tokens(
                self.registry,
                variant_id,
                scope="eval",
                profile_id="canonical5",
            ),
        ]
        self.run_command(
            command,
            stage=f"screening_{variant_id}",
            log_path=self.study_dir / "evaluation_logs" / f"screening_{variant_id}.log",
            manifest=manifest,
        )
        if not output.is_file():
            self.fail_manifest(
                manifest,
                stage=f"screening_{variant_id}",
                message="evaluator exited without writing the required JSON output",
            )
            raise RuntimeError(f"screening evaluator did not write {output}")
        self.append_artifact(manifest, "screening_evaluation", output)
        self.save_manifest(manifest)

    def evaluate_final(self, variant_id: str, seeds: list[int]) -> None:
        output = self.evaluation_dir / "final" / f"{variant_id}.json"
        if output.is_file():
            existing = read_json(output)
            existing_checkpoints = {
                Path(item["checkpoint"]).resolve()
                for item in existing.get("evaluations", [])
            }
            expected_checkpoints = {
                self.checkpoint_for(variant_id, seed).resolve() for seed in seeds
            }
            if existing_checkpoints == expected_checkpoints:
                print(f"[skip] final evaluation exists for {variant_id}", flush=True)
                return
            print(
                f"[rerun] final {variant_id}: checkpoint set changed "
                f"from {len(existing_checkpoints)} to {len(expected_checkpoints)}",
                flush=True,
            )
        checkpoints = [self.checkpoint_for(variant_id, seed) for seed in seeds]
        command = [
            str(self.args.isaaclab_dir / "isaaclab.sh"),
            "-p",
            str(self.repo_root / "tools/evaluate_cartpole.py"),
            "--policy=sweep",
            f"--task={self.registry['task']}",
            f"--training-num-envs={self.registry['training_num_envs']}",
            "--seeds=" + ",".join(str(seed) for seed in self.registry["evaluation_seeds"]),
            f"--episodes-per-seed={self.registry['episodes_per_evaluation_seed']}",
            "--num-envs=5",
            "--max-steps-per-seed=3600",
            f"--upright-threshold-degrees={self.registry['upright_threshold_degrees']}",
            "--robust-success-upright-fraction="
            + str(self.registry["robust_success_upright_fraction"]),
            f"--action-sign-deadband={self.registry['action_sign_deadband']}",
            f"--output={output}",
            "--viz",
            "none",
        ]
        for checkpoint in checkpoints:
            command.append(f"--checkpoint={checkpoint}")
        command.extend(
            hydra_tokens(
                self.registry,
                variant_id,
                scope="eval",
                profile_id="stress30",
            )
        )
        self.run_command(
            command,
            stage=f"final_{variant_id}",
            log_path=self.study_dir / "evaluation_logs" / f"final_{variant_id}.log",
        )
        if not output.is_file():
            for seed in seeds:
                manifest = read_json(self.manifest_path(variant_id, seed))
                self.fail_manifest(
                    manifest,
                    stage=f"final_{variant_id}",
                    message="evaluator exited without writing the required JSON output",
                )
            raise RuntimeError(f"final evaluator did not write {output}")
        for seed in seeds:
            manifest = read_json(self.manifest_path(variant_id, seed))
            self.append_artifact(manifest, "final_evaluation", output)
            manifest["status"] = "succeeded"
            manifest["failure"] = None
            self.save_manifest(manifest)

    def selected_rows(self) -> list[dict[str, Any]]:
        rows = build_run_matrix(self.registry)
        return [
            row
            for row in rows
            if (self.selected_variants is None or row["variant_id"] in self.selected_variants)
            and (
                self.selected_seeds is None
                or row["training_seed"] in self.selected_seeds
            )
        ]

    def write_summary(self) -> None:
        manifests = [read_json(path) for path in sorted(self.manifest_dir.glob("*.json"))]
        summary = {
            "schema_version": 1,
            "study_id": self.registry["study_id"],
            "generated_at": utc_now(),
            "registry_sha256": canonical_sha256(self.registry),
            "elapsed_minutes": (time.monotonic() - self.started) / 60,
            "status_counts": {
                status: sum(item["status"] == status for item in manifests)
                for status in (
                    "planned",
                    "running",
                    "reused",
                    "partial",
                    "succeeded",
                    "failed",
                )
            },
            "manifest_count": len(manifests),
            "screening_evaluation_count": len(
                list((self.evaluation_dir / "screening").glob("*.json"))
            ),
            "final_evaluation_count": len(
                list((self.evaluation_dir / "final").glob("*.json"))
            ),
        }
        write_json(self.study_dir / "study_summary.json", summary)
        print(json.dumps(summary, indent=2), flush=True)

    def run(self) -> None:
        self.study_dir.mkdir(parents=True, exist_ok=True)
        self.register_reused_baseline()
        rows = self.selected_rows()

        if self.args.phase in {"train", "all"}:
            for row in rows:
                if row["status"] == "reused":
                    continue
                self.train_one(row["variant_id"], row["training_seed"])

        if self.args.phase in {"screening", "all"}:
            variants = sorted(
                {
                    row["variant_id"]
                    for row in rows
                    if row["training_seed"] == 42
                }
            )
            for variant_id in variants:
                self.evaluate_screening(variant_id)

        if self.args.phase in {"final", "all"}:
            variants = sorted({row["variant_id"] for row in rows})
            for variant_id in variants:
                seeds = sorted(
                    row["training_seed"]
                    for row in rows
                    if row["variant_id"] == variant_id
                )
                self.evaluate_final(variant_id, seeds)

        self.write_summary()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "experiments/01_cartpole_ppo/variants.json",
    )
    parser.add_argument("--isaaclab-dir", type=Path, default=Path("/workspace/isaaclab"))
    parser.add_argument(
        "--study-dir",
        type=Path,
        default=Path("/workspace/phase2/cartpole_controlled_study"),
    )
    parser.add_argument(
        "--reuse-baseline-run",
        type=Path,
        help="Existing Phase 1 seed-42 B0 training directory.",
    )
    parser.add_argument(
        "--phase",
        choices=("train", "screening", "final", "all"),
        default="all",
    )
    parser.add_argument("--variants", help="Comma-separated variant IDs.")
    parser.add_argument("--training-seeds", help="Comma-separated training seeds.")
    parser.add_argument("--time-budget-minutes", type=float, default=55.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.time_budget_minutes <= 0:
        raise SystemExit("--time-budget-minutes must be positive")
    runner = StudyRunner(args)
    try:
        runner.run()
    except Exception:
        runner.write_summary()
        raise


if __name__ == "__main__":
    main()
