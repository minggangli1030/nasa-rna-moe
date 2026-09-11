#!/bin/bash
# Remote idempotence wrapper used by the overnight evaluation watcher.
set -uo pipefail

cd "$(dirname "$0")/.."
mkdir -p results

STATUS=results/corrected_interspecies_eval.status
EXIT_CODE=results/corrected_interspecies_eval.exit_code
COMPLETE=results/corrected_interspecies_eval.COMPLETE
DRIVER_LOG=results/corrected_interspecies_eval_driver.log

if [ -f "$COMPLETE" ]; then
    exit 0
fi

rm -f "$EXIT_CODE"
printf 'RUNNING %s pid=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$$" > "$STATUS"

PYTHON=${PYTHON:-/home/exouser/moe-env/bin/python3} \
DEVICE=${DEVICE:-cuda:0} \
BATCH_SIZE=${BATCH_SIZE:-16} \
MASK_RATIO=${MASK_RATIO:-0.30} \
    bash runs/run_corrected_interspecies_eval.sh > "$DRIVER_LOG" 2>&1
rc=$?

printf '%s\n' "$rc" > "$EXIT_CODE"
if [ "$rc" -eq 0 ]; then
    printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    touch "$COMPLETE"
else
    printf 'FAILED %s rc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$rc" > "$STATUS"
fi
exit "$rc"
