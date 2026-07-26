#!/usr/bin/env python3
"""Collect small, non-secret environment metadata for an experiment record."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


def command_output(command: list[str]) -> str | None:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def collect() -> dict[str, Any]:
    torch_version = package_version("torch")
    cuda_version = None
    if torch_version is not None:
        import torch

        cuda_version = torch.version.cuda

    return {
        "platform": platform.platform(),
        "os_release": command_output(["bash", "-lc", ". /etc/os-release && printf '%s' \"$PRETTY_NAME\""]),
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "gpu": command_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ]
        ),
        "torch": torch_version,
        "torch_cuda": cuda_version,
        "isaaclab": package_version("isaaclab"),
        "isaacsim": package_version("isaacsim"),
        "skrl": package_version("skrl"),
        "rsl_rl": package_version("rsl-rl"),
        "working_directory": os.getcwd(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.dumps(collect(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)


if __name__ == "__main__":
    main()
