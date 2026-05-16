#!/usr/bin/env bash
# Run EvoCode-Bench on every task directory under data/EvoCodeBench.

set -euo pipefail

TASKS_DIR="${1:-data/EvoCodeBench}"
COMMAND="${2:-agent}"

[ -d "${TASKS_DIR}" ] || { echo "ERROR: not a directory: ${TASKS_DIR}" >&2; exit 1; }

for task in "${TASKS_DIR}"/theme_*; do
    [ -d "${task}" ] || continue
    [ -f "${task}/task.toml" ] || continue
    echo "===== $(basename "${task}") ====="
    "$(dirname "$0")/run_multiround_single.sh" "${task}" "${COMMAND}"
done
