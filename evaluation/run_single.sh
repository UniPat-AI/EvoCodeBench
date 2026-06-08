#!/usr/bin/env bash
# ==============================================================================
# EvoCode-Bench single-task runner — official Harbor multi-step format
# ==============================================================================
#
# Usage:
#   ./evaluation/run_single.sh <task_path> [oracle|nop|agent|all] [options]
#
# Modes:
#   all     Run oracle first, then agent (default).
#   oracle  Run the reference solutions (should score 1.0 on every step).
#   nop     Run the no-op agent (should score 0 — checks non-triviality).
#   agent   Run the configured coding agent.
#
# Options:
#   --start-step N   Run from step N. Steps 1..N-1 are prepared with the
#                    reference solutions via --fast-forward-mode oracle-solution
#                    (single-round / SR evaluation). NOTE: SR requires HARBOR_BIN
#                    pointed at the harbor-official-fast-forward fork
#                    (https://github.com/UniPat-AI/harbor-official-fast-forward);
#                    upstream Harbor does not yet support --fast-forward-mode.
#   --end-step M     Stop after step M.
#   --jobs-dir DIR   Override output directory. Default: <task>/harbor_jobs/<model>.
#
# Environment:
#   HARBOR_BIN       Harbor executable. Default: "harbor" (from `uv tool install harbor`
#                    or `pip install harbor`). May be a multi-word command, e.g.
#                    "uv --directory /path/to/harbor run harbor".
#   AGENT_TYPE       claude-code (default) | terminus-2 | codex | ...
#   AGENT_MODEL      Model id. Default: claude-opus-4-7.
#   AGENT_ATTEMPTS   Attempts per task. Default: 1 (set 4 for MT@4).
#   AGENT_KWARGS     JSON object rendered as repeated --agent-kwarg values,
#                    e.g. '{"reasoning_effort":"high"}'.
#   HARBOR_ENV       docker (default) | daytona | ...
#   HARBOR_N_CONCURRENT   Concurrent attempts. Default: AGENT_ATTEMPTS.
#
# Set the model credentials your agent needs (e.g. ANTHROPIC_BASE_URL /
# ANTHROPIC_AUTH_TOKEN for claude-code, or OPENAI_API_KEY / OPENAI_API_BASE for
# terminus-2) before running.
# ==============================================================================

set -euo pipefail

HARBOR_BIN="${HARBOR_BIN:-harbor}"
read -r -a HARBOR_CMD <<< "${HARBOR_BIN}"
AGENT_TYPE="${AGENT_TYPE:-claude-code}"
AGENT_MODEL="${AGENT_MODEL:-claude-opus-4-7}"
AGENT_ATTEMPTS="${AGENT_ATTEMPTS:-1}"
AGENT_KWARGS="${AGENT_KWARGS:-}"
HARBOR_ENV="${HARBOR_ENV:-docker}"
HARBOR_N_CONCURRENT="${HARBOR_N_CONCURRENT:-${AGENT_ATTEMPTS}}"

usage() { sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'; }

err() { printf 'ERROR: %s\n' "$*" >&2; }

[ $# -ge 1 ] || { usage; exit 1; }
case "$1" in -h|--help) usage; exit 0;; esac

TASK_PATH="$1"; shift
[ -d "${TASK_PATH}" ] || { err "not a directory: ${TASK_PATH}"; exit 1; }
TASK_PATH="$(cd "${TASK_PATH}" && pwd)"
[ -f "${TASK_PATH}/task.toml" ] || { err "missing task.toml in ${TASK_PATH}"; exit 1; }

MODE="all"
if [ $# -gt 0 ] && [[ "$1" != -* ]]; then MODE="$1"; shift; fi
case "${MODE}" in oracle|nop|agent|all) ;; *) err "unknown mode: ${MODE}"; usage; exit 1;; esac

START_STEP=""; END_STEP=""; JOBS_DIR_OVERRIDE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --start-step) START_STEP="$2"; shift 2 ;;
        --end-step)   END_STEP="$2"; shift 2 ;;
        --jobs-dir)   JOBS_DIR_OVERRIDE="$2"; shift 2 ;;
        -h|--help)    usage; exit 0 ;;
        *) err "unknown option: $1"; usage; exit 1 ;;
    esac
done

render_agent_kwargs() {
    [ -n "${AGENT_KWARGS}" ] || return 0
    python3 - "${AGENT_KWARGS}" <<'PY'
import json, sys
payload = json.loads(sys.argv[1])
assert isinstance(payload, dict), "AGENT_KWARGS must be a JSON object"
for key, value in payload.items():
    rendered = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
    print("--agent-kwarg")
    print(f"{key}={rendered}")
PY
}

run_one() {
    local role="$1" agent model attempts base jobs
    case "${role}" in
        oracle) agent="oracle"; model="oracle"; attempts=1 ;;
        nop)    agent="nop";    model="nop";    attempts=1 ;;
        agent)  agent="${AGENT_TYPE}"; model="${AGENT_MODEL}"; attempts="${AGENT_ATTEMPTS}" ;;
    esac
    base="${model##*/}"; [ -n "${base}" ] || base="${role}"
    jobs="${JOBS_DIR_OVERRIDE:-${TASK_PATH}/harbor_jobs/${base}}"
    mkdir -p "${jobs}"

    local -a cmd=(
        "${HARBOR_CMD[@]}" run
        --path "${TASK_PATH}"
        --agent "${agent}"
        --model "${model}"
        --n-attempts "${attempts}"
        --n-concurrent "${HARBOR_N_CONCURRENT}"
        --jobs-dir "${jobs}"
    )
    [ "${HARBOR_ENV}" != "docker" ] && cmd+=(--env "${HARBOR_ENV}")
    if [ "${role}" = "agent" ] && [ -n "${AGENT_KWARGS}" ]; then
        while IFS= read -r line; do [ -n "${line}" ] && cmd+=("${line}"); done < <(render_agent_kwargs)
    fi
    if [ -n "${START_STEP}" ]; then
        cmd+=(--start-step "${START_STEP}")
        if [ "${START_STEP}" -gt 1 ] 2>/dev/null; then
            cmd+=(--fast-forward-mode oracle-solution)
        fi
    fi
    [ -n "${END_STEP}" ] && cmd+=(--end-step "${END_STEP}")

    printf '[run_single] %s\n' "${cmd[*]}"
    "${cmd[@]}"
}

rc=0
case "${MODE}" in
    oracle) run_one oracle || rc=1 ;;
    nop)    run_one nop    || rc=1 ;;
    agent)  run_one agent  || rc=1 ;;
    all)    run_one oracle || rc=1; run_one agent || rc=1 ;;
esac
exit "${rc}"
