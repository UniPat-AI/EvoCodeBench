#!/usr/bin/env python3
"""Aggregate EvoCode-Bench leaderboard + per-task sweep CSV from wotraj results.

For each (model, task):
  - passed_rounds / total_rounds  (round "passed" = binary reward 1)
  - case% = mean over rounds of (success_count/total_cases); build-fail or
    chain-never-reached round counts 0.

Then per model:
  - Dataset score = mean over scored tasks of (passed_rounds/total_rounds) x100
  - Case score    = mean over scored tasks of (per-task case%) x100
  - Perfect tasks = # tasks with passed_rounds == total_rounds

POLICY: missing / timeout / empty-reply / aborted rounds count as 0 (no fabrication).
Any cell in BLANK (below) is excluded from that model's denominator instead of scored 0.

Outputs:
  - <repo>/evaluation/sweeps/sweep_2026-06_single_shot.csv   (per-task grid, 12 models)
  - stdout: the leaderboard table (markdown) sorted by Dataset score
  - --json for machine-readable dump
"""
import os, glob, re, json, argparse, statistics

TASKS_DIR = os.environ.get(
    "EVOCODEBENCH_TASKS_DIR",
    "/nvme1/shenhaiyang/Source/swebenchpp/data/multiturn/archives/harbor_official_multistep_converted/evocodebench_wotraj",
)
REPO = os.environ.get("EVOCODEBENCH_REPO", "/nvme1/shenhaiyang/Source/EvoCodeBench")

# (display, harbor_jobs subdir, reasoning-label)
MODELS = [
    ("Claude-Opus-4.8", "claude-opus-4-8", "effort `xhigh`"),
    ("GPT-5.5", "gpt-5.5", "effort `high`"),
    ("Kimi-K2.6", "kimi-k2.6", "thinking on"),
    ("Kimi-K2.7-Code", "kimi-k2.7-code", "thinking on"),
    ("MiniMax-M3", "minimax-m3", "thinking `adaptive`"),
    ("DeepSeek-V4-Pro", "deepseek-v4-pro", "effort `high`"),
    ("Qwen3.6-Plus", "qwen3.6-plus", "thinking on"),
    ("Qwen3.7-Max", "qwen3.7-max", "thinking on"),
    ("GLM-5.1", "glm-5.1", "thinking on"),
    ("GLM-5.2", "glm-5.2", "thinking on"),
    ("DeepSeek-V4-Flash", "deepseek-v4-flash", "effort `high`"),
    ("MiniMax-M2.7", "minimax-m2.7", "reasoning split"),
]

# (harbor subdir, task-substring) -> BLANK (excluded from denominator). None currently.
BLANK = set()

SUMMARY_RE = re.compile(r'CASE_SUMMARY total_cases=(\d+) success_count=(\d+) fail_count=(\d+)')


def latest_run(task, ms):
    r = sorted(glob.glob(os.path.join(TASKS_DIR, task, "harbor_jobs", ms, "2026-*")))
    return r[-1] if r else None


def round_reward(run, rnd):
    rt = glob.glob(os.path.join(run, f"**/steps/round-{rnd}/verifier/reward.txt"), recursive=True)
    if not rt:
        return None
    try:
        return float(open(rt[0]).read().strip())
    except Exception:
        return None


def round_caseratio(run, rnd):
    so = glob.glob(os.path.join(run, f"**/steps/round-{rnd}/verifier/test-stdout.txt"), recursive=True)
    if not so:
        return 0.0
    txt = open(so[0], errors="ignore").read()
    m = SUMMARY_RE.search(txt)
    if not m:
        return 0.0
    total, succ = int(m.group(1)), int(m.group(2))
    return (succ / total) if total else 0.0


def round_reached(run, rnd):
    if not run:
        return False
    patterns = [
        f"**/steps/round-{rnd}/verifier/reward.txt",
        f"**/steps/round-{rnd}/verifier/test-stdout.txt",
    ]
    return any(glob.glob(os.path.join(run, pattern), recursive=True) for pattern in patterns)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-csv", action="store_true", help="overwrite the sweep CSV")
    args = ap.parse_args()

    tasks = sorted(d for d in os.listdir(TASKS_DIR)
                   if d.startswith("theme_") and os.path.isdir(os.path.join(TASKS_DIR, d, "steps")))
    nrounds = {t: len(glob.glob(os.path.join(TASKS_DIR, t, "steps", "round-*"))) for t in tasks}

    # cell[(disp,task)] = (passed, total, casepct, reached_rounds, blank_bool)
    cell = {}
    for disp, ms, _ in MODELS:
        for t in tasks:
            if (ms, t) in BLANK:
                cell[(disp, t)] = (None, nrounds[t], None, None, True)
                continue
            run = latest_run(t, ms)
            n = nrounds[t]
            passed = 0
            ratios = []
            reached = 0
            for rnd in range(1, n + 1):
                if round_reached(run, rnd):
                    reached += 1
                rw = round_reward(run, rnd) if run else None
                if rw is not None and rw >= 0.999:
                    passed += 1
                ratios.append(round_caseratio(run, rnd) if run else 0.0)
            casepct = 100 * statistics.mean(ratios) if ratios else 0.0
            cell[(disp, t)] = (passed, n, casepct, reached, False)

    # leaderboard
    board = []
    for disp, ms, reason in MODELS:
        ds, cs, avg_rounds, perfect, scored = [], [], [], 0, 0
        for t in tasks:
            p, n, cp, reached, blank = cell[(disp, t)]
            if blank:
                continue
            scored += 1
            ds.append(p / n if n else 0)
            cs.append(cp)
            avg_rounds.append(reached or 0)
            if p == n and n > 0:
                perfect += 1
        board.append({
            "model": disp, "reason": reason,
            "dataset": round(100 * statistics.mean(ds), 1) if ds else 0.0,
            "case": round(statistics.mean(cs), 1) if cs else 0.0,
            "avg_rounds": round(statistics.mean(avg_rounds), 1) if avg_rounds else 0.0,
            "perfect": perfect, "scored_tasks": scored,
        })
    board.sort(key=lambda x: -x["dataset"])

    if args.json:
        print(json.dumps({"board": board, "cells": {f"{d}|{t}": cell[(d, t)] for d, t in cell}}, indent=2))
    else:
        print(f"{'Agent':<20}{'Reasoning':<20}{'Dataset':>8}{'Case':>7}{'AvgRnd':>8}{'Perfect':>9}{'N':>4}")
        for b in board:
            note = "" if b["scored_tasks"] == 26 else f"  (over {b['scored_tasks']} tasks; d7_w5 blank)"
            print(f"{b['model']:<20}{b['reason']:<20}{b['dataset']:>8}{b['case']:>7}{b['avg_rounds']:>8}{str(b['perfect'])+'/'+str(b['scored_tasks']):>9}{b['scored_tasks']:>4}{note}")

    if args.write_csv:
        csv = os.path.join(REPO, "evaluation", "sweeps", "sweep_2026-06_single_shot.csv")
        cols = [d for d, _, _ in MODELS]
        lines = ["task,total_rounds," + ",".join(cols) + ",__note"]
        for t in tasks:
            row = [t, str(nrounds[t])]
            for d in cols:
                p, n, cp, reached, blank = cell[(d, t)]
                row.append("—" if blank else f"{p}/{n} c{round(cp)}% r{reached}")
            row.append("each cell: passed_rounds/total · c=mean case pass % · r=rounds actually reached")
            lines.append(",".join(row))
        open(csv, "w").write("\n".join(lines) + "\n")
        print(f"\nwrote {csv} ({len(tasks)} tasks × {len(cols)} models)")


if __name__ == "__main__":
    main()
