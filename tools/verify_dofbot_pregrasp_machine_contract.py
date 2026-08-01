#!/usr/bin/env python3
"""Fail closed unless a fresh DOFBOT pre-grasp machine contract passed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class PregraspContractVerificationError(ValueError):
    """The machine contract is missing, stale, malformed, or failed."""


def load_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PregraspContractVerificationError(
            f"cannot read machine contract {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise PregraspContractVerificationError(
            "machine contract root must be a JSON object"
        )
    return value


def verify_machine_contract(
    contract: dict[str, Any],
    *,
    expected_git_commit: str,
) -> None:
    actual_commit = contract.get("git_commit")
    if actual_commit != expected_git_commit:
        raise PregraspContractVerificationError(
            "machine contract git commit mismatch: "
            f"expected={expected_git_commit!r} actual={actual_commit!r}"
        )

    acceptance = contract.get("acceptance")
    machine = acceptance.get("machine") if isinstance(acceptance, dict) else None
    if not isinstance(machine, dict):
        raise PregraspContractVerificationError(
            "machine contract is missing acceptance.machine"
        )

    failed_checks = machine.get("failed_checks")
    if machine.get("machine_passed") is not True or failed_checks != []:
        raise PregraspContractVerificationError(
            "pre-grasp machine gate did not pass: "
            f"decision={machine.get('decision')!r} "
            f"failed_checks={failed_checks!r}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--expected-git-commit", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = load_contract(args.contract)
        verify_machine_contract(
            contract,
            expected_git_commit=args.expected_git_commit,
        )
    except PregraspContractVerificationError as error:
        print(f"[PREGRASP CONTRACT] FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "[PREGRASP CONTRACT] PASS: "
        f"commit={args.expected_git_commit} contract={args.contract}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
