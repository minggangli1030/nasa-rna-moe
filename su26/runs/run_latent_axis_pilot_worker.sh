#!/usr/bin/env bash
# One worker in the frozen Stage 2 latent-axis calibration-only pilot.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage2_latent_axis_pilot/protocol.json}"
SOURCE_ROOT="${SOURCE_ROOT:-results/stage1_organ_k5_train_20260717T165507Z}"
EXPRESSION_PARQUET="${EXPRESSION_PARQUET:-$SOURCE_ROOT/expression/expression.parquet}"
EXPRESSION_METADATA="${EXPRESSION_METADATA:-$SOURCE_ROOT/expression/extraction_report.json}"
MANIFEST="${MANIFEST:-$SOURCE_ROOT/expression/manifest.parquet}"
POOLED_CHECKPOINT="${POOLED_CHECKPOINT:-$SOURCE_ROOT/models/pooled/best_model.pt}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/stage2_latent_axis_pilot}"
RUN_SPECS="${RUN_SPECS:-}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"
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

for path in "$PROTOCOL" "$EXPRESSION_PARQUET" "$EXPRESSION_METADATA" "$MANIFEST" "$POOLED_CHECKPOINT" core/train_latent_moe.py; do
  require_file "$path"
done
[[ -n "$RUN_SPECS" ]] || fail "empty_run_specs"
[[ "$(sha256sum "$EXPRESSION_PARQUET" | awk '{print $1}')" == "$EXPECTED_EXPRESSION_SHA256" ]] || fail "expression_hash"
[[ "$(sha256sum "$MANIFEST" | awk '{print $1}')" == "$EXPECTED_MANIFEST_SHA256" ]] || fail "manifest_hash"
[[ "$(sha256sum "$POOLED_CHECKPOINT" | awk '{print $1}')" == "$EXPECTED_CHECKPOINT_SHA256" ]] || fail "checkpoint_hash"

"$PYTHON_BIN" -m py_compile core/train_single.py core/train_latent_moe.py evaluation/evaluate_latent_axis_pilot.py
"$PYTHON_BIN" -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p["matched_modes"] == ["organ_supervised","balanced_random","label_free"]; assert p["training_seeds"] == [17,42,101]; assert p["screening"]["test_access_before_pass"] is False' "$PROTOCOL"

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "LATENT_AXIS_PREFLIGHT_OK"
  echo "python=$PYTHON_BIN"
  echo "run_specs=$RUN_SPECS"
  echo "output_root=$OUTPUT_ROOT"
  exit 0
fi

printf '{"schema_version":1,"protocol":"%s","run_specs":"%s","code_commit":"%s","launched_at_utc":"%s"}\n' \
  "$PROTOCOL" "$RUN_SPECS" "${CODE_COMMIT:-unknown}" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  > "$OUTPUT_ROOT/worker_provenance.json"

for spec in $RUN_SPECS; do
  mode="${spec%%:*}"
  seed="${spec##*:}"
  case "$mode" in
    organ_supervised|balanced_random|label_free) ;;
    *) fail "invalid_mode=$mode" ;;
  esac
  case "$seed" in
    17|42|101) ;;
    *) fail "invalid_seed=$seed" ;;
  esac
  output="$OUTPUT_ROOT/${mode}_seed${seed}"
  log="$OUTPUT_ROOT/${mode}_seed${seed}.log"
  if [[ -f "$output/COMPLETE" ]]; then
    set_status "RUNNING phase=already_complete mode=$mode seed=$seed"
    continue
  fi
  [[ ! -e "$output" ]] || fail "incomplete_output=$output"
  set_status "RUNNING phase=train mode=$mode seed=$seed"
  "$PYTHON_BIN" core/train_latent_moe.py \
    --expression-parquet "$EXPRESSION_PARQUET" \
    --expression-metadata "$EXPRESSION_METADATA" \
    --manifest "$MANIFEST" \
    --pooled-checkpoint "$POOLED_CHECKPOINT" \
    --output-dir "$output" \
    --mode "$mode" \
    --seed "$seed" \
    --num-experts 5 \
    --adapter-dim 64 \
    --router-hidden-dim 128 \
    --max-updates 1500 \
    --validation-interval 150 \
    --batch-size 8 \
    --validation-batch-size 8 \
    --mask-ratio 0.30 \
    --mask-token -10.0 \
    --mask-seed 271828 \
    --repeated-mask-seeds 271828 271829 271830 \
    --learning-rate 0.001 \
    --weight-decay 0.01 \
    --temperature 0.7 \
    --load-balance-weight 0.05 \
    --entropy-weight 0.01 \
    --router-supervision-weight 0.1 \
    --use-amp \
    > "$log" 2>&1 \
    || fail "training mode=$mode seed=$seed"
done

touch "$OUTPUT_ROOT/WORKER_COMPLETE"
set_status "COMPLETE"
