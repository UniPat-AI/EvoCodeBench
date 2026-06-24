<div align="center">

<h1>
  <img src="assets/hero.png" alt="EvoCode-Bench logo" width="42" />
  EvoCode-Bench: Evaluating Coding Agents in Multi-Turn Iterative Interactions
</h1>

[![Dataset](https://img.shields.io/badge/Dataset-Hugging_Face-orange?style=for-the-badge)](https://huggingface.co/datasets/UnipatAI/EvoCodeBench)
[![GitHub](https://img.shields.io/badge/GitHub-EvoCodeBench-24292F?style=for-the-badge&logo=github&logoColor=white)](https://github.com/UniPat-AI/EvoCodeBench)
[![Paper](https://img.shields.io/badge/Paper-arXiv_2605.24110-b91c1c?style=for-the-badge)](https://arxiv.org/abs/2605.24110)
[![More Work](https://img.shields.io/badge/More_Work-Terminal--X-24292F?style=for-the-badge&logo=github&logoColor=white)](https://github.com/UniPat-AI/Terminal-X)
[![Framework](https://img.shields.io/badge/Framework-Harbor_Official_Multi--Step-blue?style=for-the-badge)](https://harborframework.com/docs/tasks/multi-step)
[![Leaderboard](https://img.shields.io/badge/Leaderboard-UniPat_AI-brightgreen?style=for-the-badge)](https://unipat.ai/benchmarks/EvoCode-Bench)

</div>

---

## News

**2026-06-20 — Results re-release (v2).** The leaderboard, per-task results, and
trajectories published before this date are **superseded**. We re-ran the entire
benchmark on a patched harness after fixing an evaluation-integrity leak in Harbor's
shared multi-step verifier mode (agents could read the grader during their own turn;
reported upstream as [#1960](https://github.com/harbor-framework/harbor/issues/1960) /
[#1961](https://github.com/harbor-framework/harbor/pull/1961)), one contaminated task,
and 11 task/test defects. See
[Known issues & responsible disclosure](#known-issues--responsible-disclosure)
and [`CHANGELOG.md`](CHANGELOG.md). Treat any EvoCode-Bench number dated before 2026-06-20
as outdated.

**June 2026.** EvoCode-Bench runs on the **[Harbor official multi-step task format](https://harborframework.com/docs/tasks/multi-step)**. Each task is a sequence of `[[steps]]` run in one persistent container, with a per-step verifier after each step and trial-level reward aggregation.

EvoCode-Bench tests whether coding agents can keep a project working as user requests change. It contains **26 stateful coding tasks** and **227 evaluated rounds** (Harbor *steps*). Each task keeps the same workspace and agent session for **5-15 rounds**, while cumulative executable tests check new requirements and still-active prior requirements.

> The original paper evaluation used a different runner (`harbor_multiturn`) and the
> MT@4 / SR / Comp metrics. That framework, the legacy task layout, and the paper
> results are kept under [`legacy/`](legacy/README.md) for reproducibility — not needed
> for normal use.

## Overview

Most coding benchmarks evaluate one specification followed by one final assessment. EvoCode-Bench instead evaluates an interactive coding session. Later rounds inherit earlier implementation decisions, dependencies, file layouts, API choices, and test behavior. Each round (Harbor step) is scored by a cumulative verifier, and the trial reward is the mean of the per-step rewards.

The benchmark is organized along two axes from the paper:

| Engineering activity | Explorative | Contractual | Document-driven | Total |
|:--|--:|--:|--:|--:|
| Construction | 9 / 80 | 3 / 37 | 1 / 7 | 13 / 124 |
| Spec Evolution | 1 / 8 | 1 / 7 | 1 / 7 | 3 / 22 |
| Review | 3 / 21 | 1 / 7 | 1 / 9 | 5 / 37 |
| Migration | 3 / 29 | 1 / 7 | 1 / 8 | 5 / 44 |
| **Total** | **16 / 138** | **6 / 58** | **4 / 31** | **26 / 227** |

Each cell reports **tasks / rounds**. A *round* maps one-to-one to a Harbor *step*.

## Task Format

EvoCode-Bench tasks use the **Harbor official multi-step layout** — one sub-directory per step under `steps/`, executed in the order declared by the `[[steps]]` array in `task.toml`:

```text
task/
├── task.toml                       # metadata + [[steps]] list + reward strategy
├── environment/
│   └── Dockerfile                  # single container shared across all steps
└── steps/
    ├── round-1/
    │   ├── instruction.md          # this round's user request (WHAT, not HOW)
    │   ├── solution/solve.sh        # reference delta for this round
    │   └── tests/test.sh           # cumulative tests through this round
    ├── round-2/
    │   ├── instruction.md
    │   ├── solution/solve.sh
    │   └── tests/test.sh
    └── round-N/ ...
```

`task.toml` follows the official schema (`schema_version = "1.2"`):

```toml
schema_version = "1.2"
multi_step_reward_strategy = "mean"      # trial reward = mean of per-step rewards

[metadata]
name = "service-mesh-health-router"
difficulty = "hard"
category = "systems-networking"

[metadata.requirement_chain]
num_steps = 8

[[metadata.requirement_chain.steps]]
step = "round-1"
change_types = ["extension"]
# ... one entry per step (extension / correction / conflict)

[agent]
timeout_sec = 1800.0                      # global default; override per step via [steps.agent]

[verifier]
timeout_sec = 1800.0                      # global default; override per step via [steps.verifier]

[environment]
build_timeout_sec = 600.0
cpus = 1
memory_mb = 4096
storage_mb = 10240

[[steps]]
name = "round-1"                          # matches steps/round-1/

[[steps]]
name = "round-2"
# ... one [[steps]] entry per step, in execution order
```

The task format is built around three constraints:

- **Persistent workspace**: the same Docker container carries files, dependencies, and generated artifacts across steps.
- **Continuous agent session**: the agent receives a sequence of user requests rather than independent prompts.
- **Cumulative tests**: round `i` verifies every still-active requirement from rounds `1..i`, so regressions are caught immediately. Each step's `tests/test.sh` writes a binary reward to `/logs/verifier/reward.txt`.

## Framework

EvoCode-Bench's standard multi-step evaluation runs on **upstream [Harbor](https://harborframework.com)** — the same framework used by Terminal-Bench 2.0 — using its native multi-step support. No fork is required to run a full task (all steps).

```bash
uv tool install harbor      # or: pip install harbor
harbor run --help
```

Upstream Harbor's official multi-step runner provides:

- native `[[steps]]` sequencing in the order declared in `task.toml`;
- a single persistent Docker workspace shared across all steps;
- a continuous agent session across steps;
- a per-step verifier run against the cumulative test suite after each step;
- trial-level reward aggregation via `multi_step_reward_strategy` (`mean` for EvoCode-Bench).

> Need single-round fast-forward (SR), or want to reproduce the paper? See
> [`legacy/`](legacy/README.md) — it covers our Harbor fork and the original
> `harbor_multiturn` framework. Not required for normal use.

## Quick Start

### 1. Prerequisites

- **Python 3.11+** (the `evaluation/*.py` helpers use the stdlib `tomllib`).
- **Docker** running, or a remote Daytona target.
- A model endpoint for your agent.

Install the Harbor CLI:

```bash
# uv runs the Harbor CLI. See https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install harbor      # or: pip install harbor
```

`pip install harbor` (upstream) runs full tasks (all steps).

### 2. Prepare Tasks

Download the released EvoCode-Bench task directories from [Hugging Face](https://huggingface.co/datasets/UnipatAI/EvoCodeBench) and place them under `data/EvoCodeBench`. If you already have the Terminal-X repository, the tasks are also available under `Terminal-X/data/EvoCodeBench/`.

### 3. Configure Model Endpoint

For the `claude-code` agent:

```bash
export AGENT_TYPE="claude-code"
export AGENT_MODEL="claude-opus-4-7"
export ANTHROPIC_BASE_URL="https://api.your-provider.com"
export ANTHROPIC_AUTH_TOKEN="sk-..."
```

For the `terminus-2` agent (OpenAI-compatible):

```bash
export AGENT_TYPE="terminus-2"
export AGENT_MODEL="openai/gpt-5.5"
export OPENAI_API_KEY="sk-..."
export OPENAI_API_BASE="https://api.your-provider.com/v1"
```

### 4. Validate the Dataset

```bash
python evaluation/validate_dataset.py data/EvoCodeBench
```

The released benchmark should report **26 tasks** and **227 steps**.

### 5. Run One Task

```bash
# Agent (pass@1 by default; set AGENT_ATTEMPTS for pass@k)
AGENT_TYPE=claude-code AGENT_MODEL=claude-opus-4-7 \
  ./evaluation/run_single.sh data/EvoCodeBench/theme_d1_w1_code_build_greenfield_implementation agent

# Oracle verification (reference solutions; should score 1.0 on every step)
./evaluation/run_single.sh data/EvoCodeBench/theme_d1_w1_code_build_greenfield_implementation oracle

# No-op baseline (empty submission; should score 0)
./evaluation/run_single.sh data/EvoCodeBench/theme_d1_w1_code_build_greenfield_implementation nop
```

### 6. Run All Tasks

```bash
AGENT_TYPE=claude-code AGENT_MODEL=claude-opus-4-7 \
  ./evaluation/run_all.sh data/EvoCodeBench agent
```

Each task writes Harbor outputs under:

```text
data/EvoCodeBench/<task>/harbor_jobs/<model>/
```

## Metrics

Each step is scored with a **binary reward** — 1 if all of that step's key requirements pass, 0 otherwise — written by the verifier to `/logs/verifier/reward.txt`. Harbor aggregates a trial's per-step rewards into a trial-level reward via `multi_step_reward_strategy = "mean"`.

The score is the **mean per-step reward**:

- **per-task score** = (passed steps) / (total steps) for the trial;
- **dataset score** = mean of per-task scores across the 26 tasks.

A complementary **case score** uses the same shape at finer granularity. Each step's verifier
also reports per-test-case results (`CASE_SUMMARY total_cases=… success_count=…`). Define:

- **per-step case ratio** = `success_count / total_cases` for the step (a step whose code fails to
  build, or that the chain never reached, has ratio 0);
- **per-task case score** = mean of the per-step case ratios over the task's steps;
- **dataset case score** = mean of per-task case scores across the 26 tasks ×100.

The dataset score is all-or-nothing per step, so it rewards finishing a step exactly; the case score
credits partial progress (e.g. passing 44 of 45 cases). A large gap between the two for a model means it
gets most of the work right but rarely lands a whole step.

```bash
python evaluation/compute_metrics.py \
  --tasks-dir data/EvoCodeBench \
  --results-dir data/EvoCodeBench \
  --model claude-opus-4-7          # score one agent; add --json for machine-readable output
```

`--model` selects the `harbor_jobs/<model>/` results to score (the `oracle` and `nop` baselines are excluded by default).
For single-attempt runs, `mean_reward` is the same dataset-score quantity reported
in the leaderboard. The script also reports two completion-style diagnostics:
`final_step_completion_rate` (the last step passed, useful for legacy Comp-style
analysis because the last verifier is cumulative) and `perfect_task_rate` (one
attempt passed every step, the percentage version of the leaderboard's Perfect tasks).
The leaderboard table itself is generated by `evaluation/viz/leaderboard.py`.

> The paper's MT@4 / SR / Comp metrics and single-round fast-forward evaluation live
> in [`legacy/`](legacy/README.md).

## Results

Evaluated on the current dataset release with the Harbor official multi-step runner:
full 5–15 round chains, **one attempt per task** (no best-of-k). `oracle` scores 1.0
and `nop` scores 0 on every task.

The leaderboard mixes percentages, counts, and interaction counts, so read the columns
as follows:

| Column | Definition |
|:--|:--|
| Agent | Model or agent backend evaluated with the `terminus-2` scaffold. |
| Reasoning | Thinking / effort setting used for that model. |
| Dataset score | Current score on a 0–100 scale. For each task, compute `passed_rounds / total_rounds`; then average that task score over all 26 tasks and multiply by 100. If a chain aborts before later rounds, those missing rounds count as 0. This is close in spirit to MT@1 because it is one attempt per task, but it is not the legacy paper MT@1: this table uses the Harbor official multi-step full-chain runner and averages binary per-round rewards within each task first. |
| Case score | Current score on a 0–100 scale using verifier test cases instead of all-or-nothing round rewards: average each round's `passed_test_cases / total_test_cases`, then average by task and by dataset. Build failures and unreached rounds count as 0. |
| Avg rounds | Mean number of agent-tool interactions per reached benchmark round, read from `steps/round-N/agent/trajectory.json`. If a run stops before later benchmark rounds, those unreached rounds are not included in this average. |
| Perfect tasks | Number of tasks where every benchmark round passed, out of 26. This is the all-round completion count; for example, `9/26` equals a 34.6% completion rate. |

The table below is the **current 2026-06-20 clean re-release**. Earlier June 13–16
v1 numbers were withdrawn after the re-run and are not repeated here; see
[`CHANGELOG.md`](CHANGELOG.md), [Known issues & responsible disclosure](#known-issues--responsible-disclosure),
and [`legacy/`](legacy/README.md) for the historical record.

| Agent | Reasoning | Dataset score | Case score | Avg rounds | Perfect tasks |
|:--|:--|--:|--:|--:|--:|
| Claude-Opus-4.8 | effort `xhigh` | 59.1 | 96.6 | 62.2 | 9/26 |
| GPT-5.5 | effort `high` | 29.5 | 81.8 | 53.7 | 0/26 |
| MiniMax-M3 | thinking `adaptive` | 23.4 | 61.5 | 123.7 | 2/26 |
| GLM-5.2 | thinking on¹ | 16.2 | 47.5 | 66.3 | 1/26 |
| DeepSeek-V4-Pro | effort `high` | 14.1 | 61.7 | 144.1 | 1/26 |
| Kimi-K2.6 | thinking on¹ | 13.2 | 65.7 | 117.4 | 0/26 |
| DeepSeek-V4-Flash | effort `high` | 12.2 | 58.9 | 122.2 | 0/26 |
| Qwen3.7-Max | thinking on¹ | 11.9 | 67.4 | 117.1 | 0/26 |
| Qwen3.6-Plus | thinking on¹ | 9.7 | 67.7 | 115.8 | 0/26 |
| Kimi-K2.7-Code | thinking on¹ | 7.8 | 45.4 | 67.5 | 0/26 |
| GLM-5.1 | thinking on¹ | 5.9 | 52.5 | 88.4 | 0/26 |
| MiniMax-M2.7 | reasoning split | 5.1 | 44.9 | 115.1 | 0/26 |

GLM-5.2 and Kimi-K2.7-Code were added in the 2026-06-20 re-release.

*Reasoning* is the thinking configuration used for each model: models with an effort knob ran at the
listed level (Opus at its highest, `xhigh`; the rest at `high`); ¹ models without an
effort knob ran with their native thinking simply enabled (Qwen `enable_thinking`,
GLM/Kimi `thinking.type=enabled`), and MiniMax M3/M2.7 used their adaptive / split
reasoning modes. All agents used the `terminus-2` scaffold.

The case score credits partial progress that the all-or-nothing Dataset score hides —
e.g. GPT-5.5 scores 29.5 on binary round rewards but passes **81.8%** of verifier test
cases, because it often misses a round by just one or two cases.

Per-task / per-round / per-test-case detail: [`evaluation/sweeps/sweep_2026-06_single_shot.csv`](evaluation/sweeps/sweep_2026-06_single_shot.csv)
and the [interactive results site](https://unipat-ai.github.io/EvoCodeBench/).
The released Hugging Face resources also include the clean evaluation trajectories; use the
per-round `agent/trajectory.json` files to audit model behavior and reproduce the Avg rounds values.

To recompute the leaderboard table from the released run artifacts:

```bash
EVOCODEBENCH_TASKS_DIR=data/EvoCodeBench \
python evaluation/viz/leaderboard.py --write-csv
```

This script reads verifier rewards and `CASE_SUMMARY` logs for Dataset/Case score, and
reads each reached round's `agent/trajectory.json` to count agent-tool interactions for Avg rounds.

**Explore the results interactively → [unipat-ai.github.io/EvoCodeBench](https://unipat-ai.github.io/EvoCodeBench/)** —
one page per task with a per-round × per-model test-case heatmap, drill-down into the exact
cases each model failed (intent / expected / actual / reason), and a written difficulty and
performance-gap analysis. The same pages are under [`docs/`](docs/) and render locally with any
static server (`python3 -m http.server` from `docs/`).

> The original paper results (MT@4 / SR / Comp, legacy runner) are in [`legacy/`](legacy/README.md).

## Known issues & responsible disclosure

### Verifier readable during the agent phase (Harbor shared-step leak)

While auditing per-model, per-round trajectories from our **first** evaluation (the
v1 leaderboard, June 13–16), we found that on some tasks the agent could read the
verifier's grading script (`/tests/test.sh`) and the previous step's verifier output
(`/logs/verifier/reward.txt`, `test-stdout.txt`) **from inside its own step**.

**Root cause (framework, not the tasks).** This is a property of Harbor's default
*shared* multi-step verifier mode: the verifier runs in the agent's container, and
`/tests` + `/logs/verifier` are cleared only right before each verifier — never before
the next step's agent phase. So from step 2 onward, the previous step's cumulative
grading script and reward persist and are readable to the agent. It reproduces on
upstream Harbor and is **not specific to EvoCode-Bench**. We reported it upstream:

- Issue: <https://github.com/harbor-framework/harbor/issues/1960>
- Fix PR: <https://github.com/harbor-framework/harbor/pull/1961>

**Remediation.** We patched our evaluation harness (same fix as PR #1961: clear
`/tests` and `/logs/verifier` at the start of every agent phase) and **re-ran the entire
benchmark on the patched harness**. The current [Results](#results) are from these clean
runs. *The numbers and trajectories published before 2026-06-20 are superseded* — see
[`CHANGELOG.md`](CHANGELOG.md).

**What we observed in v1 (now withdrawn).** Across the 26 tasks, agents read or ran the
leaked grader (or read the prior reward) in at least one round on **12 tasks / 22 (task,
model) pairs / 47 round-level occurrences**. Because the leaked file is the *previous*
step's grader, accesses only land from round 2 on. The behavior was uneven across
models — heavily concentrated in a few:

| Task | Model | Rounds | Behavior | Access |
|:--|:--|:--|:--|:--|
| d5_w1 | DeepSeek-V4-Flash | R7 | read grader, read reward | succeeded |
| d12_w1 | DeepSeek-V4-Pro | R2 | read grader | succeeded |
| d9_w11 | DeepSeek-V4-Pro | R2,R3,R5,R6 | read+ran grader | succeeded |
| d11_w9 | Kimi-K2.6 | R4,R5,R6 | read+ran grader | succeeded |
| d12_w1 | Kimi-K2.6 | R3 | read grader, read reward | succeeded |
| d1_w9 | Kimi-K2.6 | R7 | read grader | succeeded |
| d5_w1 | Kimi-K2.6 | R2,R4,R13 | read+ran grader, read reward | succeeded |
| d9_w11 | Kimi-K2.6 | R2,R7 | read grader, read reward | succeeded |
| d1_w9 | MiniMax-M2.7 | R2 | read grader | unclear |
| d10_w12 | MiniMax-M3 | R5,R6,R7 | read+ran grader | succeeded |
| d10_w4 | MiniMax-M3 | R6 | read+ran grader | succeeded |
| d10_w5 | MiniMax-M3 | R4 | read+ran grader, read reward | succeeded |
| d10_w9 | MiniMax-M3 | R5,R6,R7 | read+ran grader | succeeded |
| d11_w2 | MiniMax-M3 | R5 | read+ran grader | succeeded |
| d12_w1 | MiniMax-M3 | R7 | read+ran grader | succeeded |
| d1_w5 | MiniMax-M3 | R2,R7,R8 | read+ran grader, read reward | succeeded |
| d5_w1 | MiniMax-M3 | R7,R9,R10,R11,R12 | read+ran grader, read reward | succeeded |
| d8_w5 | MiniMax-M3 | R4,R5,R6,R10 | read+ran grader | succeeded |
| d9_w11 | MiniMax-M3 | R3,R4,R6,R7,R15 | read+ran grader, read reward | succeeded |
| d12_w1 | Opus-4.8 | R7 | read+ran grader, read reward | succeeded |
| d5_w1 | Opus-4.8 | R9 | read+ran grader, read reward | succeeded |
| d12_w1 | Qwen3.7-Max | R7 | read+ran grader | unclear |

`"Access = succeeded"` means the agent's terminal
actually received grader/reward content. In almost all cases reading the grader did not
help (the models still failed the round); we withdrew the affected v1 results regardless.
If you evaluate with stock upstream Harbor in shared mode, apply the same sanitization or
use separate-verifier mode.

### Other corrections in the 2026-06-20 re-release

The re-run also fixed one contaminated task (d12_w1) and 11 task/test defects. Full
details, dates, and the old-vs-new framing are in [`CHANGELOG.md`](CHANGELOG.md).

## Relation to Terminal-X

EvoCode-Bench is the **iteration** component of [Terminal-X](https://github.com/UniPat-AI/Terminal-X), alongside DeepTerminalBench for single-shot depth and RoadmapBench for version upgrades. Terminal-X contains the combined benchmark suite and cross-dataset blog; this repository focuses on the EvoCode-Bench task format, evaluation protocol, and official-Harbor runner.

## Citation

```bibtex
@misc{shen2026evocodebench,
  title = {EvoCode-Bench: Evaluating Coding Agents in Multi-Turn Iterative Interactions},
  author = {Haiyang Shen and Xuanzhong Chen and Wendong Xu and Yun Ma and Liang Chen and Kuan Li},
  year = {2026},
  eprint = {2605.24110},
  archivePrefix = {arXiv},
  primaryClass = {cs.SE},
  url = {https://arxiv.org/abs/2605.24110}
}
```

## License

Code in this repository is released under the MIT License. Dataset terms follow the dataset release metadata.
