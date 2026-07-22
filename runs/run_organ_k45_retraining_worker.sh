#!/usr/bin/env bash
# Train genuine organ/random K4/K5 banks under the two frozen budget views.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_organ_k45_retraining/protocol.json}"
SOURCE_ROOT="${SOURCE_ROOT:-/media/volume/moe-reboot/results/stage1_organ_k5_train_20260717T165507Z}"
EXPRESSION_PARQUET="${EXPRESSION_PARQUET:-$SOURCE_ROOT/expression/expression.parquet}"
EXPRESSION_METADATA="${EXPRESSION_METADATA:-$SOURCE_ROOT/expression/extraction_report.json}"
MANIFEST="${MANIFEST:-$SOURCE_ROOT/expression/manifest.parquet}"
POOLED_CHECKPOINT="${POOLED_CHECKPOINT:-$SOURCE_ROOT/models/pooled/best_model.pt}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set EXPERIMENT_ROOT to the persistent experiment root}"
PARTITION_ROOT="${PARTITION_ROOT:-$EXPERIMENT_ROOT/partitions}"
PARTITION_MANIFEST="${PARTITION_MANIFEST:-$PARTITION_ROOT/train_cal_partitions.parquet}"
PARTITION_REPORT="${PARTITION_REPORT:-$PARTITION_ROOT/partition_report.json}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage2_utility_axis_pilot_f8ab3cd/axis/axis_definitions.npz}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$EXPERIMENT_ROOT/packed}"
RUN_SEEDS="${RUN_SEEDS:-}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"
MAX_UPDATES_OVERRIDE="${MAX_UPDATES_OVERRIDE:-}"
SMOKE_ONLY="${SMOKE_ONLY:-0}"
CODE_COMMIT="${CODE_COMMIT:-unknown}"

EXPECTED_EXPRESSION_SHA256=148776bc2d5bbe4a969103de7abab932b7467c804934fc697366ae2c209c0821
EXPECTED_MANIFEST_SHA256=bc4e8e4e36ab0e869fd885197842dc797edad5a08b8093beb21185dbeda7f9cc
EXPECTED_CHECKPOINT_SHA256=080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789
EXPECTED_AXIS_DEFINITIONS_SHA256=1d7fba55d00f3fe363932abfba2a0e0d76e70e8dedf71aa46c69e29679b0b7cb

AXES=(
  organ_k5
  organ_k4_epe
  organ_k4_total_active
  random_group_k5_p17
  random_group_k5_p42
  random_group_k5_p101
  random_group_k4_epe_p17
  random_group_k4_epe_p42
  random_group_k4_epe_p101
  random_group_k4_total_active_p17
  random_group_k4_total_active_p42
  random_group_k4_total_active_p101
)

mkdir -p "$OUTPUT_ROOT"
STATUS="$OUTPUT_ROOT/WORKER_STATUS"
LOCK="$OUTPUT_ROOT/worker.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "ERROR: worker lock exists: $LOCK" >&2
  exit 1
fi
FINAL_STATUS_WRITTEN=0
cleanup() {
  rc=$?
  if [[ "$rc" -ne 0 && "$FINAL_STATUS_WRITTEN" -eq 0 ]]; then
    printf 'FAILED reason=unexpected_exit_%s %s\n' "$rc" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  fi
  rmdir "$LOCK" 2>/dev/null || true
  exit "$rc"
}
trap cleanup EXIT

set_status() {
  printf '%s %s\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
}
fail() {
  set_status "FAILED reason=$1"
  FINAL_STATUS_WRITTEN=1
  exit 1
}
require_file() {
  [[ -s "$1" ]] || fail "missing_file=$1"
}
file_sha256() {
  sha256sum "$1" | awk '{print $1}'
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
  core/train_fixed_partition_moe.py \
  core/train_fixed_partition_banks.py; do
  require_file "$path"
done
[[ -n "$RUN_SEEDS" ]] || fail empty_run_seeds
[[ "$(file_sha256 "$EXPRESSION_PARQUET")" == "$EXPECTED_EXPRESSION_SHA256" ]] || fail expression_hash
[[ "$(file_sha256 "$MANIFEST")" == "$EXPECTED_MANIFEST_SHA256" ]] || fail manifest_hash
[[ "$(file_sha256 "$POOLED_CHECKPOINT")" == "$EXPECTED_CHECKPOINT_SHA256" ]] || fail checkpoint_hash
[[ "$(file_sha256 "$AXIS_DEFINITIONS")" == "$EXPECTED_AXIS_DEFINITIONS_SHA256" ]] || fail axis_definitions_hash

"$PYTHON_BIN" -m py_compile core/train_fixed_partition_moe.py core/train_fixed_partition_banks.py || fail python_compile
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; r=json.load(open(sys.argv[1])); p=json.load(open(sys.argv[4])); digest=lambda x: hashlib.sha256(open(x,"rb").read()).hexdigest(); expected=sys.argv[5:]; assert r["status"]=="complete" and r["development_only"] is True and r["test_accessed"] is False; assert r["config"]["axes"]==expected; assert r["hashes"]["partition_manifest_sha256"]==digest(sys.argv[2]); assert r["hashes"]["axis_definitions_sha256"]==digest(sys.argv[3]); assert r["hashes"]["protocol_sha256"]==digest(sys.argv[4]); assert p["firewall"]["test_access_allowed"] is False and p["firewall"]["test_cache_allowed"] is False' \
  "$PARTITION_REPORT" "$PARTITION_MANIFEST" "$AXIS_DEFINITIONS" "$PROTOCOL" "${AXES[@]}" \
  || fail partition_contract

for seed in $RUN_SEEDS; do
  case "$seed" in
    17|42|101) ;;
    *) fail "invalid_seed=$seed" ;;
  esac
done
if [[ "$SMOKE_ONLY" == "1" && -z "$MAX_UPDATES_OVERRIDE" ]]; then
  fail smoke_requires_max_updates_override
fi
if [[ "$SMOKE_ONLY" != "1" && -n "$MAX_UPDATES_OVERRIDE" ]]; then
  fail full_run_rejects_max_updates_override
fi

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "ORGAN_K45_WORKER_PREFLIGHT_OK"
  echo "seeds=$RUN_SEEDS"
  echo "output_root=$OUTPUT_ROOT"
  FINAL_STATUS_WRITTEN=1
  exit 0
fi

printf '{"schema_version":1,"protocol":"%s","protocol_sha256":"%s","partition_manifest_sha256":"%s","run_seeds":"%s","code_commit":"%s","launched_at_utc":"%s","development_only":true,"test_accessed":false}\n' \
  "$PROTOCOL" "$(file_sha256 "$PROTOCOL")" "$(file_sha256 "$PARTITION_MANIFEST")" "$RUN_SEEDS" "$CODE_COMMIT" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  > "$OUTPUT_ROOT/worker_provenance.json"

axis_args=()
for axis in "${AXES[@]}"; do
  axis_args+=(--axis "$axis")
done

budget_args=(
  --axis-update-budget organ_k5=1500
  --axis-update-budget organ_k4_epe=1500
  --axis-update-budget organ_k4_total_active=1875
  --axis-update-budget random_group_k5_p17=1500
  --axis-update-budget random_group_k5_p42=1500
  --axis-update-budget random_group_k5_p101=1500
  --axis-update-budget random_group_k4_epe_p17=1500
  --axis-update-budget random_group_k4_epe_p42=1500
  --axis-update-budget random_group_k4_epe_p101=1500
  --axis-update-budget random_group_k4_total_active_p17=1875
  --axis-update-budget random_group_k4_total_active_p42=1875
  --axis-update-budget random_group_k4_total_active_p101=1875
  --axis-target-exposures organ_k5=2400
  --axis-target-exposures organ_k4_epe=2400
  --axis-target-exposures organ_k4_total_active=3000
  --axis-target-exposures random_group_k5_p17=2400
  --axis-target-exposures random_group_k5_p42=2400
  --axis-target-exposures random_group_k5_p101=2400
  --axis-target-exposures random_group_k4_epe_p17=2400
  --axis-target-exposures random_group_k4_epe_p42=2400
  --axis-target-exposures random_group_k4_epe_p101=2400
  --axis-target-exposures random_group_k4_total_active_p17=3000
  --axis-target-exposures random_group_k4_total_active_p42=3000
  --axis-target-exposures random_group_k4_total_active_p101=3000
)

key_args=(
  --axis-expert-key organ_k5=organ:adipose,organ:brain,organ:liver,organ:skeletal_muscle,organ:skin
  --axis-expert-key organ_k4_epe=organ:brain,organ:liver,organ:skeletal_muscle,organ:skin
  --axis-expert-key organ_k4_total_active=organ:brain,organ:liver,organ:skeletal_muscle,organ:skin
  --axis-expert-key random_group_k5_p17=random:k5:p17:0,random:k5:p17:1,random:k5:p17:2,random:k5:p17:3,random:k5:p17:4
  --axis-expert-key random_group_k5_p42=random:k5:p42:0,random:k5:p42:1,random:k5:p42:2,random:k5:p42:3,random:k5:p42:4
  --axis-expert-key random_group_k5_p101=random:k5:p101:0,random:k5:p101:1,random:k5:p101:2,random:k5:p101:3,random:k5:p101:4
  --axis-expert-key random_group_k4_epe_p17=random:k4:p17:0,random:k4:p17:1,random:k4:p17:2,random:k4:p17:3
  --axis-expert-key random_group_k4_epe_p42=random:k4:p42:0,random:k4:p42:1,random:k4:p42:2,random:k4:p42:3
  --axis-expert-key random_group_k4_epe_p101=random:k4:p101:0,random:k4:p101:1,random:k4:p101:2,random:k4:p101:3
  --axis-expert-key random_group_k4_total_active_p17=random:k4:p17:0,random:k4:p17:1,random:k4:p17:2,random:k4:p17:3
  --axis-expert-key random_group_k4_total_active_p42=random:k4:p42:0,random:k4:p42:1,random:k4:p42:2,random:k4:p42:3
  --axis-expert-key random_group_k4_total_active_p101=random:k4:p101:0,random:k4:p101:1,random:k4:p101:2,random:k4:p101:3
)

for seed in $RUN_SEEDS; do
  output="$OUTPUT_ROOT/seed$seed"
  log="$OUTPUT_ROOT/seed$seed.log"
  if [[ -f "$output/COMPLETE" ]]; then
    set_status "RUNNING phase=already_complete seed=$seed"
    continue
  fi
  [[ ! -e "$output" ]] || fail "incomplete_output=$output"
  set_status "RUNNING phase=train seed=$seed"
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
    "${axis_args[@]}" \
    "${budget_args[@]}" \
    "${key_args[@]}" \
    --allow-fallback-label \
    --require-calibration-coverage \
    --output-dir "$output" \
    --research-stage stage1_organ_k45_adaptive_development \
    --experiment packed_genuine_organ_k4_k5_budget_comparison \
    --bank-experiment hard_conditional_residual_experts_k4_k5 \
    --seed "$seed" \
    --adapter-dim 64 \
    --exposures-per-expert 2400 \
    --maximum-exposure-fractional-deviation 0.05 \
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
    || fail "training_seed=$seed"
done

touch "$OUTPUT_ROOT/WORKER_COMPLETE"
set_status COMPLETE
FINAL_STATUS_WRITTEN=1
