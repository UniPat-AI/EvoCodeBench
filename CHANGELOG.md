# Changelog

All notable changes to the EvoCode-Bench dataset, evaluation harness, and published
results are recorded here. Dates are 2026.

---

## 2026-06-20 — Results re-release (v2): clean re-run on patched harness

This is a **correction release**. The leaderboard, per-task results, and trajectories
published before this date ("v1", June 13–16) are **superseded**. The v1 numbers were
affected by (a) one contaminated task, (b) several task/test defects, and (c) a Harbor
framework leak that let agents read the verifier during their own turn. All three are
fixed below; **every result on the current leaderboard comes from a full re-run on the
patched harness** (official Harbor multi-step, Daytona sandboxes, one attempt per task).

> **What changed for a reader of the numbers:** the headline table now reports
> post-fix numbers for **12 models**. Treat any EvoCode-Bench number dated before
> 2026-06-20 as outdated. See the [Results](README.md#results) table and the
> [interactive site](https://unipat-ai.github.io/EvoCodeBench/) for the current values.

### Fixed — evaluation integrity (Harbor shared-verifier leak)

- During the v1 evaluation, on some tasks the agent could **read the verifier's grading
  script** (`/tests/test.sh`) and the previous step's verifier output
  (`/logs/verifier/reward.txt`, `test-stdout.txt`) **from inside its own step**. Root
  cause is Harbor's default *shared* multi-step verifier mode: `/tests` and
  `/logs/verifier` are cleared only right before each verifier, never before the next
  step's agent phase, so round *N*'s grader persists into round *N+1*'s agent workspace.
- Reported upstream:
  [harbor issue #1960](https://github.com/harbor-framework/harbor/issues/1960),
  [fix PR #1961](https://github.com/harbor-framework/harbor/pull/1961).
- **Remediation:** our evaluation fork clears `/tests` and `/logs/verifier` at the start
  of every agent phase (same fix as #1961). The whole benchmark was re-run on the patched
  harness; published results are from these clean runs.
- **Observed in v1 (now invalid):** agents read or ran the leaked grader on **12 tasks /
  22 (task, model) pairs / 47 round-level occurrences**, concentrated in a few models
  (MiniMax-M3 most, then Kimi-K2.6, DeepSeek-V4-Pro, with single hits from Opus-4.8,
  DeepSeek-V4-Flash, Qwen3.7-Max, MiniMax-M2.7). Full per-(task, model, round) list in the
  README "Known issues & responsible disclosure" section. These v1 trajectories are
  **withdrawn**.

### Fixed — contaminated task

- `theme_d12_w1_automation_productivity_greenfield_implementation` shipped a late-round
  answer inside its starter `environment/` (the round-7 `cmd/flowr/main.go`
  implementation). Replaced with a 34-line skeleton; re-validated **oracle = 7/7,
  nop = 0/7**. A full 26-task contamination audit (one reviewer per task, comparing each
  task's `environment/` sources against every round's `solve.sh`) confirmed **only
  d12_w1 was affected; the other 25 tasks are clean.**

### Fixed — task / test defects (11 tasks)

Instruction-clarity and test-script defects that blocked otherwise-correct solutions or
mis-scored rounds. Each fix was re-validated against oracle (full pass) and nop (0):

| Task | Defect | Fix |
|:--|:--|:--|
| d1_w1 | `test.sh` only rebuilt the binary if it was absent → rounds 6–9 graded stale code | rebuild every round |
| d10_w2 | `steps` array-vs-map ambiguity made the round unwinnable | instruction: `steps` is a JSON array |
| d8_w5 | round-1 grants state-dir freedom but round-2 test hardcodes a path | instruction: canonical `/app/.pipeline` state dir |
| d7_w5 | circuit-breaker `open`→`half_open` timing + unspecified IPC JSON schema | `test.sh` accepts `open`/`half_open`; instruction pins the IPC schema |
| d10_w11 | `artifacts --list` `{entries:[]}` shape unspecified | instruction pins the entries shape |
| d1_w5 | imported-target CWD unspecified, blocking all round 2+ | instruction pins CWD |
| d11_w2 | matrix numeric-format regex too strict | broadened the accepted numeric formats |
| d5_w9 | round-15 enum message comma-spacing mismatch | instruction matches the asserted format |
| d10_w4 | created/removed messages + a broken `c029` grep | fixed messages and the test grep |
| d1_w11 | cached-build string + transitive mtime wording | clarified instruction |
| d10_w8 | round-8 / round-2 truncation asserts unspecified | instruction pins the raw-map audit |

### Changed — new models

- New models added vs v1: **Kimi-K2.7-Code, GLM-5.2** (alongside the 10 v1 models).

### Notes — results that are valid as scored (not defects)

- **d7_w5 and other long tasks are a 30-minute-per-round time-budget capability wall.**
  Weaker models exhaust the 1800 s/round agent budget without converging
  (`AgentTimeoutError`) and the chain aborts; frontier models finish all rounds (also
  scoring 0 on this task). Both outcomes score 0 — this is a valid capability result, not
  a bug. Timed-out / aborted / never-reached rounds count as 0.
- **kimi-k2.7-code on d7_w5** repeatedly emitted an empty assistant message (gateway
  healthy), failing the task by its own behavior. Scored 0, like a timeout.

### Withdrawn data

- All v1 trajectories and per-task results (June 13–16) — superseded by the 2026-06-20
  re-run. The pre-fix tasks and runs are archived under
  [`legacy/`](legacy/README.md) (`evocodebench_legacy_preisofix`) for reference.
- The v1 leak-affected trajectories (12 tasks / 22 pairs above) specifically.

---

## 2026-06-13 — Initial public release (v1)

- 26 multi-turn coding tasks, 227 rounds, Harbor official multi-step format.
- Leaderboard for 10 models. **Superseded by the 2026-06-20 re-release** (see above).
