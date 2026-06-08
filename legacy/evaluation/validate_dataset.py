#!/usr/bin/env python3
"""Validate EvoCode-Bench task structure and summarize round metadata."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path


def load_task(path: Path) -> dict:
    with (path / "task.toml").open("rb") as f:
        return tomllib.load(f)


def validate_task(path: Path) -> tuple[int, list[str]]:
    errors: list[str] = []
    config = load_task(path)
    multiround = config.get("metadata", {}).get("multiround", {})
    num_rounds = multiround.get("num_rounds")
    rounds = multiround.get("rounds", [])

    if not isinstance(num_rounds, int) or num_rounds < 1:
        errors.append("metadata.multiround.num_rounds must be a positive integer")
        return 0, errors

    declared = [r.get("round") for r in rounds]
    expected = list(range(1, num_rounds + 1))
    if declared != expected:
        errors.append(f"round metadata must be contiguous {expected}, got {declared}")

    for round_num in expected:
        round_dir = path / f"round_{round_num}"
        if not round_dir.is_dir():
            errors.append(f"missing round_{round_num}/")
            continue
        for rel in ("instruction.md", "tests/test.sh", "solution/solve.sh"):
            if not (round_dir / rel).exists():
                errors.append(f"missing round_{round_num}/{rel}")

    for rel in ("instruction.md", "environment/Dockerfile", "task.toml"):
        if not (path / rel).exists():
            errors.append(f"missing {rel}")

    return num_rounds, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks_dir", type=Path, help="Directory containing EvoCode-Bench task folders")
    args = parser.parse_args()

    if not args.tasks_dir.is_dir():
        print(f"error: not a directory: {args.tasks_dir}", file=sys.stderr)
        return 2

    task_dirs = sorted(p for p in args.tasks_dir.iterdir() if (p / "task.toml").exists())
    if not task_dirs:
        print(f"error: no tasks found under {args.tasks_dir}", file=sys.stderr)
        return 2

    total_rounds = 0
    failed = 0
    for task in task_dirs:
        rounds, errors = validate_task(task)
        total_rounds += rounds
        if errors:
            failed += 1
            print(f"[FAIL] {task.name}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"[ OK ] {task.name}: {rounds} rounds")

    print()
    print(f"tasks: {len(task_dirs)}")
    print(f"rounds: {total_rounds}")
    if failed:
        print(f"invalid tasks: {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

