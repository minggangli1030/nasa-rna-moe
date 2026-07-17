#!/bin/bash
# Chain step 4: the ACTUAL K=5 organ training run. Fires only after the K=5
# smoke/code test completes AND passes its mechanical health check, so we never
# spend a real training budget on a broken pipeline. Same five organs
# (brain, adipose, liver, skin, skeletal_muscle) on the frozen recovered cohort,
# but with a real per-expert budget and periodic best-validation checkpointing.
# This is a first real behaviour run (single seed); multi-seed rigor for a
# definitive claim comes later (Gate 1), after the PI meeting / GTEx decision.
set -uo pipefail
cd "$(dirname "$0")/.."

SMOKE_COMPLETE=results/stage1_organ_k5_smoke.COMPLETE
SMOKE_EXIT=results/stage1_organ_k5_smoke.exit_code
SMOKE_OUTPUT_POINTER=results/stage1_organ_k5_smoke.output_root
MANIFEST=${MANIFEST:-artifacts/stage1_organ_k5/organ_pilot_manifest.csv}
STATUS=results/stage1_organ_k5_train.status
EXIT_CODE=results/stage1_organ_k5_train.exit_code
COMPLETE=results/stage1_organ_k5_train.COMPLETE
OUTPUT_POINTER=results/stage1_organ_k5_train.output_root
LOG=results/stage1_organ_k5_train_launch.log
POLL_SECONDS=${POLL_SECONDS:-300}

# Real training budget for the actual run.
export RUN_MODE=full
export MAX_UPDATES=${MAX_UPDATES:-1500}
export VALIDATION_INTERVAL=${VALIDATION_INTERVAL:-150}
export BOOTSTRAP_REPS=${BOOTSTRAP_REPS:-2000}

if [ -f "$COMPLETE" ]; then
    exit 0
fi

printf 'WAITING_FOR_SMOKE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
while [ ! -f "$SMOKE_COMPLETE" ]; do
    sleep "$POLL_SECONDS"
done

# Gate: the smoke must have exited cleanly.
if [ -f "$SMOKE_EXIT" ] && [ "$(cat "$SMOKE_EXIT")" != "0" ]; then
    printf 'BLOCKED smoke_exit=%s %s\n' \
        "$(cat "$SMOKE_EXIT")" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    printf '1\n' > "$EXIT_CODE"
    exit 1
fi

# Gate: the smoke's mechanical health check must report pass.
SMOKE_ROOT="$(cat "$SMOKE_OUTPUT_POINTER" 2>/dev/null || true)"
HEALTH="$SMOKE_ROOT/mechanical_health.json"
if [ -z "$SMOKE_ROOT" ] || [ ! -f "$HEALTH" ]; then
    printf 'BLOCKED missing_health=%s %s\n' \
        "$HEALTH" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    printf '1\n' > "$EXIT_CODE"
    exit 1
fi
health_status="$("${PYTHON_BIN:-python3}" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' "$HEALTH" 2>/dev/null || true)"
if [ "$health_status" != "pass" ]; then
    printf 'BLOCKED smoke_health=%s %s\n' \
        "$health_status" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    printf '1\n' > "$EXIT_CODE"
    exit 1
fi

OUTPUT_ROOT="results/stage1_organ_k5_train_$(date -u '+%Y%m%dT%H%M%SZ')"
printf 'RUNNING output=%s manifest=%s max_updates=%s val_interval=%s %s\n' \
    "$OUTPUT_ROOT" "$MANIFEST" "$MAX_UPDATES" "$VALIDATION_INTERVAL" \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
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
