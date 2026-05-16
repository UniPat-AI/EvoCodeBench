#!/usr/bin/env bash
# ==============================================================================
# EvoCode-Bench multi-round single-task runner
# ==============================================================================
#
# Usage:
#   ./eval/run_multiround_single.sh <task_path> [oracle|agent|all] [options]
#
# Modes:
#   all     Run oracle first, then agent (default).
#   oracle  Verify the reference round chain.
#   agent   Run the configured coding agent.
#
# Options:
#   --start-round N
#       Fast-forward rounds 1..N-1 with reference deltas, then start the agent
#       at round N. This is used for SR-style single-round evaluation.
#   --max-round N
#       Stop after round N.
#   --resume-trial PATH --resume-round N
#       Continue a previous trial from a saved round-boundary state.
#   --continue-successes-per-round N
#       Keep N successful state lineages after each round. Default: 1.
#   --jobs-dir DIR
#       Override output directory. Default: <task>/harbor_jobs/<model>.
#
# Required environment:
#   HARBOR_MULTITURN_REPO  checkout of git@github.com:UniPat-AI/harbor_multiturn.git
#
# Common agent environment:
#   AGENT_TYPE      terminus-2 (default) | claude
#   AGENT_MODEL     LiteLLM model ID, e.g. openai/gpt-5.5
#   AGENT_ATTEMPTS  attempts per task, default 4 for MT@4
#   AGENT_KWARGS    JSON object rendered as repeated --agent-kwarg values
#   HARBOR_DELETE   true (default) | false
#
# For terminus-2, set OPENAI_API_KEY and OPENAI_API_BASE/OPENAI_BASE_URL for
# your OpenAI-compatible model endpoint. For claude, set ANTHROPIC_API_KEY.
# ==============================================================================

set -euo pipefail

HARBOR_REPO="${HARBOR_MULTITURN_REPO:-}"
[ -n "${HARBOR_REPO}" ] || { echo "ERROR: Set HARBOR_MULTITURN_REPO to your harbor_multiturn checkout." >&2; exit 1; }
HARBOR_REPO="$(cd "${HARBOR_REPO}" && pwd)"
HARBOR_CMD=(uv --directory "${HARBOR_REPO}" run harbor)

AGENT_TYPE="${AGENT_TYPE:-terminus-2}"
AGENT_MODEL="${AGENT_MODEL:-openai/gpt-5.5}"
AGENT_ATTEMPTS="${AGENT_ATTEMPTS:-4}"
AGENT_KWARGS="${AGENT_KWARGS:-}"
HARBOR_N_CONCURRENT="${HARBOR_N_CONCURRENT:-${AGENT_ATTEMPTS}}"
HARBOR_DELETE="${HARBOR_DELETE:-true}"

if [ -t 1 ]; then
    B=$'\033[34m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
else
    B=''; G=''; Y=''; R=''; N=''
fi
info() { printf '%b\n' "${B}[INFO]${N} $*"; }
ok()   { printf '%b\n' "${G}[OK]${N}   $*"; }
warn() { printf '%b\n' "${Y}[WARN]${N} $*"; }
err()  { printf '%b\n' "${R}[ERR]${N}  $*"; }

show_help() { sed -n '2,/^set -euo pipefail/{/^#/!d; s/^# \{0,1\}//p}' "$0"; }
is_posint() { [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -gt 0 ]; }

parse_agent_kwargs() {
    local -n out="$1"
    [ -z "${AGENT_KWARGS}" ] && return 0
    local rendered
    if ! rendered="$(python3 -c '
import json, os, sys
raw = os.environ.get("AGENT_KWARGS", "").strip()
if not raw:
    sys.exit(0)
d = json.loads(raw)
if not isinstance(d, dict):
    raise SystemExit("AGENT_KWARGS must be a JSON object")
for k, v in d.items():
    print(f"{k}={json.dumps(v, ensure_ascii=False, separators=(\",\",\":\"))}")
' 2>&1)"; then
        err "AGENT_KWARGS is not valid JSON: ${rendered}"
        exit 1
    fi
    local line
    while IFS= read -r line; do
        [ -n "${line}" ] && out+=(--agent-kwarg "${line}")
    done <<< "${rendered}"
}

run_harbor() {
    local mode="$1"
    local agent model attempts
    if [ "${mode}" = "oracle" ]; then
        agent="oracle"
        model="oracle"
        attempts=1
    else
        agent="${AGENT_TYPE}"
        model="${AGENT_MODEL}"
        attempts="${AGENT_ATTEMPTS}"
    fi

    local jobs_dir
    if [ -n "${RESUME_TRIAL}" ]; then
        jobs_dir="$(cd "$(dirname "$(dirname "${RESUME_TRIAL}")")" && pwd)"
    elif [ -n "${JOBS_DIR_OVERRIDE}" ]; then
        jobs_dir="${JOBS_DIR_OVERRIDE}"
        mkdir -p "${jobs_dir}"
    else
        local sub="${model##*/}"
        [ "${mode}" = "oracle" ] && sub="oracle"
        jobs_dir="${TASK_PATH}/harbor_jobs/${sub}"
        mkdir -p "${jobs_dir}"
    fi

    local -a kwargs_args=()
    [ "${mode}" = "agent" ] && parse_agent_kwargs kwargs_args

    local -a delete_args=()
    [ "${HARBOR_DELETE}" = "false" ] && delete_args=(--no-delete)

    local -a cmd=(
        "${HARBOR_CMD[@]}" run
        --path "${TASK_PATH}"
        --agent "${agent}"
        --model "${model}"
        --n-attempts "${attempts}"
        --n-concurrent "${HARBOR_N_CONCURRENT}"
        "${delete_args[@]}"
        "${kwargs_args[@]}"
        --jobs-dir "${jobs_dir}"
    )
    [ -n "${START_ROUND}" ] && cmd+=(--start-round "${START_ROUND}")
    [ -n "${MAX_ROUND}" ] && cmd+=(--max-round "${MAX_ROUND}")
    [ -n "${RESUME_TRIAL}" ] && cmd+=(--resume-trial "${RESUME_TRIAL}" --resume-round "${RESUME_ROUND}")
    [ -n "${CONTINUE_SUCCESSES}" ] && cmd+=(--multiround-continue-successes-per-round "${CONTINUE_SUCCESSES}")

    info "[${mode}] ${cmd[*]}"
    set +e
    "${cmd[@]}"
    local rc=$?
    set -e
    [ "${rc}" -eq 0 ] && ok "[${mode}] done" || warn "[${mode}] exit code ${rc}"
    return "${rc}"
}

[ $# -ge 1 ] || { show_help; exit 1; }
[[ "$1" =~ ^(-h|--help|help)$ ]] && { show_help; exit 0; }

TASK_PATH="$1"
shift
[ -d "${TASK_PATH}" ] || { err "not a directory: ${TASK_PATH}"; exit 1; }
TASK_PATH="$(cd "${TASK_PATH}" && pwd)"
[ -f "${TASK_PATH}/task.toml" ] || { err "missing task.toml in ${TASK_PATH}"; exit 1; }

COMMAND="all"
if [ $# -gt 0 ] && [[ ! "$1" =~ ^- ]]; then
    COMMAND="$1"
    shift
fi
case "${COMMAND}" in
    oracle|agent|all) ;;
    *) err "unknown command: ${COMMAND}"; exit 1 ;;
esac

START_ROUND=""
MAX_ROUND=""
RESUME_TRIAL=""
RESUME_ROUND=""
CONTINUE_SUCCESSES="1"
JOBS_DIR_OVERRIDE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --start-round) START_ROUND="$2"; shift 2 ;;
        --max-round) MAX_ROUND="$2"; shift 2 ;;
        --resume-trial) RESUME_TRIAL="$2"; shift 2 ;;
        --resume-round) RESUME_ROUND="$2"; shift 2 ;;
        --continue-successes-per-round) CONTINUE_SUCCESSES="$2"; shift 2 ;;
        --jobs-dir) JOBS_DIR_OVERRIDE="$2"; shift 2 ;;
        -h|--help) show_help; exit 0 ;;
        *) err "unknown option: $1"; exit 1 ;;
    esac
done

[ -n "${START_ROUND}" ] && { is_posint "${START_ROUND}" || { err "--start-round must be >= 1"; exit 1; }; }
[ -n "${MAX_ROUND}" ] && { is_posint "${MAX_ROUND}" || { err "--max-round must be >= 1"; exit 1; }; }
if [ -n "${START_ROUND}" ] && [ -n "${MAX_ROUND}" ] && [ "${START_ROUND}" -gt "${MAX_ROUND}" ]; then
    err "--start-round (${START_ROUND}) > --max-round (${MAX_ROUND})"
    exit 1
fi
if [ -n "${RESUME_TRIAL}" ]; then
    [[ "${RESUME_TRIAL}" = /* ]] || RESUME_TRIAL="${TASK_PATH}/${RESUME_TRIAL}"
    [ -d "${RESUME_TRIAL}" ] || { err "resume-trial not found: ${RESUME_TRIAL}"; exit 1; }
    [ -n "${RESUME_ROUND}" ] || { err "--resume-trial requires --resume-round"; exit 1; }
    is_posint "${RESUME_ROUND}" && [ "${RESUME_ROUND}" -ge 2 ] || { err "--resume-round must be >= 2"; exit 1; }
    [ -z "${START_ROUND}" ] || { err "--start-round and --resume-trial are mutually exclusive"; exit 1; }
fi

info "Task:    $(basename "${TASK_PATH}")"
info "Command: ${COMMAND}"
info "Agent:   ${AGENT_TYPE} | model=${AGENT_MODEL} | attempts=${AGENT_ATTEMPTS}"

rc=0
case "${COMMAND}" in
    oracle) run_harbor oracle || rc=1 ;;
    agent) run_harbor agent || rc=1 ;;
    all) run_harbor oracle || rc=1; run_harbor agent || rc=1 ;;
esac
exit "${rc}"

