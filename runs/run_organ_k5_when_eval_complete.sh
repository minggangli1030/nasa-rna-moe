#!/bin/bash
# Chain step 3: once the shuffled-mixed 20k evaluation completes, run the K=5 organ
# smoke/code test directly on the frozen recovered cohort
# (artifacts/stage1_organ_k5/organ_pilot_manifest.csv) instead of the older pilot
# manifest. This is a software + behavior sanity run on the real chosen five organs
# (brain, adipose, liver, skin, skeletal_muscle) BEFORE any longer multi-seed run;
# its losses are not authorized as biological evidence.
set -uo pipefail
cd "$(dirname "$0")/.."

EVAL_COMPLETE=results/mixed_20k_v3_shuffled_eval.COMPLETE
EVAL_EXIT=results/mixed_20k_v3_shuffled_eval.exit_code
MANIFEST=${MANIFEST:-artifacts/stage1_organ_k5/organ_pilot_manifest.csv}
STATUS=results/stage1_organ_k5_smoke.status
EXIT_CODE=results/stage1_organ_k5_smoke.exit_code
COMPLETE=results/stage1_organ_k5_smoke.COMPLETE
OUTPUT_POINTER=results/stage1_organ_k5_smoke.output_root
LOG=results/stage1_organ_k5_smoke_launch.log
POLL_SECONDS=${POLL_SECONDS:-300}
# Short but non-trivial budget so the comparison ladder is non-degenerate and we can
# eyeball whether experts start separating from pooled. Still a code test, not a run.
export MAX_UPDATES=${MAX_UPDATES:-300}

if [ -f "$COMPLETE" ]; then
    exit 0
fi
if [ ! -f "$MANIFEST" ]; then
    printf 'BLOCKED missing_manifest=%s %s\n' \
        "$MANIFEST" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    printf '1\n' > "$EXIT_CODE"
    exit 1
fi

printf 'WAITING_FOR_EVAL %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
while [ ! -f "$EVAL_COMPLETE" ]; do
    sleep "$POLL_SECONDS"
done

if [ -f "$EVAL_EXIT" ] && [ "$(cat "$EVAL_EXIT")" != "0" ]; then
    printf 'BLOCKED eval_exit=%s %s\n' \
        "$(cat "$EVAL_EXIT")" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    printf '1\n' > "$EXIT_CODE"
    exit 1
fi

OUTPUT_ROOT="results/stage1_organ_k5_smoke_$(date -u '+%Y%m%dT%H%M%SZ')"
printf 'RUNNING output=%s manifest=%s max_updates=%s %s\n' \
    "$OUTPUT_ROOT" "$MANIFEST" "$MAX_UPDATES" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
bash runs/run_organ_smoke.sh --output-root "$OUTPUT_ROOT" --manifest "$MANIFEST" > "$LOG" 2>&1
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
