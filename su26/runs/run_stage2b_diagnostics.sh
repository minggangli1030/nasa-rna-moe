#!/usr/bin/env bash
# Strict launcher for frozen Stage 2B ridge, cache, and B0-B5 diagnostic stages.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set exact diagnostic implementation commit}"
EXPECTED_PROTOCOL_SHA256="${EXPECTED_PROTOCOL_SHA256:?set frozen protocol SHA256}"
PROTOCOL="${PROTOCOL:?set frozen protocol path}"
ACTION="${ACTION:?set ridge, extract, or evaluate}"
OUTPUT_PATH="${OUTPUT_PATH:?set a new output path}"
SOURCE_ROOT="${SOURCE_ROOT:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_529c0c3}"
TRAINING_ROOT="${TRAINING_ROOT:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_training_98e2cba}"
PRIVATE_ROOT="${PRIVATE_ROOT:-/media/volume/moe-reboot/results/stage2_aligned_program_repair_51ab2f5}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"
BASIS_BUNDLE="${BASIS_BUNDLE:-artifacts/stage2_organ_expert_mechanism/aligned_program_basis.npz}"
DEVICE="${DEVICE:-cuda}"

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || exit 2
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || exit 2
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || exit 2
[[ ! -e "$OUTPUT_PATH" ]] || exit 2

"$PYTHON_BIN" -m py_compile \
  core/stage2b_cache.py \
  core/stage2b_diagnostics.py \
  core/stage2b_metrics.py \
  evaluation/extract_stage2b_canonical_training_cache.py \
  evaluation/evaluate_stage2b_diagnostics.py \
  evaluation/evaluate_stage2b_refusal.py
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="frozen_before_stage2b_diagnostic_access"; assert p["code_commit"]==sys.argv[2]; assert p["firewalls"]["archs4_access"] is False; assert p["firewalls"]["calibration_split_access"] is False; assert p["firewalls"]["neural_checkpoint_updates"] is False' \
  "$PROTOCOL" "$CODE_COMMIT"

common=(
  --protocol "$PROTOCOL"
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256"
  --expression-parquet "$SOURCE_ROOT/expression/expression.parquet"
  --expression-metadata "$SOURCE_ROOT/expression/extraction_report.json"
  --manifest "$SOURCE_ROOT/manifest/gtex_training_manifest.parquet"
  --axis-definitions "$AXIS_DEFINITIONS"
  --basis-bundle "$BASIS_BUNDLE"
  --device "$DEVICE"
)

case "$ACTION" in
  ridge)
    "$PYTHON_BIN" evaluation/extract_stage2b_canonical_training_cache.py \
      select-ridge \
      "${common[@]}" \
      --pooled-checkpoint "17=$TRAINING_ROOT/seed17/pooled/best_model.pt" \
      --pooled-checkpoint "42=$TRAINING_ROOT/seed42/pooled/best_model.pt" \
      --pooled-checkpoint "101=$TRAINING_ROOT/seed101/pooled/best_model.pt" \
      --private-checkpoint "17=$PRIVATE_ROOT/seed17/final_heads.pt" \
      --private-checkpoint "42=$PRIVATE_ROOT/seed42/final_heads.pt" \
      --private-checkpoint "101=$PRIVATE_ROOT/seed101/final_heads.pt" \
      ${MECHANICAL_ONLY:+--mechanical-only} \
      --output "$OUTPUT_PATH"
    ;;
  extract)
    SEED="${SEED:?set seed for extract}"
    RIDGE_SELECTION_REPORT="${RIDGE_SELECTION_REPORT:?set ridge report}"
    extra=()
    if [[ -n "${MAX_SAMPLES_PER_ORGAN:-}" ]]; then
      extra+=(--max-samples-per-organ "$MAX_SAMPLES_PER_ORGAN")
    fi
    if [[ -n "${B1_SAMPLES_PER_ORGAN:-}" ]]; then
      extra+=(--b1-samples-per-organ "$B1_SAMPLES_PER_ORGAN")
    fi
    if [[ -n "${MECHANICAL_ONLY:-}" ]]; then
      extra+=(--mechanical-only)
    fi
    "$PYTHON_BIN" evaluation/extract_stage2b_canonical_training_cache.py \
      extract \
      "${common[@]}" \
      --seed "$SEED" \
      --pooled-checkpoint "$TRAINING_ROOT/seed$SEED/pooled/best_model.pt" \
      --private-checkpoint "$PRIVATE_ROOT/seed$SEED/final_heads.pt" \
      --ridge-selection-report "$RIDGE_SELECTION_REPORT" \
      --output-dir "$OUTPUT_PATH" \
      "${extra[@]}"
    ;;
  evaluate)
    CACHE_ROOT_17="${CACHE_ROOT_17:?set seed17 cache root}"
    CACHE_ROOT_42="${CACHE_ROOT_42:?set seed42 cache root}"
    CACHE_ROOT_101="${CACHE_ROOT_101:?set seed101 cache root}"
    mkdir -p "$OUTPUT_PATH"
    "$PYTHON_BIN" evaluation/evaluate_stage2b_diagnostics.py \
      --protocol "$PROTOCOL" \
      --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
      --manifest "$SOURCE_ROOT/manifest/gtex_training_manifest.parquet" \
      --axis-definitions "$AXIS_DEFINITIONS" \
      --basis-bundle "$BASIS_BUNDLE" \
      --cache-root "17=$CACHE_ROOT_17" \
      --cache-root "42=$CACHE_ROOT_42" \
      --cache-root "101=$CACHE_ROOT_101" \
      --output-dir "$OUTPUT_PATH/b0_b4"
    "$PYTHON_BIN" evaluation/evaluate_stage2b_refusal.py \
      --protocol "$PROTOCOL" \
      --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
      --refusal-input "substitution_report=$SUBSTITUTION_REPORT" \
      --refusal-input "substitution_per_seed_edges=$SUBSTITUTION_PER_SEED_EDGES" \
      --refusal-input "additive_report=$ADDITIVE_REPORT" \
      --refusal-input "additive_edges=$ADDITIVE_EDGES" \
      --refusal-input "additive_per_seed=$ADDITIVE_PER_SEED" \
      --refusal-input "stability_report=$STABILITY_REPORT" \
      --refusal-input "stability_edges=$STABILITY_EDGES" \
      --refusal-input "expert_similarity=$EXPERT_SIMILARITY" \
      --output-dir "$OUTPUT_PATH/b5"
    touch "$OUTPUT_PATH/COMPLETE"
    (
      cd "$OUTPUT_PATH"
      find . -type f ! -name IMMUTABLE_SHA256SUMS -print0 \
        | sort -z | xargs -0 sha256sum > IMMUTABLE_SHA256SUMS
    )
    ;;
  *)
    exit 2
    ;;
esac
