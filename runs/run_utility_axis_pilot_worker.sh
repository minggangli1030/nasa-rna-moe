#!/usr/bin/env bash
# Run one or more packed hard-partition seed jobs from the frozen axis artifact.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage2_utility_axis_pilot/protocol.json}"
SOURCE_ROOT="${SOURCE_ROOT:-results/stage1_organ_k5_train_20260717T165507Z}"
EXPRESSION_PARQUET="${EXPRESSION_PARQUET:-$SOURCE_ROOT/expression/expression.parquet}"
EXPRESSION_METADATA="${EXPRESSION_METADATA:-$SOURCE_ROOT/expression/extraction_report.json}"
MANIFEST="${MANIFEST:-$SOURCE_ROOT/expression/manifest.parquet}"
POOLED_CHECKPOINT="${POOLED_CHECKPOINT:-$SOURCE_ROOT/models/pooled/best_model.pt}"
AXIS_ROOT="${AXIS_ROOT:-results/stage2_utility_axis_pilot/axis}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/stage2_utility_axis_pilot/packed}"
RUN_SEEDS="${RUN_SEEDS:-}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"
MAX_UPDATES_OVERRIDE="${MAX_UPDATES_OVERRIDE:-}"
SMOKE_ONLY="${SMOKE_ONLY:-0}"
EXPECTED_EXPRESSION_SHA256=148776bc2d5bbe4a969103de7abab932b7467c804934fc697366ae2c209c0821
EXPECTED_MANIFEST_SHA256=bc4e8e4e36ab0e869fd885197842dc797edad5a08b8093beb21185dbeda7f9cc
EXPECTED_CHECKPOINT_SHA256=080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789

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

PARTITION_MANIFEST="$AXIS_ROOT/partition_manifest.parquet"
PARTITION_REPORT="$AXIS_ROOT/partition_report.json"
AXIS_DEFINITIONS="$AXIS_ROOT/axis_definitions.npz"
for path in "$PROTOCOL" "$EXPRESSION_PARQUET" "$EXPRESSION_METADATA" "$MANIFEST" "$POOLED_CHECKPOINT" "$PARTITION_MANIFEST" "$PARTITION_REPORT" "$AXIS_DEFINITIONS" core/train_fixed_partition_banks.py; do
  require_file "$path"
done
[[ -n "$RUN_SEEDS" ]] || fail empty_run_seeds
[[ "$(sha256sum "$EXPRESSION_PARQUET" | awk '{print $1}')" == "$EXPECTED_EXPRESSION_SHA256" ]] || fail expression_hash
[[ "$(sha256sum "$MANIFEST" | awk '{print $1}')" == "$EXPECTED_MANIFEST_SHA256" ]] || fail manifest_hash
[[ "$(sha256sum "$POOLED_CHECKPOINT" | awk '{print $1}')" == "$EXPECTED_CHECKPOINT_SHA256" ]] || fail checkpoint_hash
"$PYTHON_BIN" -m py_compile core/train_fixed_partition_moe.py core/train_fixed_partition_banks.py
"$PYTHON_BIN" -c 'import hashlib,json,sys; r=json.load(open(sys.argv[1])); pairs=((sys.argv[2],"partition_manifest_sha256"),(sys.argv[3],"axis_definitions_sha256")); assert r["status"]=="complete" and r["test_accessed"] is False; [(lambda got,key: (_ for _ in ()).throw(AssertionError(key)) if got != r["hashes"][key] else None)(hashlib.sha256(open(path,"rb").read()).hexdigest(), key) for path,key in pairs]' "$PARTITION_REPORT" "$PARTITION_MANIFEST" "$AXIS_DEFINITIONS"
for seed in $RUN_SEEDS; do
  case "$seed" in 17|42|101) ;; *) fail "invalid_seed=$seed" ;; esac
done

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "UTILITY_AXIS_WORKER_PREFLIGHT_OK"
  echo "python=$PYTHON_BIN"
  echo "seeds=$RUN_SEEDS"
  echo "output_root=$OUTPUT_ROOT"
  exit 0
fi

printf '{"schema_version":1,"protocol":"%s","run_seeds":"%s","code_commit":"%s","launched_at_utc":"%s","test_accessed":false}\n' \
  "$PROTOCOL" "$RUN_SEEDS" "${CODE_COMMIT:-unknown}" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  > "$OUTPUT_ROOT/worker_provenance.json"

for seed in $RUN_SEEDS; do
  output="$OUTPUT_ROOT/seed${seed}"
  log="$OUTPUT_ROOT/seed${seed}.log"
  if [[ -f "$output/COMPLETE" ]]; then
    set_status "RUNNING phase=already_complete seed=$seed"
    continue
  fi
  [[ ! -e "$output" ]] || fail "incomplete_output=$output"
  set_status "RUNNING phase=packed_train seed=$seed"
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
    --output-dir "$output" \
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
    || fail "packed_training_seed=$seed"
done

touch "$OUTPUT_ROOT/WORKER_COMPLETE"
set_status COMPLETE
