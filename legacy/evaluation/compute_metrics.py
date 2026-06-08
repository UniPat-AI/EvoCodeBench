#!/usr/bin/env python3
"""Compute EvoCode-Bench MT-style metrics from Harbor multi-turn outputs.

The script expects Harbor trial directories containing:

    <trial>/result.json
    <trial>/verifier/multiround_results.json

It groups trials by task slug, computes best-of-attempt round rewards, and
reports the mean per-task fail-stop score. This matches the paper's MT@4
definition when each task has four attempts.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TrialRecord:
    task: str
    num_rounds: int
    round_rewards: dict[int, float]
    reward: float | None
    aggregate_start: int | None
    aggregate_end: int | None
    turns: float | None
    output_tokens: float | None


def load_num_rounds(task_dir: Path) -> int:
    with (task_dir / "task.toml").open("rb") as f:
        data = tomllib.load(f)
    return int(data["metadata"]["multiround"]["num_rounds"])


def task_index(tasks_dir: Path) -> dict[str, int]:
    index: dict[str, int] = {}
    for task_dir in sorted(tasks_dir.iterdir()):
        if (task_dir / "task.toml").exists():
            index[task_dir.name] = load_num_rounds(task_dir)
    return index


def find_task_slug(path: Path, tasks: dict[str, int]) -> str | None:
    parts = set(path.parts)
    for slug in tasks:
        if slug in parts:
            return slug
    return None


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_trial(result_path: Path, tasks: dict[str, int]) -> TrialRecord | None:
    task = find_task_slug(result_path, tasks)
    if task is None:
        return None

    trial_dir = result_path.parent
    mr_path = trial_dir / "verifier" / "multiround_results.json"
    if not mr_path.exists():
        return None

    result = read_json(result_path)
    mr = read_json(mr_path)

    rewards: dict[int, float] = {}
    for item in mr:
        if not isinstance(item, dict):
            continue
        round_num = item.get("round")
        reward = item.get("reward")
        if isinstance(round_num, int) and isinstance(reward, (int, float)):
            rewards[round_num] = float(reward)

    verifier = result.get("verifier_result") or {}
    agent = result.get("agent_result") or {}
    metadata = agent.get("metadata") or {}
    turns = metadata.get("n_episodes")
    output_tokens = agent.get("n_output_tokens")

    return TrialRecord(
        task=task,
        num_rounds=tasks[task],
        round_rewards=rewards,
        reward=(verifier.get("rewards") or {}).get("reward"),
        aggregate_start=verifier.get("aggregate_window_start"),
        aggregate_end=verifier.get("aggregate_window_end"),
        turns=float(turns) if isinstance(turns, (int, float)) else None,
        output_tokens=float(output_tokens) if isinstance(output_tokens, (int, float)) else None,
    )


def discover_trials(results_dir: Path, tasks: dict[str, int]) -> list[TrialRecord]:
    records: list[TrialRecord] = []
    for result_path in sorted(results_dir.rglob("result.json")):
        record = load_trial(result_path, tasks)
        if record is not None:
            records.append(record)
    return records


def compute(records: list[TrialRecord], tasks: dict[str, int]) -> dict[str, Any]:
    by_task: dict[str, list[TrialRecord]] = {slug: [] for slug in tasks}
    for record in records:
        by_task.setdefault(record.task, []).append(record)

    task_scores: dict[str, float] = {}
    task_completed: dict[str, bool] = {}
    attempts_per_task: dict[str, int] = {}

    for slug, num_rounds in tasks.items():
        trials = by_task.get(slug, [])
        attempts_per_task[slug] = len(trials)
        best_rounds: list[float] = []
        for round_num in range(1, num_rounds + 1):
            best = 0.0
            for trial in trials:
                best = max(best, trial.round_rewards.get(round_num, 0.0))
            best_rounds.append(best)
        task_scores[slug] = sum(best_rounds) / num_rounds if num_rounds else 0.0
        task_completed[slug] = any(t.round_rewards.get(num_rounds, 0.0) >= 1.0 for t in trials)

    mt_score = sum(task_scores.values()) / len(tasks) if tasks else 0.0
    comp = sum(1 for v in task_completed.values() if v) / len(tasks) if tasks else 0.0

    turns = [r.turns for r in records if r.turns is not None]
    tokens = [r.output_tokens for r in records if r.output_tokens is not None]

    return {
        "tasks": len(tasks),
        "evaluated_tasks": sum(1 for v in attempts_per_task.values() if v > 0),
        "trials": len(records),
        "mt_score": mt_score * 100,
        "completion_rate": comp * 100,
        "avg_turns": statistics.mean(turns) if turns else None,
        "output_tokens_k": (statistics.mean(tokens) / 1000) if tokens else None,
        "task_scores": task_scores,
        "attempts_per_task": attempts_per_task,
    }


def print_table(metrics: dict[str, Any]) -> None:
    print("=" * 64)
    print("EvoCode-Bench Results")
    print("=" * 64)
    print(f"  Tasks evaluated:   {metrics['evaluated_tasks']}/{metrics['tasks']}")
    print(f"  Trials found:       {metrics['trials']}")
    print(f"  MT score:           {metrics['mt_score']:.1f}")
    print(f"  Completion rate:    {metrics['completion_rate']:.1f}")
    if metrics["avg_turns"] is not None:
        print(f"  Avg turns:          {metrics['avg_turns']:.1f}")
    if metrics["output_tokens_k"] is not None:
        print(f"  Output tokens:      {metrics['output_tokens_k']:.1f}K")
    print("=" * 64)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-dir", type=Path, required=True, help="EvoCode-Bench task directory")
    parser.add_argument("--results-dir", type=Path, required=True, help="Harbor jobs/results directory")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a text table")
    args = parser.parse_args()

    if not args.tasks_dir.is_dir():
        print(f"error: not a directory: {args.tasks_dir}", file=sys.stderr)
        return 2
    if not args.results_dir.is_dir():
        print(f"error: not a directory: {args.results_dir}", file=sys.stderr)
        return 2

    tasks = task_index(args.tasks_dir)
    records = discover_trials(args.results_dir, tasks)
    metrics = compute(records, tasks)

    if args.json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    else:
        print_table(metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

