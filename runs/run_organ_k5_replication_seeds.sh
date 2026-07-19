#!/usr/bin/env bash
# Frozen Stage 1 K=5 replication: train seeds 43 and 44, then evaluate all
# three seeds once. The original gates remain authoritative; the added direct
# organ-vs-random comparisons are explicitly non-gating diagnostics.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x /home/exouser/moe-env/bin/python3 ]]; then
    PYTHON_BIN=/home/exouser/moe-env/bin/python3
  else
    PYTHON_BIN=python3
  fi
fi

PROTOCOL=artifacts/stage1_organ_k5/replication_protocol.json
MANIFEST=artifacts/stage1_organ_k5/organ_pilot_manifest.csv
EXPECTED_MANIFEST_SHA256=25c62b071720117721a24930945fbd4c8c7cdc4a2a81ae003a920e9402441d5b
BASE_ROOT=results/stage1_organ_k5_train_20260717T165507Z
BASE_EVALUATION="$BASE_ROOT/evaluation_replication_v2"
RUN_ROOT=results/stage1_organ_k5_replication
STATUS="$RUN_ROOT/STATUS"
EXIT_CODE="$RUN_ROOT/exit_code"
COMPLETE="$RUN_ROOT/COMPLETE"
DECISION="$RUN_ROOT/three_seed_decision.json"
LOCK_DIR="$RUN_ROOT/launch.lock"
CODE_COMMIT="${CODE_COMMIT:-unknown}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"
SEEDS=(43 44)

mkdir -p "$RUN_ROOT"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "ERROR: replication launcher lock already exists: $LOCK_DIR" >&2
  exit 1
fi
cleanup_lock() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup_lock EXIT

set_status() {
  printf '%s %s\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
}
fail() {
  code="$1"
  shift
  printf '%s\n' "$code" > "$EXIT_CODE"
  set_status "FAILED rc=$code reason=$*"
  exit "$code"
}
require_file() {
  [[ -s "$1" ]] || fail 1 "missing_file=$1"
}

if [[ -f "$COMPLETE" ]]; then
  require_file "$DECISION"
  exit 0
fi

for path in \
  "$PROTOCOL" \
  "$MANIFEST" \
  "$BASE_ROOT/prediction_cache.npz" \
  runs/run_organ_smoke.sh \
  evaluation/evaluate_organ_moe.py \
  evaluation/check_organ_smoke_health.py \
  evaluation/decide_organ_specialization.py; do
  require_file "$path"
done
[[ -f "$BASE_ROOT/COMPLETE" ]] || fail 1 "missing_marker=$BASE_ROOT/COMPLETE"

actual_manifest_sha256="$(sha256sum "$MANIFEST" | awk '{print $1}')"
if [[ "$actual_manifest_sha256" != "$EXPECTED_MANIFEST_SHA256" ]]; then
  fail 1 "manifest_sha256=$actual_manifest_sha256"
fi

"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["training_seeds"] == [42,43,44]; assert p["new_training_seeds"] == [43,44]; assert p["original_gate_policy"]["unchanged"] is True; assert p["exploratory_direct_random_control"]["gating"] is False' \
  "$PROTOCOL" || fail 1 "invalid_replication_protocol"

available_kb="$(df -Pk "$RUN_ROOT" | awk 'NR==2 {print $4}')"
if [[ -z "$available_kb" || "$available_kb" -lt 41943040 ]]; then
  fail 1 "insufficient_disk_kb=${available_kb:-unknown}"
fi

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "REPLICATION_PREFLIGHT_OK"
  echo "python=$PYTHON_BIN"
  echo "base_root=$BASE_ROOT"
  echo "manifest_sha256=$actual_manifest_sha256"
  echo "available_kb=$available_kb"
  echo "seeds=${SEEDS[*]}"
  exit 0
fi

printf '{"schema_version":1,"code_commit":"%s","protocol":"%s","manifest_sha256":"%s","launched_at_utc":"%s"}\n' \
  "$CODE_COMMIT" "$PROTOCOL" "$actual_manifest_sha256" \
  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$RUN_ROOT/launch_provenance.json"

set_status "RUNNING phase=reevaluate_seed42"
if [[ ! -s "$BASE_EVALUATION/report.json" ]]; then
  mkdir -p "$BASE_EVALUATION"
  "$PYTHON_BIN" evaluation/evaluate_organ_moe.py \
    --cache "$BASE_ROOT/prediction_cache.npz" \
    --output-dir "$BASE_EVALUATION" \
    --train-split train \
    --calibration-split calibration \
    --test-split test \
    --seed 271828 \
    --training-seed 42 \
    --bootstrap-reps 2000 \
    > "$RUN_ROOT/seed42_reevaluation.log" 2>&1 \
    || fail 1 "seed42_reevaluation"
fi
"$PYTHON_BIN" evaluation/check_organ_smoke_health.py \
  --report "$BASE_EVALUATION/report.json" \
  --output "$BASE_EVALUATION/mechanical_health.json" \
  > "$RUN_ROOT/seed42_health.log" 2>&1 \
  || fail 1 "seed42_health"

for seed in "${SEEDS[@]}"; do
  output="results/stage1_organ_k5_train_seed${seed}_v1"
  log="$RUN_ROOT/seed${seed}.log"
  if [[ -f "$output/COMPLETE" && -s "$output/evaluation/report.json" ]]; then
    set_status "RUNNING phase=seed${seed}_already_complete"
  else
    if [[ -e "$output" ]]; then
      fail 1 "incomplete_output_exists=$output"
    fi
    available_kb="$(df -Pk "$RUN_ROOT" | awk 'NR==2 {print $4}')"
    if [[ -z "$available_kb" || "$available_kb" -lt 20971520 ]]; then
      fail 1 "insufficient_disk_before_seed${seed}_kb=${available_kb:-unknown}"
    fi
    set_status "RUNNING phase=train_seed${seed} output=$output"
    env \
      RUN_MODE=full \
      TRAIN_SEED="$seed" \
      PROTOCOL_SEED=314159 \
      MASK_SEED=271828 \
      MAX_UPDATES=1500 \
      VALIDATION_INTERVAL=150 \
      BOOTSTRAP_REPS=2000 \
      bash runs/run_organ_smoke.sh \
        --output-root "$output" \
        --manifest "$MANIFEST" \
        > "$log" 2>&1 \
      || fail 1 "seed${seed}_training_or_evaluation"
  fi
  "$PYTHON_BIN" -c \
    'import json,sys; r=json.load(open(sys.argv[1])); assert r["training_seed"] == int(sys.argv[2]); assert r["schema_version"] >= 2; assert r["exploratory_random_controls"]["gating"] is False' \
    "$output/evaluation/report.json" "$seed" \
    || fail 1 "seed${seed}_report_validation"
done

set_status "RUNNING phase=three_seed_decision"
"$PYTHON_BIN" evaluation/decide_organ_specialization.py \
  --report "$BASE_EVALUATION/report.json" \
  --report results/stage1_organ_k5_train_seed43_v1/evaluation/report.json \
  --report results/stage1_organ_k5_train_seed44_v1/evaluation/report.json \
  --min-seeds 3 \
  --output "$DECISION" \
  > "$RUN_ROOT/three_seed_decision.log" 2>&1 \
  || fail 1 "three_seed_decision"

printf '0\n' > "$EXIT_CODE"
touch "$COMPLETE"
set_status "COMPLETE decision=$DECISION"
