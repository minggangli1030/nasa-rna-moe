#!/usr/bin/env bash
# Train the exact matched organ-K5 and frozen-random-K5 hard adapter banks.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_organ_k_confirmation/protocol.json}"
SOURCE_ROOT="${SOURCE_ROOT:-results/stage1_organ_k5_train_20260717T165507Z}"
EXPRESSION_PARQUET="${EXPRESSION_PARQUET:-$SOURCE_ROOT/expression/expression.parquet}"
EXPRESSION_METADATA="${EXPRESSION_METADATA:-$SOURCE_ROOT/expression/extraction_report.json}"
MANIFEST="${MANIFEST:-$SOURCE_ROOT/expression/manifest.parquet}"
POOLED_CHECKPOINT="${POOLED_CHECKPOINT:-$SOURCE_ROOT/models/pooled/best_model.pt}"
PARTITION_ROOT="${PARTITION_ROOT:-results/stage1_organ_k_confirmation/partitions}"
PARTITION_MANIFEST="${PARTITION_MANIFEST:-$PARTITION_ROOT/train_cal_partitions.parquet}"
PARTITION_REPORT="${PARTITION_REPORT:-$PARTITION_ROOT/partition_report.json}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-results/stage2_utility_axis_pilot_f8ab3cd/axis/axis_definitions.npz}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/stage1_organ_k_confirmation/packed}"
RUN_SEEDS="${RUN_SEEDS:-}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"
MAX_UPDATES_OVERRIDE="${MAX_UPDATES_OVERRIDE:-}"
SMOKE_ONLY="${SMOKE_ONLY:-0}"
CODE_COMMIT="${CODE_COMMIT:-unknown}"

EXPECTED_EXPRESSION_SHA256=148776bc2d5bbe4a969103de7abab932b7467c804934fc697366ae2c209c0821
EXPECTED_MANIFEST_SHA256=bc4e8e4e36ab0e869fd885197842dc797edad5a08b8093beb21185dbeda7f9cc
EXPECTED_CHECKPOINT_SHA256=080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789
EXPECTED_AXIS_DEFINITIONS_SHA256=1d7fba55d00f3fe363932abfba2a0e0d76e70e8dedf71aa46c69e29679b0b7cb

mkdir -p "$OUTPUT_ROOT"
STATUS="$OUTPUT_ROOT/WORKER_STATUS"
LOCK="$OUTPUT_ROOT/worker.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "ERROR: worker lock exists: $LOCK" >&2
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

set_status() {
  printf '%s %s\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
}
fail() {
  set_status "FAILED reason=$1"
  exit 1
}
require_file() {
  [[ -s "$1" ]] || fail "missing_file=$1"
}

for path in \
  "$PROTOCOL" \
  "$EXPRESSION_PARQUET" \
  "$EXPRESSION_METADATA" \
  "$MANIFEST" \
  "$POOLED_CHECKPOINT" \
  "$PARTITION_MANIFEST" \
  "$PARTITION_REPORT" \
  "$AXIS_DEFINITIONS" \
  core/train_fixed_partition_banks.py; do
  require_file "$path"
done
[[ -n "$RUN_SEEDS" ]] || fail empty_run_seeds
[[ "$(sha256sum "$EXPRESSION_PARQUET" | awk '{print $1}')" == "$EXPECTED_EXPRESSION_SHA256" ]] || fail expression_hash
[[ "$(sha256sum "$MANIFEST" | awk '{print $1}')" == "$EXPECTED_MANIFEST_SHA256" ]] || fail manifest_hash
[[ "$(sha256sum "$POOLED_CHECKPOINT" | awk '{print $1}')" == "$EXPECTED_CHECKPOINT_SHA256" ]] || fail checkpoint_hash
[[ "$(sha256sum "$AXIS_DEFINITIONS" | awk '{print $1}')" == "$EXPECTED_AXIS_DEFINITIONS_SHA256" ]] || fail axis_definitions_hash

"$PYTHON_BIN" -m py_compile \
  core/train_fixed_partition_moe.py \
  core/train_fixed_partition_banks.py
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; report=json.load(open(sys.argv[1])); manifest=sys.argv[2]; definitions=sys.argv[3]; expected=["organ_k5","random_k5","random_group_k5_p17","random_group_k5_p42","random_group_k5_p101"]; assert report["status"]=="complete" and report["test_accessed"] is False; assert report["hashes"]["partition_manifest_sha256"]==hashlib.sha256(open(manifest,"rb").read()).hexdigest(); assert report["hashes"]["axis_definitions_sha256"]==hashlib.sha256(open(definitions,"rb").read()).hexdigest(); assert report["axes"]==expected' \
  "$PARTITION_REPORT" "$PARTITION_MANIFEST" "$AXIS_DEFINITIONS" \
  || fail partition_contract

for seed in $RUN_SEEDS; do
  case "$seed" in
    17|42|101) ;;
    *) fail "invalid_seed=$seed" ;;
  esac
done

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "ORGAN_K_CONFIRMATION_WORKER_PREFLIGHT_OK"
  echo "python=$PYTHON_BIN"
  echo "seeds=$RUN_SEEDS"
  echo "output_root=$OUTPUT_ROOT"
  exit 0
fi

printf '{"schema_version":1,"protocol":"%s","run_seeds":"%s","code_commit":"%s","launched_at_utc":"%s","test_accessed":false}\n' \
  "$PROTOCOL" "$RUN_SEEDS" "$CODE_COMMIT" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  > "$OUTPUT_ROOT/worker_provenance.json"

for seed in $RUN_SEEDS; do
  output="$OUTPUT_ROOT/seed${seed}"
  log="$OUTPUT_ROOT/seed${seed}.log"
  if [[ -f "$output/COMPLETE" ]]; then
    set_status "RUNNING phase=already_complete seed=$seed"
    continue
  fi
  [[ ! -e "$output" ]] || fail "incomplete_output=$output"
  set_status "RUNNING phase=matched_k5_train seed=$seed"
  extra=()
  if [[ -n "$MAX_UPDATES_OVERRIDE" ]]; then
    extra+=(--max-updates "$MAX_UPDATES_OVERRIDE")
  fi
  if [[ "$SMOKE_ONLY" == "1" ]]; then
    extra+=(--smoke-only)
  fi
  "$PYTHON_BIN" core/train_fixed_partition_banks.py \
    --expression-parquet "$EXPRESSION_PARQUET" \
    --expression-metadata "$EXPRESSION_METADATA" \
    --manifest "$MANIFEST" \
    --pooled-checkpoint "$POOLED_CHECKPOINT" \
    --protocol "$PROTOCOL" \
    --partition-manifest "$PARTITION_MANIFEST" \
    --partition-report "$PARTITION_REPORT" \
    --axis-definitions "$AXIS_DEFINITIONS" \
    --axis organ_k5 \
    --axis random_k5 \
    --axis random_group_k5_p17 \
    --axis random_group_k5_p42 \
    --axis random_group_k5_p101 \
    --output-dir "$output" \
    --research-stage stage1_organ_k_confirmation \
    --experiment packed_matched_organ_random_k5_banks \
    --bank-experiment hard_k5_conditional_residual_experts \
    --seed "$seed" \
    --adapter-dim 64 \
    --exposures-per-expert 2400 \
    --batch-size 8 \
    --validation-batch-size 8 \
    --mask-ratio 0.30 \
    --learning-rate 0.001 \
    --weight-decay 0.01 \
    --crossfit-folds 5 \
    --crossfit-seed 8675309 \
    --use-amp \
    "${extra[@]}" \
    > "$log" 2>&1 \
    || fail "matched_k5_training_seed=$seed"
done

touch "$OUTPUT_ROOT/WORKER_COMPLETE"
set_status COMPLETE
