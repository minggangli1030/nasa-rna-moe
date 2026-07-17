#!/usr/bin/env bash
# Stage 1 five-organ mechanical smoke. This validates the complete software path;
# it is not authorized as biological evidence.
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

SOURCE_MANIFEST="${SOURCE_MANIFEST:-artifacts/stage1_organ_pilot/organ_pilot_manifest.csv}"
HUMAN_H5="${HUMAN_H5:-/media/volume/moe-reboot/archs4/human_matrix_v11.h5}"
CANONICAL_GENES="${CANONICAL_GENES:-data/ensembl/canonical_genes_shared.txt}"
HUMAN_EXON_LENGTHS="${HUMAN_EXON_LENGTHS:-data/gencode/gencode_v49_gene_exon_lengths.csv}"
STAGE0_COMPLETE_MARKER="${STAGE0_COMPLETE_MARKER:-results/mixed_20k_v3_shuffled_eval.COMPLETE}"

OUTPUT_ROOT=""
TRAIN_SEED="${TRAIN_SEED:-42}"
PROTOCOL_SEED="${PROTOCOL_SEED:-314159}"
MASK_SEED="${MASK_SEED:-271828}"
MAX_UPDATES="${MAX_UPDATES:-50}"
BATCH_SIZE="${BATCH_SIZE:-8}"
DEVICE="${DEVICE:-auto}"
HIDDEN_DIM="${HIDDEN_DIM:-768}"
FFN_DIM="${FFN_DIM:-3072}"
NUM_HEADS="${NUM_HEADS:-8}"
NUM_LAYERS="${NUM_LAYERS:-4}"
BOOTSTRAP_REPS="${BOOTSTRAP_REPS:-500}"
QC_MIN_NONZERO="${QC_MIN_NONZERO:-14000}"
# VALIDATION_INTERVAL: if set, validate every N updates (real runs pick best-val
# checkpoints); if empty, keep smoke behaviour (validate once at the end).
VALIDATION_INTERVAL="${VALIDATION_INTERVAL:-}"
# RUN_MODE: "smoke" (default) marks output SMOKE_ONLY; "full" marks FULL_RUN.
RUN_MODE="${RUN_MODE:-smoke}"
REQUIRE_STAGE0_COMPLETE=1
PREFLIGHT_ONLY=0

usage() {
  echo "Usage: $0 [--output-root DIR] [--preflight] [--allow-stage0-incomplete]"
  echo "          [--human-h5 PATH] [--manifest PATH] [--seed N] [--max-updates N]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-root)
      OUTPUT_ROOT="$2"
      shift 2
      ;;
    --preflight)
      PREFLIGHT_ONLY=1
      shift
      ;;
    --allow-stage0-incomplete)
      REQUIRE_STAGE0_COMPLETE=0
      shift
      ;;
    --human-h5)
      HUMAN_H5="$2"
      shift 2
      ;;
    --manifest)
      SOURCE_MANIFEST="$2"
      shift 2
      ;;
    --seed)
      TRAIN_SEED="$2"
      shift 2
      ;;
    --max-updates)
      MAX_UPDATES="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "ERROR: required file not found: $1" >&2
    exit 1
  fi
}

require_file "$SOURCE_MANIFEST"
require_file "$HUMAN_H5"
require_file "$CANONICAL_GENES"
require_file "$HUMAN_EXON_LENGTHS"
require_file evaluation/build_balanced_organ_protocol.py
require_file evaluation/filter_manifest_by_expression_qc.py
require_file preprocessing/extract_manifest_expression.py
require_file core/train_manifest.py
require_file evaluation/cache_organ_predictions.py
require_file evaluation/evaluate_organ_moe.py
require_file evaluation/check_organ_smoke_health.py

if [[ "$REQUIRE_STAGE0_COMPLETE" -eq 1 ]]; then
  require_file "$STAGE0_COMPLETE_MARKER"
fi

"$PYTHON_BIN" -c "import h5py, numpy, pandas, pyarrow, sklearn, torch"
"$PYTHON_BIN" -m py_compile \
  preprocessing/extract_manifest_expression.py \
  core/train_manifest.py \
  evaluation/build_balanced_organ_protocol.py \
  evaluation/filter_manifest_by_expression_qc.py \
  evaluation/cache_organ_predictions.py \
  evaluation/evaluate_organ_moe.py \
  evaluation/check_organ_smoke_health.py

if [[ "$PREFLIGHT_ONLY" -eq 1 ]]; then
  echo "PREFLIGHT_OK"
  echo "python=$PYTHON_BIN"
  echo "manifest=$SOURCE_MANIFEST"
  echo "human_h5=$HUMAN_H5"
  echo "stage0_required=$REQUIRE_STAGE0_COMPLETE"
  exit 0
fi

if [[ -z "$OUTPUT_ROOT" ]]; then
  OUTPUT_ROOT="results/stage1_organ_smoke_$(date -u '+%Y%m%dT%H%M%SZ')"
fi
if [[ -e "$OUTPUT_ROOT" ]]; then
  echo "ERROR: output root already exists; refusing to overwrite: $OUTPUT_ROOT" >&2
  exit 1
fi
mkdir -p "$OUTPUT_ROOT"
STATUS_FILE="$OUTPUT_ROOT/STATUS"
printf 'RUNNING %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS_FILE"
on_exit() {
  code=$?
  if [[ "$code" -ne 0 ]]; then
    printf 'FAILED exit=%s %s\n' "$code" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS_FILE"
    touch "$OUTPUT_ROOT/FAILED"
  fi
}
trap on_exit EXIT

INITIAL_PROTOCOL="$OUTPUT_ROOT/protocol_initial"
QC_SCAN="$OUTPUT_ROOT/expression_qc_scan"
QC_FILTERED="$OUTPUT_ROOT/qc_filtered"
FINAL_PROTOCOL="$OUTPUT_ROOT/protocol_final"
FINAL_EXPRESSION="$OUTPUT_ROOT/expression"
mkdir -p "$INITIAL_PROTOCOL"

"$PYTHON_BIN" evaluation/build_balanced_organ_protocol.py \
  --manifest "$SOURCE_MANIFEST" \
  --output-dir "$INITIAL_PROTOCOL" \
  --seed "$PROTOCOL_SEED"

INITIAL_MANIFEST="$INITIAL_PROTOCOL/organ_protocol_manifest.csv"
if "$PYTHON_BIN" preprocessing/extract_manifest_expression.py \
  --manifest "$INITIAL_MANIFEST" \
  --human-h5 "$HUMAN_H5" \
  --canonical-genes "$CANONICAL_GENES" \
  --human-exon-lengths "$HUMAN_EXON_LENGTHS" \
  --qc-min-nonzero "$QC_MIN_NONZERO" \
  --output-dir "$QC_SCAN"; then
  PROTOCOL_MANIFEST="$INITIAL_MANIFEST"
  EXPRESSION_DIR="$QC_SCAN"
else
  if [[ ! -f "$QC_SCAN/extraction_report.json" ]]; then
    echo "ERROR: expression extraction failed before producing a QC report; see the extractor error above" >&2
    exit 1
  fi
  "$PYTHON_BIN" -c \
    'import json,sys; r=json.load(open(sys.argv[1])); assert r.get("status")=="failed_qc", r.get("status")' \
    "$QC_SCAN/extraction_report.json"
  "$PYTHON_BIN" evaluation/filter_manifest_by_expression_qc.py \
    --manifest "$SOURCE_MANIFEST" \
    --failed-extraction-report "$QC_SCAN/extraction_report.json" \
    --output-dir "$QC_FILTERED"
  "$PYTHON_BIN" evaluation/build_balanced_organ_protocol.py \
    --manifest "$QC_FILTERED/qc_eligible_manifest.csv" \
    --output-dir "$FINAL_PROTOCOL" \
    --seed "$PROTOCOL_SEED"
  PROTOCOL_MANIFEST="$FINAL_PROTOCOL/organ_protocol_manifest.csv"
  "$PYTHON_BIN" preprocessing/extract_manifest_expression.py \
    --manifest "$PROTOCOL_MANIFEST" \
    --human-h5 "$HUMAN_H5" \
    --canonical-genes "$CANONICAL_GENES" \
    --human-exon-lengths "$HUMAN_EXON_LENGTHS" \
    --qc-min-nonzero "$QC_MIN_NONZERO" \
    --output-dir "$FINAL_EXPRESSION"
  EXPRESSION_DIR="$FINAL_EXPRESSION"
fi

EXPRESSION_PARQUET="$EXPRESSION_DIR/expression.parquet"
EXPRESSION_METADATA="$EXPRESSION_DIR/extraction_report.json"
TRAIN_MANIFEST="$EXPRESSION_DIR/manifest.parquet"
require_file "$EXPRESSION_PARQUET"
require_file "$EXPRESSION_METADATA"
require_file "$TRAIN_MANIFEST"

ORGANS=()
while IFS= read -r organ; do
  [[ -n "$organ" ]] && ORGANS+=("$organ")
done < <("$PYTHON_BIN" -c \
  'import pandas as pd,sys; m=pd.read_csv(sys.argv[1]); print("\n".join(sorted(m.organ.unique())))' \
  "$PROTOCOL_MANIFEST")
if [[ "${#ORGANS[@]}" -lt 2 ]]; then
  echo "ERROR: fewer than two organs survived preprocessing" >&2
  exit 1
fi

COMMON_TRAIN_ARGS=(
  --expression-parquet "$EXPRESSION_PARQUET"
  --expression-metadata "$EXPRESSION_METADATA"
  --manifest "$TRAIN_MANIFEST"
  --train-split train
  --validation-split calibration
  --train-filter-column balanced_train
  --seed "$TRAIN_SEED"
  --batch-size "$BATCH_SIZE"
  --validation-batch-size "$BATCH_SIZE"
  --mask-ratio 0.30
  --hidden-dim "$HIDDEN_DIM"
  --ffn-dim "$FFN_DIM"
  --num-heads "$NUM_HEADS"
  --num-layers "$NUM_LAYERS"
  --device "$DEVICE"
  --export-split train
  --export-split calibration
  --export-split test
  --export-mask-seed "$MASK_SEED"
)

MODELS_DIR="$OUTPUT_ROOT/models"
mkdir -p "$MODELS_DIR"
POOLED_UPDATES=$((MAX_UPDATES * ${#ORGANS[@]}))
POOLED_VAL_INTERVAL="${VALIDATION_INTERVAL:-$POOLED_UPDATES}"
ORGAN_VAL_INTERVAL="${VALIDATION_INTERVAL:-$MAX_UPDATES}"
"$PYTHON_BIN" core/train_manifest.py \
  "${COMMON_TRAIN_ARGS[@]}" \
  --output-dir "$MODELS_DIR/pooled" \
  --role pooled \
  --sampling-mode organ_balanced \
  --max-updates "$POOLED_UPDATES" \
  --validation-interval "$POOLED_VAL_INTERVAL"

for organ in "${ORGANS[@]}"; do
  "$PYTHON_BIN" core/train_manifest.py \
    "${COMMON_TRAIN_ARGS[@]}" \
    --output-dir "$MODELS_DIR/organ_$organ" \
    --role organ \
    --organ "$organ" \
    --sampling-mode organ_balanced \
    --max-updates "$MAX_UPDATES" \
    --validation-interval "$ORGAN_VAL_INTERVAL"
done

for index in "${!ORGANS[@]}"; do
  shard="random_$index"
  "$PYTHON_BIN" core/train_manifest.py \
    "${COMMON_TRAIN_ARGS[@]}" \
    --output-dir "$MODELS_DIR/$shard" \
    --role random \
    --random-shard "$shard" \
    --sampling-mode organ_balanced \
    --max-updates "$MAX_UPDATES" \
    --validation-interval "$ORGAN_VAL_INTERVAL"
done

CACHE_ARGS=(
  --manifest-csv "$PROTOCOL_MANIFEST"
  --expression "$EXPRESSION_PARQUET"
  --prediction "pooled=$MODELS_DIR/pooled/predictions.npz"
  --output "$OUTPUT_ROOT/prediction_cache.npz"
  --train-filter-column balanced_train
  --train-split train
  --random-shard-column random_shard
  --mask-seed "$MASK_SEED"
  --mask-fraction 0.30
  --expression-input-space tpm
)
for organ in "${ORGANS[@]}"; do
  CACHE_ARGS+=(--prediction "organ:$organ=$MODELS_DIR/organ_$organ/predictions.npz")
done
for index in "${!ORGANS[@]}"; do
  shard="random_$index"
  CACHE_ARGS+=(--prediction "random:$shard=$MODELS_DIR/$shard/predictions.npz")
done
"$PYTHON_BIN" evaluation/cache_organ_predictions.py "${CACHE_ARGS[@]}"

"$PYTHON_BIN" evaluation/evaluate_organ_moe.py \
  --cache "$OUTPUT_ROOT/prediction_cache.npz" \
  --output-dir "$OUTPUT_ROOT/evaluation" \
  --train-split train \
  --calibration-split calibration \
  --test-split test \
  --seed "$MASK_SEED" \
  --training-seed "$TRAIN_SEED" \
  --bootstrap-reps "$BOOTSTRAP_REPS"

"$PYTHON_BIN" evaluation/check_organ_smoke_health.py \
  --report "$OUTPUT_ROOT/evaluation/report.json" \
  --output "$OUTPUT_ROOT/mechanical_health.json"

if [[ "$RUN_MODE" == "full" ]]; then
  touch "$OUTPUT_ROOT/FULL_RUN"
else
  touch "$OUTPUT_ROOT/SMOKE_ONLY"
fi
touch "$OUTPUT_ROOT/COMPLETE"
rm -f "$OUTPUT_ROOT/FAILED"
printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS_FILE"
trap - EXIT
echo "ORGAN_SMOKE_COMPLETE $OUTPUT_ROOT"
