#!/usr/bin/env bash
# Freeze the metadata-only fitting manifest and held-out random-control mappings.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_k4_final_refit/protocol.json}"
K45_ROOT="${K45_ROOT:-/media/volume/moe-reboot/results/stage1_organ_k45_retraining_191192e}"
SOURCE_PARTITIONS="${SOURCE_PARTITIONS:-$K45_ROOT/partitions/train_cal_partitions.parquet}"
SOURCE_PARTITION_REPORT="${SOURCE_PARTITION_REPORT:-$K45_ROOT/partitions/partition_report.json}"
K45_EVALUATION_REPORT="${K45_EVALUATION_REPORT:-$K45_ROOT/calibration_evaluation/report.json}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set EXPERIMENT_ROOT to a new persistent result root}"
PARTITION_ROOT="${PARTITION_ROOT:-$EXPERIMENT_ROOT/partitions}"
MAPPING_ROOT="${MAPPING_ROOT:-$EXPERIMENT_ROOT/random_mappings}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"
EXPECTED_PROTOCOL_SHA256=718f4a876ba641e53aaff3ad75db8c70c727db0a086477b13c17487672cbb85b

STATUS="$EXPERIMENT_ROOT/PREPARE_STATUS"
LOCK="$EXPERIMENT_ROOT/prepare.lock"
mkdir -p "$EXPERIMENT_ROOT"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "ERROR: preparation lock exists: $LOCK" >&2
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

for path in \
  "$PROTOCOL" \
  "$SOURCE_PARTITIONS" \
  "$SOURCE_PARTITION_REPORT" \
  "$K45_EVALUATION_REPORT" \
  evaluation/build_stage1_k4_final_refit_manifest.py \
  evaluation/freeze_stage1_k4_random_mappings.py; do
  require_file "$path"
done
for marker in \
  "$K45_ROOT/packed/seed17/COMPLETE" \
  "$K45_ROOT/packed/seed42/COMPLETE" \
  "$K45_ROOT/packed/seed101/COMPLETE"; do
  [[ -e "$marker" ]] || fail "missing_marker=$marker"
done
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || fail protocol_hash

"$PYTHON_BIN" -m py_compile \
  evaluation/build_stage1_k4_final_refit_manifest.py \
  evaluation/freeze_stage1_k4_random_mappings.py \
  || fail python_compile
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["authorization"]["requested_by_user"] is True; assert p["evidence_label"]["label"]=="final_refit_for_external_confirmation" and p["evidence_label"]["internal_efficacy_scoring"] is False; assert p["prior_evidence"]["decision_branch"]=="k4_robust" and p["prior_evidence"]["selected_candidate"]=="k4_epe"; assert p["data"]["fitting_pool"]=="balanced_train_plus_calibration" and p["data"]["expected_fit_samples"]==2657; assert p["firewall"]["test_access_allowed"] is False and p["firewall"]["external_access_allowed_during_refit"] is False' \
  "$PROTOCOL" || fail protocol_contract

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "STAGE1_K4_FINAL_PREPARE_PREFLIGHT_OK"
  FINAL_STATUS_WRITTEN=1
  exit 0
fi

if [[ -e "$PARTITION_ROOT/COMPLETE" ]]; then
  set_status "RUNNING phase=validate_existing_partitions"
  "$PYTHON_BIN" -c \
    'import hashlib,json,sys; d=lambda p:hashlib.sha256(open(p,"rb").read()).hexdigest(); r=json.load(open(sys.argv[1])); assert r["status"]=="complete" and r["internal_efficacy_scoring"] is False and r["test_accessed"] is False; assert r["hashes"]["partition_manifest_sha256"]==d(sys.argv[2]); assert r["hashes"]["protocol_sha256"]==d(sys.argv[3]); assert r["hashes"]["source_k45_partition_manifest_sha256"]==d(sys.argv[4]); assert r["hashes"]["source_k45_partition_report_sha256"]==d(sys.argv[5]); assert r["hashes"]["k45_evaluation_report_sha256"]==d(sys.argv[6])' \
    "$PARTITION_ROOT/partition_report.json" \
    "$PARTITION_ROOT/development_fit_manifest.parquet" \
    "$PROTOCOL" "$SOURCE_PARTITIONS" "$SOURCE_PARTITION_REPORT" \
    "$K45_EVALUATION_REPORT" || fail existing_partition_validation
else
  [[ ! -e "$PARTITION_ROOT" ]] || fail "incomplete_partition_output=$PARTITION_ROOT"
  set_status "RUNNING phase=build_partitions"
  "$PYTHON_BIN" evaluation/build_stage1_k4_final_refit_manifest.py \
    --protocol "$PROTOCOL" \
    --source-partition-manifest "$SOURCE_PARTITIONS" \
    --source-partition-report "$SOURCE_PARTITION_REPORT" \
    --k45-evaluation-report "$K45_EVALUATION_REPORT" \
    --output-dir "$PARTITION_ROOT" \
    > "$EXPERIMENT_ROOT/prepare_partitions.log" 2>&1 \
    || fail build_partitions
fi

if [[ -e "$MAPPING_ROOT/COMPLETE" ]]; then
  set_status "RUNNING phase=validate_existing_random_mappings"
  "$PYTHON_BIN" -c \
    'import hashlib,json,sys; d=lambda p:hashlib.sha256(open(p,"rb").read()).hexdigest(); r=json.load(open(sys.argv[1])); assert r["status"]=="complete" and r["candidate_selection"] is False and r["test_accessed"] is False and r["external_data_accessed"] is False; assert r["hashes"]["protocol_sha256"]==d(sys.argv[2]); assert r["hashes"]["k45_evaluation_report_sha256"]==d(sys.argv[3]); assert set(r["mappings"])=={"17","42","101"}; organs=("brain","liver","skeletal_muscle","skin"); [((lambda item: (item["organ_to_expert"]["adipose"]==-1 and all(item["organ_to_expert"][organ]==min(range(4),key=lambda i:(item["equal_study_mse_by_organ_and_expert"][organ][i],i)) for organ in organs)))(item) or (_ for _ in ()).throw(AssertionError(seed))) for seed,item in r["mappings"].items()]' \
    "$MAPPING_ROOT/random_control_mappings.json" "$PROTOCOL" \
    "$K45_EVALUATION_REPORT" || fail existing_mapping_validation
else
  [[ ! -e "$MAPPING_ROOT" ]] || fail "incomplete_mapping_output=$MAPPING_ROOT"
  set_status "RUNNING phase=freeze_random_mappings"
  "$PYTHON_BIN" evaluation/freeze_stage1_k4_random_mappings.py \
    --protocol "$PROTOCOL" \
    --k45-evaluation-report "$K45_EVALUATION_REPORT" \
    --seed-root "17=$K45_ROOT/packed/seed17" \
    --seed-root "42=$K45_ROOT/packed/seed42" \
    --seed-root "101=$K45_ROOT/packed/seed101" \
    --output-dir "$MAPPING_ROOT" \
    > "$EXPERIMENT_ROOT/freeze_random_mappings.log" 2>&1 \
    || fail freeze_random_mappings
fi

touch "$EXPERIMENT_ROOT/FINAL_PROTOCOL_FROZEN"
touch "$EXPERIMENT_ROOT/FINAL_INPUTS_FROZEN"
touch "$EXPERIMENT_ROOT/PREPARE_COMPLETE"
set_status COMPLETE
FINAL_STATUS_WRITTEN=1
