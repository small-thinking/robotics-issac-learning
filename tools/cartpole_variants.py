#!/usr/bin/env python3
"""Validate and inspect the preregistered CartPole ablation matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY = (
    Path(__file__).resolve().parents[1] / "experiments/01_cartpole_ppo/variants.json"
)


class RegistryError(ValueError):
    """Raised when the experiment registry violates its contract."""


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_registry(path: Path | str = DEFAULT_REGISTRY) -> dict[str, Any]:
    registry = json.loads(Path(path).read_text())
    validate_registry(registry)
    return registry


def _require_unique(items: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise RegistryError(f"{label} has a missing or invalid id")
        if item_id in result:
            raise RegistryError(f"duplicate {label} id: {item_id}")
        result[item_id] = item
    return result


def _validate_override(
    override: dict[str, Any],
    allowed: dict[str, dict[str, Any]],
    expected_scope: str,
) -> None:
    path = override.get("path")
    if path not in allowed:
        raise RegistryError(f"override path is not allowlisted: {path}")
    specification = allowed[path]
    if specification["scope"] != expected_scope:
        raise RegistryError(
            f"{path} has scope {specification['scope']}, expected {expected_scope}"
        )

    value = override.get("value")
    value_type = specification["type"]
    valid = {
        "null": value is None,
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "array": isinstance(value, list),
    }.get(value_type, False)
    if not valid:
        raise RegistryError(f"{path} must have type {value_type}")
    if value_type == "array":
        if len(value) != specification.get("length"):
            raise RegistryError(f"{path} must have length {specification.get('length')}")
        if specification.get("items") == "number" and any(
            not isinstance(item, (int, float)) or isinstance(item, bool) for item in value
        ):
            raise RegistryError(f"{path} must contain only numbers")


def validate_registry(registry: dict[str, Any]) -> None:
    if registry.get("schema_version") != 1:
        raise RegistryError("unsupported schema_version")

    variants = _require_unique(registry.get("variants", []), "variant")
    profiles = _require_unique(registry.get("evaluation_profiles", []), "profile")
    waves = _require_unique(registry.get("waves", []), "wave")
    baseline_id = registry.get("baseline_variant_id")
    if baseline_id not in variants:
        raise RegistryError("baseline_variant_id does not name a variant")

    allowed = registry.get("allowed_overrides", {})
    if not allowed:
        raise RegistryError("allowed_overrides cannot be empty")

    for variant in variants.values():
        contrast_id = variant.get("contrast_variant_id")
        if contrast_id is not None and contrast_id not in variants:
            raise RegistryError(f"{variant['id']} has unknown contrast {contrast_id}")
        for override in variant.get("interface_overrides", []):
            _validate_override(override, allowed, "interface")
        for override in variant.get("objective_overrides", []):
            _validate_override(override, allowed, "objective")

    for profile in profiles.values():
        if profile.get("num_envs", 0) < registry.get("episodes_per_evaluation_seed", 0):
            raise RegistryError(f"profile {profile['id']} has too few environments")
        if profile.get("max_steps_per_seed", 0) <= 0:
            raise RegistryError(f"profile {profile['id']} has invalid max steps")
        for override in profile.get("overrides", []):
            _validate_override(override, allowed, "evaluation_profile")

    seen_cells: set[tuple[str, int]] = set()
    for wave in waves.values():
        for variant_id in wave.get("variant_ids", []):
            if variant_id not in variants:
                raise RegistryError(f"wave {wave['id']} has unknown variant {variant_id}")
            for seed in wave.get("training_seeds", []):
                cell = (variant_id, seed)
                if cell in seen_cells:
                    raise RegistryError(f"duplicate training cell: {variant_id}, seed {seed}")
                seen_cells.add(cell)
        profile_ids = list(wave.get("checkpoint_evaluation_profiles", []))
        profile_ids += wave.get("final_checkpoint_evaluation_profiles", [])
        for profile_id in profile_ids:
            if profile_id not in profiles:
                raise RegistryError(f"wave {wave['id']} has unknown profile {profile_id}")


def get_variant(registry: dict[str, Any], variant_id: str) -> dict[str, Any]:
    for variant in registry["variants"]:
        if variant["id"] == variant_id:
            return variant
    raise RegistryError(f"unknown variant: {variant_id}")


def get_profile(registry: dict[str, Any], profile_id: str) -> dict[str, Any]:
    for profile in registry["evaluation_profiles"]:
        if profile["id"] == profile_id:
            return profile
    raise RegistryError(f"unknown evaluation profile: {profile_id}")


def _hydra_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, separators=(",", ":"))


def hydra_tokens(
    registry: dict[str, Any],
    variant_id: str,
    *,
    scope: str,
    profile_id: str | None = None,
) -> list[str]:
    if scope not in {"train", "eval"}:
        raise RegistryError(f"invalid scope: {scope}")
    variant = get_variant(registry, variant_id)
    overrides = list(variant["interface_overrides"])
    if scope == "train":
        overrides += variant["objective_overrides"]
    elif profile_id is not None:
        overrides += get_profile(registry, profile_id)["overrides"]
    return [f"{item['path']}={_hydra_value(item['value'])}" for item in overrides]


def build_run_matrix(registry: dict[str, Any]) -> list[dict[str, Any]]:
    reused = {
        (item["variant_id"], item["training_seed"])
        for wave in registry["waves"]
        for item in wave.get("reuse_existing", [])
    }
    rows = []
    for wave in registry["waves"]:
        for variant_id in wave["variant_ids"]:
            for seed in wave["training_seeds"]:
                rows.append(
                    {
                        "run_id": f"{registry['study_id']}__{variant_id}__seed{seed}",
                        "wave": wave["id"],
                        "variant_id": variant_id,
                        "training_seed": seed,
                        "status": "reused" if (variant_id, seed) in reused else "planned",
                        "checkpoint_vector_steps": wave["checkpoint_vector_steps"],
                        "checkpoint_evaluation_profiles": wave[
                            "checkpoint_evaluation_profiles"
                        ],
                        "final_checkpoint_evaluation_profiles": wave[
                            "final_checkpoint_evaluation_profiles"
                        ],
                    }
                )
    return rows


def build_planned_manifest(
    registry: dict[str, Any],
    variant_id: str,
    training_seed: int,
    *,
    git_commit: str,
    git_dirty: bool,
) -> dict[str, Any]:
    row = next(
        (
            candidate
            for candidate in build_run_matrix(registry)
            if candidate["variant_id"] == variant_id
            and candidate["training_seed"] == training_seed
        ),
        None,
    )
    if row is None:
        raise RegistryError(
            f"variant {variant_id} and seed {training_seed} are not in the run matrix"
        )
    variant = get_variant(registry, variant_id)
    expected_diff = variant["interface_overrides"] + variant["objective_overrides"]
    return {
        "schema_version": 1,
        "study_id": registry["study_id"],
        "run_id": row["run_id"],
        "status": row["status"],
        "variant": {
            "id": variant["id"],
            "factor": variant["factor"],
            "factor_level": variant["factor_level"],
            "contrast_variant_id": variant["contrast_variant_id"],
            "expected_diff": expected_diff,
            "registry_sha256": canonical_sha256(registry),
            "interface_contract_sha256": canonical_sha256(
                variant["interface_overrides"]
            ),
        },
        "training": {
            "seed": training_seed,
            "num_envs": registry["training_num_envs"],
            "task": registry["task"],
            "checkpoint_vector_step": registry["primary_checkpoint_vector_step"],
        },
        "evaluation": {
            "profile_ids": row["checkpoint_evaluation_profiles"]
            + row["final_checkpoint_evaluation_profiles"],
            "seeds": registry["evaluation_seeds"],
            "episodes_per_seed": registry["episodes_per_evaluation_seed"],
            "fixed_environment_ids": list(
                range(registry["episodes_per_evaluation_seed"])
            ),
        },
        "provenance": {
            "git_commit": git_commit,
            "git_dirty": git_dirty,
            "software": {},
            "gpu": {},
            "resolved_env_sha256": None,
            "resolved_agent_sha256": None,
        },
        "commands": [],
        "artifacts": [],
        "failure": None,
    }


def _git_provenance() -> tuple[str, bool]:
    root = DEFAULT_REGISTRY.parents[2]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return commit, dirty


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("variant_id")
    show_parser.add_argument("--scope", choices=("train", "eval"), default="train")
    show_parser.add_argument("--profile")

    args_parser = subparsers.add_parser("hydra-args")
    args_parser.add_argument("variant_id")
    args_parser.add_argument("--scope", choices=("train", "eval"), required=True)
    args_parser.add_argument("--profile")

    matrix_parser = subparsers.add_parser("matrix")
    matrix_parser.add_argument(
        "--wave",
        choices=("screening", "confirmation", "all"),
        default="all",
    )
    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("variant_id")
    manifest_parser.add_argument("--training-seed", type=int, required=True)

    args = parser.parse_args()
    registry = load_registry(args.registry)

    if args.command == "validate":
        print(
            json.dumps(
                {
                    "study_id": registry["study_id"],
                    "registry_sha256": canonical_sha256(registry),
                    "variant_count": len(registry["variants"]),
                    "run_count": len(build_run_matrix(registry)),
                },
                indent=2,
            )
        )
    elif args.command == "show":
        print(
            json.dumps(
                {
                    "variant": get_variant(registry, args.variant_id),
                    "scope": args.scope,
                    "profile": args.profile,
                    "hydra_tokens": hydra_tokens(
                        registry, args.variant_id, scope=args.scope, profile_id=args.profile
                    ),
                },
                indent=2,
            )
        )
    elif args.command == "hydra-args":
        print(
            "\n".join(
                hydra_tokens(
                    registry, args.variant_id, scope=args.scope, profile_id=args.profile
                )
            )
        )
    elif args.command == "matrix":
        rows = build_run_matrix(registry)
        if args.wave != "all":
            rows = [row for row in rows if row["wave"] == args.wave]
        print(json.dumps(rows, indent=2))
    else:
        git_commit, git_dirty = _git_provenance()
        print(
            json.dumps(
                build_planned_manifest(
                    registry,
                    args.variant_id,
                    args.training_seed,
                    git_commit=git_commit,
                    git_dirty=git_dirty,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
