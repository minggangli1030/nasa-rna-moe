#!/usr/bin/env bash
# Full strict GTEx-only pooled/K8/random/control/router fitting.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the deployed full Git commit}"
SOURCE_ROOT="${SOURCE_ROOT:?set SOURCE_ROOT to the completed GTEx extraction root}"
TRAINING_ROOT="${TRAINING_ROOT:?set TRAINING_ROOT to a new persistent output root}"
SMOKE_ROOT="${SMOKE_ROOT:?set SMOKE_ROOT to the completed mechanical smoke root}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_gtex_to_archs4/protocol.json}"
MANIFEST_ROOT="${MANIFEST_ROOT:-$SOURCE_ROOT/manifest}"
EXPRESSION_ROOT="${EXPRESSION_ROOT:-$SOURCE_ROOT/expression}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"
RUN_SEEDS="${RUN_SEEDS:-17 42 101}"
EXPECTED_PROTOCOL_SHA256=1d982a469f3e1c7c907394d85f2c4b5c75558de88607680ecb1d51af06380a69

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: CODE_COMMIT must be a full hexadecimal commit" >&2
  exit 1
}
[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || {
  echo "ERROR: deployed Git HEAD differs from CODE_COMMIT" >&2
  exit 1
}
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo "ERROR: deployed tracked Git tree is dirty" >&2
  exit 1
}
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || {
  echo "ERROR: protocol hash mismatch" >&2
  exit 1
}
[[ -e "$SMOKE_ROOT/SMOKE_COMPLETE" ]] || {
  echo "ERROR: mechanical smoke has not passed" >&2
  exit 1
}
grep -q '^COMPLETE ' "$SMOKE_ROOT/SMOKE_STATUS" || {
  echo "ERROR: mechanical smoke status is not COMPLETE" >&2
  exit 1
}
for path in \
  "$PROTOCOL" \
  "$MANIFEST_ROOT/gtex_training_manifest.parquet" \
  "$MANIFEST_ROOT/manifest_report.json" \
  "$EXPRESSION_ROOT/expression.parquet" \
  "$EXPRESSION_ROOT/extraction_report.json" \
  "$EXPRESSION_ROOT/EXTRACTION_COMPLETE" \
  "$AXIS_DEFINITIONS"; do
  [[ -s "$path" ]] || {
    echo "ERROR: missing required input $path" >&2
    exit 1
  }
done
[[ ! -e "$TRAINING_ROOT" ]] || {
  echo "ERROR: training output already exists: $TRAINING_ROOT" >&2
  exit 1
}
mkdir -p "$TRAINING_ROOT"
STATUS="$TRAINING_ROOT/TRAINING_STATUS"
LOCK="$TRAINING_ROOT/training.lock"
mkdir "$LOCK"
cleanup() {
  rc=$?
  rmdir "$LOCK" 2>/dev/null || true
  if [[ "$rc" -ne 0 ]]; then
    printf 'FAILED exit=%s %s\n' "$rc" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  fi
}
trap cleanup EXIT

"$PYTHON_BIN" -m py_compile \
  core/train_manifest.py \
  core/train_fixed_partition_banks.py \
  evaluation/refit_gtex_to_archs4_router.py
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="frozen_gtex_to_archs4_development_contract"; assert p["strict_model_family"]["archs4_derived_weights_allowed"] is False; assert p["strict_model_family"]["pooled_training"]["max_updates"]==7350; assert p["strict_model_family"]["adapter_training"]["max_updates"]==1500; assert p["firewalls"]["best_seed_selection"] is False; assert p["firewalls"]["archs4_lockbox_expression_access_before_candidate_freeze"] is False' \
  "$PROTOCOL"
"$PYTHON_BIN" -c \
  'import torch; assert torch.cuda.is_available(); p=torch.cuda.get_device_properties(0); assert p.total_memory >= 39*1024**3; print(p.name,p.total_memory)' \
  > "$TRAINING_ROOT/cuda_preflight.log"
printf '%s\n' "$CODE_COMMIT" > "$TRAINING_ROOT/CODE_COMMIT"
printf '%s\n' "$EXPECTED_PROTOCOL_SHA256" > "$TRAINING_ROOT/PROTOCOL_SHA256"

for seed in $RUN_SEEDS; do
  [[ "$seed" == "17" || "$seed" == "42" || "$seed" == "101" ]] || {
    echo "ERROR: unsupported training seed $seed" >&2
    exit 1
  }
  SEED_ROOT="$TRAINING_ROOT/seed$seed"
  mkdir "$SEED_ROOT"
  printf 'RUNNING phase=pooled seed=%s %s\n' "$seed" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  "$PYTHON_BIN" core/train_manifest.py \
    --expression-parquet "$EXPRESSION_ROOT/expression.parquet" \
    --expression-metadata "$EXPRESSION_ROOT/extraction_report.json" \
    --manifest "$MANIFEST_ROOT/gtex_training_manifest.parquet" \
    --output-dir "$SEED_ROOT/pooled" \
    --role pooled \
    --train-split train \
    --validation-split calibration \
    --train-filter-column balanced_train \
    --sampling-mode organ_balanced \
    --seed "$seed" \
    --validation-mask-seed 271828 \
    --max-updates 7350 \
    --batch-size 8 \
    --validation-batch-size 8 \
    --validation-interval 50 \
    --learning-rate 0.0002 \
    --weight-decay 0.01 \
    --normalization log1p_tpm \
    --mask-ratio 0.30 \
    --mask-token -10.0 \
    --hidden-dim 768 \
    --ffn-dim 3072 \
    --num-heads 8 \
    --num-layers 4 \
    --ree-base 100 \
    --feature-type sqr \
    --compute-type iter \
    --device cuda \
    --num-workers 0 \
    --log-every 50 \
    > "$SEED_ROOT/pooled.log" 2>&1
  "$PYTHON_BIN" -c \
    'import json,sys; r=json.load(open(sys.argv[1])); assert r["status"]=="complete" and r["completed_updates"]==7350; assert r["model"]["hidden_dim"]==768 and r["model"]["num_layers"]==4 and r["model"]["num_heads"]==8; assert r["training"]["sampling_mode"]=="organ_balanced"' \
    "$SEED_ROOT/pooled/run_metadata.json"

  printf 'RUNNING phase=banks seed=%s %s\n' "$seed" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  "$PYTHON_BIN" core/train_fixed_partition_banks.py \
    --expression-parquet "$EXPRESSION_ROOT/expression.parquet" \
    --expression-metadata "$EXPRESSION_ROOT/extraction_report.json" \
    --manifest "$MANIFEST_ROOT/gtex_training_manifest.parquet" \
    --pooled-checkpoint "$SEED_ROOT/pooled/best_model.pt" \
    --protocol "$PROTOCOL" \
    --partition-manifest "$MANIFEST_ROOT/gtex_training_manifest.parquet" \
    --partition-report "$MANIFEST_ROOT/manifest_report.json" \
    --axis-definitions "$AXIS_DEFINITIONS" \
    --axis organ_k8 \
    --axis random_k8_p17 \
    --axis random_k8_p42 \
    --axis random_k8_p101 \
    --axis pooled_adapter \
    --axis-update-budget organ_k8=1500 \
    --axis-update-budget random_k8_p17=1500 \
    --axis-update-budget random_k8_p42=1500 \
    --axis-update-budget random_k8_p101=1500 \
    --axis-update-budget pooled_adapter=1500 \
    --axis-target-exposures organ_k8=1500 \
    --axis-target-exposures random_k8_p17=1500 \
    --axis-target-exposures random_k8_p42=1500 \
    --axis-target-exposures random_k8_p101=1500 \
    --axis-target-exposures pooled_adapter=12000 \
    --axis-expert-key organ_k8=organ:adipose,organ:brain,organ:colon,organ:heart,organ:liver,organ:lung,organ:skeletal_muscle,organ:skin \
    --require-calibration-coverage \
    --sampling-mode organ_sample_balanced \
    --output-dir "$SEED_ROOT/banks" \
    --research-stage gtex_to_archs4_strict_development \
    --experiment gtex_k8_packed_strict_training \
    --bank-experiment gtex_k8_strict_residual_bank \
    --seed "$seed" \
    --code-commit "$CODE_COMMIT" \
    --train-split train \
    --validation-split calibration \
    --train-filter-column balanced_train \
    --adapter-dim 64 \
    --exposures-per-expert 2400 \
    --max-updates 1500 \
    --batch-size 8 \
    --validation-batch-size 8 \
    --mask-ratio 0.30 \
    --mask-token -10.0 \
    --learning-rate 0.001 \
    --weight-decay 0.01 \
    --crossfit-folds 5 \
    --crossfit-seed 8675309 \
    --log-interval 100 \
    --device cuda \
    --num-workers 0 \
    > "$SEED_ROOT/banks.log" 2>&1
  "$PYTHON_BIN" -c \
    'import json,pathlib,sys; r=pathlib.Path(sys.argv[1]); m=json.load(open(r/"run_metadata.json")); axes=["organ_k8","random_k8_p17","random_k8_p42","random_k8_p101","pooled_adapter"]; assert m["status"]=="complete" and m["config"]["axes"]==axes and all(m["config"]["bank_update_budgets"][a]==1500 for a in axes); assert all(json.load(open(r/"banks"/a/"run_metadata.json"))["artifacts"]["checkpoint_roundtrip_verified"] for a in axes)' \
    "$SEED_ROOT/banks"
  touch "$SEED_ROOT/SEED_COMPLETE"
done

printf 'RUNNING phase=router %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/refit_gtex_to_archs4_router.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --expression-parquet "$EXPRESSION_ROOT/expression.parquet" \
  --expression-metadata "$EXPRESSION_ROOT/extraction_report.json" \
  --manifest "$MANIFEST_ROOT/gtex_training_manifest.parquet" \
  --manifest-report "$MANIFEST_ROOT/manifest_report.json" \
  --axis-definitions "$AXIS_DEFINITIONS" \
  --output-dir "$TRAINING_ROOT/router" \
  --router-seed 271828 \
  --mask-token -10.0 \
  > "$TRAINING_ROOT/router.log" 2>&1

(
  cd "$TRAINING_ROOT"
  find . -type f \
    ! -name FULL_SHA256SUMS \
    ! -name TRAINING_STATUS \
    ! -name TRAINING_COMPLETE \
    -print0 \
    | sort -z \
    | xargs -0 sha256sum > FULL_SHA256SUMS
)
touch "$TRAINING_ROOT/TRAINING_COMPLETE"
printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
