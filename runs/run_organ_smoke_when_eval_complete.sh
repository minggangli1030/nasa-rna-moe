#!/bin/bash
# Launch the Stage 1 five-organ mechanical smoke once the shuffled-mixed 20k V3
# evaluation completes. This validates the complete software path only; it is not
# authorized as biological evidence. Follows the same gated-watcher pattern as
# evaluate_shuffled_mixed_when_complete.sh.
set -uo pipefail
cd "$(dirname "$0")/.."

EVAL_COMPLETE=results/mixed_20k_v3_shuffled_eval.COMPLETE
EVAL_EXIT=results/mixed_20k_v3_shuffled_eval.exit_code
STATUS=results/stage1_organ_smoke.status
EXIT_CODE=results/stage1_organ_smoke.exit_code
COMPLETE=results/stage1_organ_smoke.COMPLETE
OUTPUT_POINTER=results/stage1_organ_smoke.output_root
LOG=results/stage1_organ_smoke_launch.log
POLL_SECONDS=${POLL_SECONDS:-300}

if [ -f "$COMPLETE" ]; then
    exit 0
fi

printf 'WAITING_FOR_EVAL %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
while [ ! -f "$EVAL_COMPLETE" ]; do
    sleep "$POLL_SECONDS"
done

# Only proceed if the gating evaluation actually succeeded. A missing exit_code
# with a present COMPLETE marker is treated as success (the marker is only
# touched on rc==0 by the eval watcher).
if [ -f "$EVAL_EXIT" ] && [ "$(cat "$EVAL_EXIT")" != "0" ]; then
    printf 'BLOCKED eval_exit=%s %s\n' \
        "$(cat "$EVAL_EXIT")" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    printf '1\n' > "$EXIT_CODE"
    exit 1
fi

OUTPUT_ROOT="results/stage1_organ_smoke_$(date -u '+%Y%m%dT%H%M%SZ')"
printf 'RUNNING output=%s %s\n' "$OUTPUT_ROOT" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
bash runs/run_organ_smoke.sh --output-root "$OUTPUT_ROOT" > "$LOG" 2>&1
rc=$?

printf '%s\n' "$rc" > "$EXIT_CODE"
printf '%s\n' "$OUTPUT_ROOT" > "$OUTPUT_POINTER"
if [ "$rc" -eq 0 ]; then
    printf 'COMPLETE output=%s %s\n' \
        "$OUTPUT_ROOT" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    touch "$COMPLETE"
else
    printf 'FAILED rc=%s output=%s %s\n' \
        "$rc" "$OUTPUT_ROOT" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
fi
exit "$rc"
