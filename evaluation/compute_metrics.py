#!/usr/bin/env python3
"""Compute EvoCode-Bench metrics from official Harbor multi-step outputs.

Reads per-step rewards from Harbor trial directories produced by the official
multi-step runner:

    <trial>/steps/<step-name>/verifier/reward.txt   # binary 1/0 per step
    <trial>/result.json                              # trial metadata

Trials are grouped by task slug (the task directory name appears in the trial
path). The script reports the official mean per-step reward, best-of-attempt
MT@k, final-step completion, and the stricter all-steps-passed perfect-task
rate derived from the same per-step rewards.

Single-Round (SR) is measured from separate fast-forward runs (see the README's
Single-Round Fast-Forward section); point --results-dir at those runs to score
SR with the same per-step reward reading.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tomllib
from collections import defaultdict
from pathlib import Path


def task_step_names(tasks_dir: Path) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for task in sorted(tasks_dir.iterdir()):
        cfg_path = task / "task.toml"
        if not cfg_path.exists():
            continue
        try:
            with cfg_path.open("rb") as f:
                cfg = tomllib.load(f)
        except Exception:  # noqa: BLE001
            continue
        names = [s.get("name") for s in (cfg.get("steps") or []) if s.get("name")]
        if names:
            index[task.name] = names
    return index


def trial_step_rewards(trial_dir: Path, step_names: list[str]) -> dict[int, float]:
    rewards: dict[int, float] = {}
    for i, name in enumerate(step_names, start=1):
        rf = trial_dir / "steps" / name / "verifier" / "reward.txt"
        if rf.exists():
            try:
                rewards[i] = float(rf.read_text().strip())
            except (ValueError, OSError):
                pass
    return rewards


def find_slug(path: Path, slugs: dict[str, list[str]]) -> str | None:
    parts = set(path.parts)
    for slug in slugs:
        if slug in parts:
            return slug
    return None


def jobs_bucket(path: Path) -> str | None:
    """Return the harbor_jobs/<bucket>/ name for a trial path (e.g. the model, or 'oracle'/'nop')."""
    parts = path.parts
    if "harbor_jobs" in parts:
        i = parts.index("harbor_jobs")
        if i + 1 < len(parts):
            return parts[i + 1]
    return None


def passed(reward: float | None) -> float:
    return 1.0 if (reward is not None and reward >= 0.999) else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-dir", type=Path, required=True,
                        help="Directory of EvoCode-Bench task folders (for the [[steps]] index)")
    parser.add_argument("--results-dir", type=Path, required=True,
                        help="Directory to scan for Harbor trial result.json files")
    parser.add_argument("--model", default=None,
                        help="Only score trials under harbor_jobs/<model>/ (short name, e.g. claude-opus-4-7). "
                             "Default: score every bucket except the 'oracle' and 'nop' baselines.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    tasks = task_step_names(args.tasks_dir)
    if not tasks:
        print(f"error: no tasks under {args.tasks_dir}", file=sys.stderr)
        return 2

    model_short = args.model.split("/")[-1] if args.model else None
    grouped: dict[str, list[dict[int, float]]] = defaultdict(list)
    for result in args.results_dir.rglob("result.json"):
        trial_dir = result.parent
        if not (trial_dir / "steps").is_dir():
            continue
        bucket = jobs_bucket(trial_dir)
        if model_short is not None:
            if bucket != model_short:
                continue
        elif bucket in ("oracle", "nop"):
            continue
        slug = find_slug(trial_dir, tasks)
        if slug is None:
            continue
        grouped[slug].append(trial_step_rewards(trial_dir, tasks[slug]))

    per_task_mean: dict[str, float] = {}   # official: mean over attempts of (fraction of steps passed)
    per_task_mtk: dict[str, float] = {}    # paper: best-of-attempt per step, then mean over steps
    completed_final_step: dict[str, bool] = {}
    perfect_task: dict[str, bool] = {}

    for slug, step_names in tasks.items():
        n = len(step_names)
        attempts = grouped.get(slug, [])
        if not attempts:
            continue
        attempt_scores = [sum(passed(tr.get(i)) for i in range(1, n + 1)) / n for tr in attempts]
        per_task_mean[slug] = statistics.mean(attempt_scores)
        best_per_step = [max(passed(tr.get(i)) for tr in attempts) for i in range(1, n + 1)]
        per_task_mtk[slug] = sum(best_per_step) / n
        completed_final_step[slug] = any(passed(tr.get(n)) >= 1.0 for tr in attempts)
        perfect_task[slug] = any(
            all(passed(tr.get(i)) >= 1.0 for i in range(1, n + 1))
            for tr in attempts
        )

    n_tasks = len(tasks)
    evaluated = len(per_task_mean)
    mean_reward = 100 * statistics.mean(per_task_mean.values()) if per_task_mean else 0.0
    mt_at_k = 100 * sum(per_task_mtk.values()) / n_tasks if n_tasks else 0.0
    final_step_comp = 100 * sum(1 for v in completed_final_step.values() if v) / n_tasks if n_tasks else 0.0
    perfect = 100 * sum(1 for v in perfect_task.values() if v) / n_tasks if n_tasks else 0.0
    hard = (100 * sum(1 for v in per_task_mean.values() if v <= 0.5) / evaluated) if evaluated else 0.0

    metrics = {
        "tasks": n_tasks,
        "evaluated": evaluated,
        "mean_reward": round(mean_reward, 2),
        "mt_at_k": round(mt_at_k, 2),
        "final_step_completion_rate": round(final_step_comp, 2),
        "completion_rate": round(final_step_comp, 2),
        "perfect_task_rate": round(perfect, 2),
        "hard_task_rate": round(hard, 2),
    }

    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print(f"Tasks: {n_tasks}  (evaluated: {evaluated})")
        print(f"  Mean per-step reward (official): {mean_reward:.1f}")
        print(f"  MT@k (best-of-attempt):          {mt_at_k:.1f}")
        print(f"  Final-step completion rate:      {final_step_comp:.1f}")
        print(f"  Perfect-task rate (all steps):   {perfect:.1f}")
        print(f"  Hard-task rate (score <= 0.5):   {hard:.1f}")
        if evaluated < n_tasks:
            print(f"  note: {n_tasks - evaluated} task(s) had no trials under {args.results_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
