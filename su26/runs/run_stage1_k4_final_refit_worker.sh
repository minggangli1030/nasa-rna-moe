#!/usr/bin/env bash
# Fit the frozen K4 candidate and matched controls with no internal efficacy scoring.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_k4_final_refit/protocol.json}"
DEVELOPMENT_DATA_ROOT="${DEVELOPMENT_DATA_ROOT:-/media/volume/moe-reboot/results/stage1_k4_final_refit_development_data_v1}"
EXPRESSION_PARQUET="${EXPRESSION_PARQUET:-$DEVELOPMENT_DATA_ROOT/expression.parquet}"
EXPRESSION_METADATA="${EXPRESSION_METADATA:-$DEVELOPMENT_DATA_ROOT/extraction_report.json}"
DEVELOPMENT_FIREWALL_REPORT="${DEVELOPMENT_FIREWALL_REPORT:-$DEVELOPMENT_DATA_ROOT/firewall_report.json}"
DEVELOPMENT_DATA_SHA256S="${DEVELOPMENT_DATA_SHA256S:-$DEVELOPMENT_DATA_ROOT/FULL_SHA256SUMS}"
SOURCE_ROOT="${SOURCE_ROOT:-/media/volume/moe-reboot/results/stage1_organ_k5_train_20260717T165507Z}"
POOLED_CHECKPOINT="${POOLED_CHECKPOINT:-$SOURCE_ROOT/models/pooled/best_model.pt}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage2_utility_axis_pilot_f8ab3cd/axis/axis_definitions.npz}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set EXPERIMENT_ROOT to the persistent final-refit root}"
PARTITION_MANIFEST="${PARTITION_MANIFEST:-$EXPERIMENT_ROOT/partitions/development_fit_manifest.parquet}"
PARTITION_REPORT="${PARTITION_REPORT:-$EXPERIMENT_ROOT/partitions/partition_report.json}"
MANIFEST="${MANIFEST:-$PARTITION_MANIFEST}"
OUTPUT_ROOT="${OUTPUT_ROOT:-$EXPERIMENT_ROOT/refit}"
RUN_SEEDS="${RUN_SEEDS:-}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"
MAX_UPDATES_OVERRIDE="${MAX_UPDATES_OVERRIDE:-}"
SMOKE_ONLY="${SMOKE_ONLY:-0}"
CODE_COMMIT="${CODE_COMMIT:-unknown}"

EXPECTED_EXPRESSION_SHA256=74ee6438a32bf62c0227af4a3e73f853697b95e8bea80d844cabd67f261c7df0
EXPECTED_EXPRESSION_METADATA_SHA256=5537ff8964415e547962be20ae0dec34171863dffe926fed7b8f6a83ad2a4415
EXPECTED_MANIFEST_SHA256=c6173aa4c7d5e8d62923a046c521a45a6e734f5f83017003b68f4afeb06261ba
EXPECTED_FIREWALL_REPORT_SHA256=d26edcbc9cdee9c809c0a56e999bc7ebd7a6b473855cd3741df2d6c9d77cca36
EXPECTED_DEVELOPMENT_SHA256S_SHA256=5bcd0c2973aecd7ac1ab119cddf37fd35b674b7a1c4f68b366449260c10c1ee2
EXPECTED_CHECKPOINT_SHA256=080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789
EXPECTED_AXIS_DEFINITIONS_SHA256=1d7fba55d00f3fe363932abfba2a0e0d76e70e8dedf71aa46c69e29679b0b7cb
EXPECTED_PROTOCOL_SHA256=718f4a876ba641e53aaff3ad75db8c70c727db0a086477b13c17487672cbb85b

AXES=(
  organ_k4_final
  random_group_k4_final_p17
  random_group_k4_final_p42
  random_group_k4_final_p101
  pooled_adapter
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
  "$DEVELOPMENT_FIREWALL_REPORT" \
  "$DEVELOPMENT_DATA_SHA256S" \
  "$AXIS_DEFINITIONS" \
  core/train_fixed_partition_moe.py \
  core/train_fixed_partition_banks.py; do
  require_file "$path"
done
[[ -n "$RUN_SEEDS" ]] || fail empty_run_seeds
[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail invalid_code_commit
[[ "$(git rev-parse HEAD 2>/dev/null)" == "$CODE_COMMIT" ]] || fail deployed_commit_mismatch
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || fail tracked_tree_dirty
[[ "$(file_sha256 "$PROTOCOL")" == "$EXPECTED_PROTOCOL_SHA256" ]] || fail protocol_hash
[[ "$(file_sha256 "$EXPRESSION_PARQUET")" == "$EXPECTED_EXPRESSION_SHA256" ]] || fail expression_hash
[[ "$(file_sha256 "$EXPRESSION_METADATA")" == "$EXPECTED_EXPRESSION_METADATA_SHA256" ]] || fail expression_metadata_hash
[[ "$(file_sha256 "$MANIFEST")" == "$EXPECTED_MANIFEST_SHA256" ]] || fail manifest_hash
[[ "$(file_sha256 "$DEVELOPMENT_FIREWALL_REPORT")" == "$EXPECTED_FIREWALL_REPORT_SHA256" ]] || fail development_firewall_report_hash
[[ "$(file_sha256 "$DEVELOPMENT_DATA_SHA256S")" == "$EXPECTED_DEVELOPMENT_SHA256S_SHA256" ]] || fail development_checksum_manifest_hash
[[ -e "$DEVELOPMENT_DATA_ROOT/DEVELOPMENT_DATA_COMPLETE" ]] || fail development_data_incomplete
(cd "$DEVELOPMENT_DATA_ROOT" && sha256sum -c FULL_SHA256SUMS >/dev/null) || fail development_data_checksum_validation
[[ "$(file_sha256 "$POOLED_CHECKPOINT")" == "$EXPECTED_CHECKPOINT_SHA256" ]] || fail checkpoint_hash
[[ "$(file_sha256 "$AXIS_DEFINITIONS")" == "$EXPECTED_AXIS_DEFINITIONS_SHA256" ]] || fail axis_definitions_hash

"$PYTHON_BIN" -m py_compile core/train_manifest.py core/train_fixed_partition_moe.py core/train_fixed_partition_banks.py || fail python_compile
"$PYTHON_BIN" -c \
  'import hashlib,json,sys; r=json.load(open(sys.argv[1])); p=json.load(open(sys.argv[4])); digest=lambda x:hashlib.sha256(open(x,"rb").read()).hexdigest(); expected=sys.argv[5:]; assert r["status"]=="complete" and r["internal_efficacy_scoring"] is False and r["test_accessed"] is False; assert r["config"]["axes"]==expected; assert r["hashes"]["partition_manifest_sha256"]==digest(sys.argv[2])==p["data"]["development_fit_manifest_sha256"]; assert r["hashes"]["axis_definitions_sha256"]==digest(sys.argv[3]); assert r["hashes"]["protocol_sha256"]==digest(sys.argv[4]); assert p["training"]["training_seeds"]==[17,42,101] and p["training"]["scheduled_updates"]==1500; assert p["firewall"]["test_access_allowed"] is False and p["firewall"]["external_access_allowed_during_refit"] is False' \
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
  echo "STAGE1_K4_FINAL_WORKER_PREFLIGHT_OK"
  echo "seeds=$RUN_SEEDS"
  FINAL_STATUS_WRITTEN=1
  exit 0
fi

if [[ -e "$OUTPUT_ROOT/worker_provenance.json" ]]; then
  "$PYTHON_BIN" -c \
    'import hashlib,json,sys; d=lambda p:hashlib.sha256(open(p,"rb").read()).hexdigest(); r=json.load(open(sys.argv[1])); assert r["protocol_sha256"]==d(sys.argv[2]) and r["partition_manifest_sha256"]==d(sys.argv[3]) and r["code_commit"]==sys.argv[4] and r["run_seeds"]==sys.argv[5] and r["final_refit"] is True and r["internal_efficacy_scoring"] is False and r["test_accessed"] is False and r["external_data_accessed"] is False' \
    "$OUTPUT_ROOT/worker_provenance.json" "$PROTOCOL" "$PARTITION_MANIFEST" \
    "$CODE_COMMIT" "$RUN_SEEDS" || fail existing_worker_provenance
else
  printf '{"schema_version":1,"protocol":"%s","protocol_sha256":"%s","partition_manifest_sha256":"%s","run_seeds":"%s","code_commit":"%s","launched_at_utc":"%s","final_refit":true,"internal_efficacy_scoring":false,"test_accessed":false,"external_data_accessed":false}\n' \
    "$PROTOCOL" "$(file_sha256 "$PROTOCOL")" "$(file_sha256 "$PARTITION_MANIFEST")" "$RUN_SEEDS" "$CODE_COMMIT" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
    > "$OUTPUT_ROOT/worker_provenance.json"
fi

axis_args=()
for axis in "${AXES[@]}"; do
  axis_args+=(--axis "$axis")
done
budget_args=(
  --axis-update-budget organ_k4_final=1500
  --axis-update-budget random_group_k4_final_p17=1500
  --axis-update-budget random_group_k4_final_p42=1500
  --axis-update-budget random_group_k4_final_p101=1500
  --axis-update-budget pooled_adapter=1500
  --axis-target-exposures organ_k4_final=2400
  --axis-target-exposures random_group_k4_final_p17=2400
  --axis-target-exposures random_group_k4_final_p42=2400
  --axis-target-exposures random_group_k4_final_p101=2400
  --axis-target-exposures pooled_adapter=12000
)
key_args=(
  --axis-expert-key organ_k4_final=organ:brain,organ:liver,organ:skeletal_muscle,organ:skin
  --axis-expert-key random_group_k4_final_p17=random:k4:p17:0,random:k4:p17:1,random:k4:p17:2,random:k4:p17:3
  --axis-expert-key random_group_k4_final_p42=random:k4:p42:0,random:k4:p42:1,random:k4:p42:2,random:k4:p42:3
  --axis-expert-key random_group_k4_final_p101=random:k4:p101:0,random:k4:p101:1,random:k4:p101:2,random:k4:p101:3
  --axis-expert-key pooled_adapter=control:pooled_residual
)

for seed in $RUN_SEEDS; do
  output="$OUTPUT_ROOT/seed$seed"
  log="$OUTPUT_ROOT/seed$seed.log"
  if [[ -f "$output/COMPLETE" ]]; then
    "$PYTHON_BIN" -c \
      'import hashlib,json,pathlib,sys; root=pathlib.Path(sys.argv[1]); seed=int(sys.argv[2]); commit=sys.argv[3]; digest=lambda p:hashlib.sha256(open(p,"rb").read()).hexdigest(); axes=sys.argv[7:]; m=json.load(open(root/"run_metadata.json")); assert m["status"]=="complete" and m["training_seed"]==seed and m["code_commit"]==commit and m["mechanical_only"] is (sys.argv[5]=="1") and m["internal_efficacy_scoring"] is False and m["test_accessed"] is False and m["external_data_accessed"] is False; assert m["config"]["axes"]==axes and m["config"]["final_refit"] is True and m["config"]["calibration_evaluation_performed"] is False and m["config"]["sampling_mode"]=="organ_sample_balanced"; assert m["hashes"]["protocol_sha256"]==digest(sys.argv[4]) and m["hashes"]["partition_manifest_sha256"]==digest(sys.argv[6]); assert all(m["hashes"][key]==digest(root/name) for name,key in (("fit_exposures.parquet","fit_exposures_sha256"),("fit_exposure_report.json","fit_exposure_report_sha256"),("fit_schedule.parquet","fit_schedule_sha256"))); [((lambda b,p: (b["status"]=="complete" and b["training_seed"]==seed and b["code_commit"]==commit and b["internal_efficacy_scoring"] is False and b["test_accessed"] is False and b["external_data_accessed"] is False and b["artifacts"]["all_final_tensors_finite"] is True and b["artifacts"]["checkpoint_roundtrip_verified"] is True and b["artifacts"]["final_experts_sha256"]==digest(p)))(json.load(open(root/"banks"/a/"run_metadata.json")),root/"banks"/a/"final_experts.pt") or (_ for _ in ()).throw(AssertionError(a))) for a in axes]' \
      "$output" "$seed" "$CODE_COMMIT" "$PROTOCOL" "$SMOKE_ONLY" \
      "$PARTITION_MANIFEST" "${AXES[@]}" \
      || fail "completed_seed_validation=$seed"
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
    --final-refit \
    --sampling-mode organ_sample_balanced \
    --output-dir "$output" \
    --research-stage final_refit_for_external_confirmation \
    --experiment packed_stage1_k4_final_refit \
    --bank-experiment hard_conditional_stage1_k4_final_refit \
    --seed "$seed" \
    --code-commit "$CODE_COMMIT" \
    --adapter-dim 64 \
    --exposures-per-expert 2400 \
    --maximum-exposure-fractional-deviation 0.05 \
    --batch-size 8 \
    --validation-batch-size 8 \
    --mask-ratio 0.30 \
    --learning-rate 0.001 \
    --weight-decay 0.01 \
    --device cuda:0 \
    --use-amp \
    "${extra[@]}" \
    > "$log" 2>&1 \
    || fail "training_seed=$seed"
done

touch "$OUTPUT_ROOT/WORKER_COMPLETE"
set_status COMPLETE
FINAL_STATUS_WRITTEN=1
