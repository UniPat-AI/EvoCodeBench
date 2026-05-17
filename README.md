<div align="center">

<h1>
  <img src="assets/hero.png" alt="EvoCode-Bench logo" width="42" />
  EvoCode-Bench: Evaluating Coding Agents in Multi-Turn Iterative Interactions
</h1>

![Dataset](https://img.shields.io/badge/Dataset-TBD-orange?style=for-the-badge)
[![GitHub](https://img.shields.io/badge/GitHub-EvoCodeBench-24292F?style=for-the-badge&logo=github&logoColor=white)](https://github.com/UniPat-AI/EvoCodeBench)
![Paper](https://img.shields.io/badge/Paper-arXiv_TBD-b91c1c?style=for-the-badge)
[![More Work](https://img.shields.io/badge/More_Work-Terminal--X-24292F?style=for-the-badge&logo=github&logoColor=white)](https://github.com/UniPat-AI/Terminal-X)
[![Framework](https://img.shields.io/badge/Framework-Harbor_Multi--Turn-blue?style=for-the-badge&logo=github&logoColor=white)](https://github.com/UniPat-AI/harbor_multiturn)
[![Leaderboard](https://img.shields.io/badge/Leaderboard-UniPat_AI-brightgreen?style=for-the-badge)](https://unipat.ai/benchmarks/EvoCode-Bench)

</div>

---

EvoCode-Bench tests whether coding agents can keep a project working as user requests change. It contains **26 stateful coding tasks** and **227 evaluated rounds**. Each task keeps the same workspace and agent session for **5-15 rounds**, while cumulative executable tests check new requirements and still-active prior requirements.

## Overview

Most coding benchmarks evaluate one specification followed by one final assessment. EvoCode-Bench instead evaluates an interactive coding session. Later rounds inherit earlier implementation decisions, dependencies, file layouts, API choices, and test behavior. Under fail-stop scoring, one regression can stop the rest of the trajectory.

The benchmark is organized along two axes from the paper:

| Engineering activity | Explorative | Contractual | Document-driven | Total |
|:--|--:|--:|--:|--:|
| Construction | 9 / 80 | 3 / 37 | 1 / 7 | 13 / 124 |
| Spec Evolution | 1 / 8 | 1 / 7 | 1 / 7 | 3 / 22 |
| Review | 3 / 21 | 1 / 7 | 1 / 9 | 5 / 37 |
| Migration | 3 / 29 | 1 / 7 | 1 / 8 | 5 / 44 |
| **Total** | **16 / 138** | **6 / 58** | **4 / 31** | **26 / 227** |

Each cell reports **tasks / rounds**.

## Task Format

EvoCode-Bench extends the Harbor task format with explicit round directories:

```text
task/
├── task.toml                    # metadata, round count, change types
├── instruction.md               # top-level task statement
├── environment/
│   └── Dockerfile               # shared Docker environment
├── round_1/
│   ├── instruction.md           # round-specific user request
│   ├── solution/solve.sh        # reference delta for this round
│   └── tests/test.sh            # cumulative tests through round 1
├── round_2/
│   ├── instruction.md
│   ├── solution/solve.sh
│   └── tests/test.sh            # cumulative tests through round 2
└── round_N/
```

The task format is built around three constraints:

- **Persistent workspace**: the same Docker container carries files, dependencies, and generated artifacts across rounds.
- **Continuous agent session**: the agent receives a sequence of user requests rather than independent prompts.
- **Cumulative tests**: round `i` verifies every still-active requirement from rounds `1..i`, so regressions are caught immediately.

## Harbor Multi-Turn

EvoCode-Bench requires the multi-turn Harbor fork:

```bash
git clone git@github.com:UniPat-AI/harbor_multiturn.git /path/to/harbor_multiturn
export HARBOR_MULTITURN_REPO=/path/to/harbor_multiturn
```

`harbor_multiturn` is the evaluation scaffold used by the paper. It adds:

- round boundary orchestration;
- persistent Docker workspace state;
- continuous agent-session state for multi-round runs;
- cumulative verifier swaps per round;
- reference fast-forwarding for SR-style single-round evaluation;
- snapshot/resume lineage for long runs;
- fail-stop reward aggregation into `verifier/multiround_results.json` and `verifier/reward.txt`.

## Quick Start

### 1. Prerequisites

```bash
# uv is used to run the Harbor CLI from the harbor_multiturn checkout.
# See https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone git@github.com:UniPat-AI/harbor_multiturn.git /path/to/harbor_multiturn
export HARBOR_MULTITURN_REPO=/path/to/harbor_multiturn
```

You also need Docker running and an OpenAI-compatible model endpoint.

### 2. Prepare Tasks

Place the released EvoCode-Bench task directories under `data/EvoCodeBench`.

If you already have the Terminal-X repository, the tasks are also available under:

```text
Terminal-X/data/EvoCodeBench/
```

### 3. Configure Model Endpoint

For the default `terminus-2` agent:

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_API_BASE="https://api.your-provider.com/v1"
export AGENT_MODEL="openai/gpt-5.5"
```

Optional:

```bash
export AGENT_TYPE="terminus-2"
export AGENT_ATTEMPTS=4
export HARBOR_N_CONCURRENT=4
```

### 4. Validate the Dataset

```bash
python evaluation/validate_dataset.py data/EvoCodeBench
```

The released benchmark should report **26 tasks** and **227 rounds**.

### 5. Run One Task

```bash
AGENT_MODEL=openai/gpt-5.5 AGENT_ATTEMPTS=4 \
  ./evaluation/run_multiround_single.sh data/EvoCodeBench/theme_d1_w1_code_build_greenfield_implementation agent
```

Oracle verification:

```bash
./evaluation/run_multiround_single.sh data/EvoCodeBench/theme_d1_w1_code_build_greenfield_implementation oracle
```

### 6. Run All Tasks

```bash
AGENT_MODEL=openai/gpt-5.5 AGENT_ATTEMPTS=4 \
  ./evaluation/run_all.sh data/EvoCodeBench agent
```

By default, each task writes Harbor outputs under:

```text
data/EvoCodeBench/<task>/harbor_jobs/<model>/
```

## Single-Round Fast-Forward

The paper reports SR as a complementary metric: the agent solves a target round after Harbor fast-forwards all previous rounds with reference deltas.

Run only round 5 from a reference-completed prior state:

```bash
AGENT_MODEL=openai/gpt-5.5 \
  ./evaluation/run_multiround_single.sh data/EvoCodeBench/theme_d1_w1_code_build_greenfield_implementation \
    agent --start-round 5 --max-round 5
```

Run rounds 3-7 after fast-forwarding rounds 1-2:

```bash
AGENT_MODEL=openai/gpt-5.5 \
  ./evaluation/run_multiround_single.sh data/EvoCodeBench/theme_d1_w1_code_build_greenfield_implementation \
    agent --start-round 3 --max-round 7
```

## Metrics

For task `t` with `N_t` rounds, let `r_{t,a,i}` be the cumulative verifier reward for attempt `a` at round `i`. Under fail-stop scoring, failed or unexecuted future rounds count as zero.

The main paper reports:

- **MT@4**: `mean_t (1/N_t) sum_i max_{a<=4} r_{t,a,i}`
- **SR**: single-round pass rate after reference fast-forwarding earlier rounds
- **Comp**: fraction of tasks completed through the final round in at least one attempt

Compute aggregate metrics from Harbor outputs:

```bash
python evaluation/compute_metrics.py \
  --tasks-dir data/EvoCodeBench \
  --results-dir data/EvoCodeBench
```

JSON output:

```bash
python evaluation/compute_metrics.py \
  --tasks-dir data/EvoCodeBench \
  --results-dir data/EvoCodeBench \
  --json
```

## Results

<p align="center">
  <img src="assets/main_results.png" width="100%" alt="EvoCode-Bench main results">
</p>

Top-line paper results:

| Agent | MT@4 | SR | Comp |
|:--|--:|--:|--:|
| Claude-Opus-4.7 | 54.0 | 76.7 | 42.3 |
| GPT-5.5 | 52.4 | 74.4 | 38.5 |
| Claude-Opus-4.6 | 44.0 | 78.9 | 34.6 |

SR exceeds MT@4 by 22-40 points for most agents. Isolated round-solving is much easier than keeping the agent's own workspace correct across many rounds.

<p align="center">
  <img src="assets/sr_vs_mt_by_round.png" width="100%" alt="SR versus MT by round">
</p>

## Relation to Terminal-X

EvoCode-Bench is the **iteration** component of [Terminal-X](https://github.com/UniPat-AI/Terminal-X), alongside DeepTerminalBench for single-shot depth and RoadmapBench for version upgrades. Terminal-X contains the combined benchmark suite and cross-dataset blog; this repository focuses on the EvoCode-Bench task format, evaluation protocol, and multi-turn runner.

## Citation

```bibtex
@misc{evocodebench2026,
  title  = {EvoCode-Bench: Evaluating Coding Agents in Multi-Turn Iterative Interactions},
  author = {UniPat AI Coding Team},
  year   = {2026},
  url    = {https://github.com/UniPat-AI/EvoCodeBench}
}
```

## License

Code in this repository is released under the MIT License. Dataset terms follow the dataset release metadata.
