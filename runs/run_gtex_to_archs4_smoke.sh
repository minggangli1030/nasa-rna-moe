#!/usr/bin/env bash
# Real-GTEx mechanical smoke for the frozen GTEx-to-ARCHS4 K8 contract.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the deployed full Git commit}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set EXPERIMENT_ROOT to the persistent result root}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_gtex_to_archs4/protocol.json}"
MANIFEST_ROOT="${MANIFEST_ROOT:-$EXPERIMENT_ROOT/manifest}"
EXPRESSION_ROOT="${EXPRESSION_ROOT:-$EXPERIMENT_ROOT/expression}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"
SMOKE_ROOT="${SMOKE_ROOT:-$EXPERIMENT_ROOT/smoke}"
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
[[ ! -e "$SMOKE_ROOT" ]] || {
  echo "ERROR: smoke output already exists: $SMOKE_ROOT" >&2
  exit 1
}
mkdir -p "$SMOKE_ROOT"
STATUS="$SMOKE_ROOT/SMOKE_STATUS"
cleanup() {
  rc=$?
  if [[ "$rc" -ne 0 ]]; then
    printf 'FAILED exit=%s %s\n' "$rc" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  fi
}
trap cleanup EXIT

"$PYTHON_BIN" -m py_compile \
  evaluation/build_gtex_to_archs4_smoke_fixture.py \
  evaluation/refit_gtex_to_archs4_router.py \
  core/train_manifest.py \
  core/train_fixed_partition_banks.py
"$PYTHON_BIN" -c \
  'import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))' \
  > "$SMOKE_ROOT/cuda_preflight.log"

printf 'RUNNING phase=fixture %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/build_gtex_to_archs4_smoke_fixture.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --manifest "$MANIFEST_ROOT/gtex_training_manifest.parquet" \
  --manifest-report "$MANIFEST_ROOT/manifest_report.json" \
  --expression "$EXPRESSION_ROOT/expression.parquet" \
  --expression-report "$EXPRESSION_ROOT/extraction_report.json" \
  --axis-definitions "$AXIS_DEFINITIONS" \
  --minimum-rows-per-split 64 \
  --output-dir "$SMOKE_ROOT/fixture" \
  > "$SMOKE_ROOT/fixture.log" 2>&1

printf 'RUNNING phase=pooled %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" core/train_manifest.py \
  --expression-parquet "$SMOKE_ROOT/fixture/smoke_expression.parquet" \
  --expression-metadata "$SMOKE_ROOT/fixture/extraction_report.json" \
  --manifest "$SMOKE_ROOT/fixture/smoke_manifest.parquet" \
  --output-dir "$SMOKE_ROOT/pooled_seed17" \
  --role pooled \
  --train-split train \
  --validation-split calibration \
  --train-filter-column balanced_train \
  --sampling-mode organ_balanced \
  --seed 17 \
  --validation-mask-seed 271828 \
  --max-updates 2 \
  --batch-size 8 \
  --validation-batch-size 8 \
  --validation-interval 2 \
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
  --log-every 1 \
  > "$SMOKE_ROOT/pooled.log" 2>&1

printf 'RUNNING phase=banks %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" core/train_fixed_partition_banks.py \
  --expression-parquet "$SMOKE_ROOT/fixture/smoke_expression.parquet" \
  --expression-metadata "$SMOKE_ROOT/fixture/extraction_report.json" \
  --manifest "$SMOKE_ROOT/fixture/smoke_manifest.parquet" \
  --pooled-checkpoint "$SMOKE_ROOT/pooled_seed17/best_model.pt" \
  --protocol "$PROTOCOL" \
  --partition-manifest "$SMOKE_ROOT/fixture/smoke_manifest.parquet" \
  --partition-report "$SMOKE_ROOT/fixture/partition_report.json" \
  --axis-definitions "$AXIS_DEFINITIONS" \
  --axis organ_k8 \
  --axis random_k8_p17 \
  --axis random_k8_p42 \
  --axis random_k8_p101 \
  --axis pooled_adapter \
  --require-calibration-coverage \
  --sampling-mode organ_sample_balanced \
  --output-dir "$SMOKE_ROOT/banks_seed17" \
  --research-stage gtex_to_archs4_mechanical_smoke \
  --experiment gtex_k8_packed_mechanical_smoke \
  --bank-experiment gtex_k8_mechanical_smoke_bank \
  --seed 17 \
  --code-commit "$CODE_COMMIT" \
  --train-split train \
  --validation-split calibration \
  --train-filter-column balanced_train \
  --adapter-dim 64 \
  --exposures-per-expert 2400 \
  --max-updates 2 \
  --batch-size 8 \
  --validation-batch-size 8 \
  --mask-ratio 0.30 \
  --mask-token -10.0 \
  --learning-rate 0.001 \
  --weight-decay 0.01 \
  --crossfit-folds 2 \
  --crossfit-seed 8675309 \
  --log-interval 1 \
  --device cuda \
  --num-workers 0 \
  --smoke-only \
  > "$SMOKE_ROOT/banks.log" 2>&1

printf 'RUNNING phase=router %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/refit_gtex_to_archs4_router.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --expression-parquet "$SMOKE_ROOT/fixture/smoke_expression.parquet" \
  --expression-metadata "$SMOKE_ROOT/fixture/extraction_report.json" \
  --manifest "$SMOKE_ROOT/fixture/smoke_manifest.parquet" \
  --manifest-report "$SMOKE_ROOT/fixture/partition_report.json" \
  --axis-definitions "$AXIS_DEFINITIONS" \
  --output-dir "$SMOKE_ROOT/router" \
  --router-seed 271828 \
  --mask-token -10.0 \
  --mechanical-only \
  > "$SMOKE_ROOT/router.log" 2>&1

"$PYTHON_BIN" -c \
  'import json,pathlib,sys; r=pathlib.Path(sys.argv[1]); p=json.load(open(r/"pooled_seed17/run_metadata.json")); b=json.load(open(r/"banks_seed17/run_metadata.json")); q=json.load(open(r/"router/router_report.json")); axes=["organ_k8","random_k8_p17","random_k8_p42","random_k8_p101","pooled_adapter"]; assert p["status"]=="complete" and p["completed_updates"]==2; assert b["status"]=="complete" and b["mechanical_only"] is True and b["config"]["axes"]==axes; assert all(json.load(open(r/"banks_seed17/banks"/a/"run_metadata.json"))["artifacts"]["checkpoint_roundtrip_verified"] for a in axes); assert q["status"]=="complete" and q["mechanical_only"] is True and q["performance_metrics_generated"] is False and q["classes"]==["adipose","brain","colon","heart","liver","lung","skeletal_muscle","skin"]' \
  "$SMOKE_ROOT"

touch "$SMOKE_ROOT/SMOKE_COMPLETE"
printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
