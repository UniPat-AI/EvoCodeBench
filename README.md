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

> The paper's MT@4 / SR / Comp metrics and single-round fast-forward evaluation live
> in [`legacy/`](legacy/README.md).

## Results

Evaluated on the current dataset release with the Harbor official multi-step runner:
full 5–15 round chains, **one attempt per task** (no best-of-k). The score is the
**dataset score** defined in [Metrics](#metrics) — the mean over 26 tasks of each
task's `passed_steps / total_steps`. All cells are from complete chains; `oracle`
scores 1.0 and `nop` scores 0 on every task.

| Agent | Reasoning | Dataset score | Case score | Perfect tasks |
|:--|:--|--:|--:|--:|
| Claude-Opus-4.8 | effort `xhigh` | 42.5 | 89.9 | 6/26 |
| GPT-5.5 | effort `high` | 23.5 | 77.2 | 0/26 |
| Kimi-K2.6 | thinking on¹ | 23.1 | 75.2 | 1/26 |
| MiniMax-M3 | thinking `adaptive` | 15.2 | 69.2 | 1/26 |
| DeepSeek-V4-Pro | effort `high` | 10.8 | 58.3 | 0/26 |
| Qwen3.6-Plus | thinking on¹ | 10.1 | 64.4 | 1/26 |
| Qwen3.7-Max | thinking on¹ | 7.6 | 64.7 | 0/26 |
| GLM-5.1 | thinking on¹ | 6.3 | 48.4 | 0/26 |
| DeepSeek-V4-Flash | effort `high` | 4.6 | 52.5 | 0/26 |
| MiniMax-M2.7 | reasoning split | 0.8 | 42.6 | 0/26 |

*Dataset score* is the mean per-task score ×100, where a task's score is `passed_rounds / total_rounds`
and a round is "passed" only if it earns the binary reward 1 (**every** test case of that round passes).

*Case score* is the finer-grained companion. For each task, take each round's
`passed_test_cases / total_test_cases`, average over the task's rounds (a round whose code fails to build,
or that the chain never reached, counts as 0), then average over the 26 tasks ×100. It credits the partial
progress the all-or-nothing round reward hides — e.g. GPT-5.5 scores 23.5 on rounds but passes **77.2%** of
test cases, because it often misses a round by just one or two cases. Both scores rank Opus-4.8 first, but
the case score spreads the field more smoothly.

*Reasoning* is the thinking configuration used for each model: models with an effort knob ran at the
listed level (Opus at its highest, `xhigh`; the rest at `high`); ¹ models without an
effort knob ran with their native thinking simply enabled (Qwen `enable_thinking`,
GLM/Kimi `thinking.type=enabled`), and MiniMax M3/M2.7 used their adaptive / split
reasoning modes. All agents used the `terminus-2` scaffold.
Per-task / per-round / per-test-case detail: [`evaluation/sweeps/sweep_2026-06_single_shot.csv`](evaluation/sweeps/sweep_2026-06_single_shot.csv)
and the [interactive results site](https://unipat-ai.github.io/EvoCodeBench/).

**Explore the results interactively → [unipat-ai.github.io/EvoCodeBench](https://unipat-ai.github.io/EvoCodeBench/)** —
one page per task with a per-round × per-model test-case heatmap, drill-down into the exact
cases each model failed (intent / expected / actual / reason), and a written difficulty and
performance-gap analysis. The same pages are under [`docs/`](docs/) and render locally with any
static server (`python3 -m http.server` from `docs/`).

> The original paper results (MT@4 / SR / Comp, legacy runner) are in [`legacy/`](legacy/README.md).

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
