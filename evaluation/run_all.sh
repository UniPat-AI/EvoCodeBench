#!/usr/bin/env bash
# Run EvoCode-Bench on every task directory under a tasks root (official format).
#
# Usage:
#   ./evaluation/run_all.sh [tasks_dir] [oracle|nop|agent|all]
#
# Environment and options are forwarded through run_single.sh (AGENT_TYPE,
# AGENT_MODEL, AGENT_ATTEMPTS, AGENT_KWARGS, HARBOR_ENV, HARBOR_BIN, ...).

set -euo pipefail

TASKS_DIR="${1:-data/EvoCodeBench}"
MODE="${2:-agent}"

[ -d "${TASKS_DIR}" ] || { echo "ERROR: not a directory: ${TASKS_DIR}" >&2; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"

rc=0
for task in "${TASKS_DIR}"/theme_*; do
    [ -d "${task}" ] || continue
    [ -f "${task}/task.toml" ] || continue
    echo "===== $(basename "${task}") ====="
    "${HERE}/run_single.sh" "${task}" "${MODE}" || { echo "WARN: $(basename "${task}") exited non-zero" >&2; rc=1; }
done
exit "${rc}"
