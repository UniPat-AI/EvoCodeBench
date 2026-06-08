#!/usr/bin/env python3
"""Validate EvoCode-Bench tasks in the official Harbor multi-step format.

Checks each task directory:
  - task.toml parses and declares a non-empty [[steps]] array;
  - every declared step has steps/<name>/{instruction.md, solution/solve.sh, tests/test.sh};
  - no orphan step directory exists that is not declared in [[steps]];
  - environment/Dockerfile and task.toml are present.

Reports the task count and per-task step count.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path


def validate_task(path: Path) -> tuple[int, list[str]]:
    errors: list[str] = []
    try:
        with (path / "task.toml").open("rb") as f:
            config = tomllib.load(f)
    except Exception as exc:  # noqa: BLE001
        return 0, [f"task.toml could not be parsed: {exc}"]

    steps = config.get("steps") or []
    if not steps:
        errors.append("task.toml declares no [[steps]]")

    names = [s.get("name") for s in steps]
    for name in names:
        if not name:
            errors.append("a [[steps]] entry is missing 'name'")
            continue
        step_dir = path / "steps" / name
        for rel in ("instruction.md", "solution/solve.sh", "tests/test.sh"):
            if not (step_dir / rel).exists():
                errors.append(f"missing steps/{name}/{rel}")

    steps_root = path / "steps"
    if steps_root.is_dir():
        on_disk = sorted(d.name for d in steps_root.iterdir() if d.is_dir())
        orphan = set(on_disk) - set(names)
        if orphan:
            errors.append(f"steps/ directories not declared in [[steps]]: {sorted(orphan)}")
    else:
        errors.append("missing steps/")

    for rel in ("environment/Dockerfile", "task.toml"):
        if not (path / rel).exists():
            errors.append(f"missing {rel}")

    return len(steps), errors


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

    total_steps = 0
    failed = 0
    for task in task_dirs:
        num_steps, errors = validate_task(task)
        total_steps += num_steps
        if errors:
            failed += 1
            print(f"FAIL  {task.name}")
            for err in errors:
                print(f"        - {err}")
        else:
            print(f"ok    {task.name}  ({num_steps} steps)")

    print()
    print(f"{len(task_dirs) - failed}/{len(task_dirs)} tasks valid  "
          f"| {len(task_dirs)} tasks, {total_steps} steps total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
