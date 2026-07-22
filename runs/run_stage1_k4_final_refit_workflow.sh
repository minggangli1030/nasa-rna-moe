#!/usr/bin/env bash
# End-to-end, metric-free final refit and candidate freeze on persistent storage.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_k4_final_refit/protocol.json}"
SOURCE_ROOT="${SOURCE_ROOT:-/media/volume/moe-reboot/results/stage1_organ_k5_train_20260717T165507Z}"
DEVELOPMENT_DATA_ROOT="${DEVELOPMENT_DATA_ROOT:-/media/volume/moe-reboot/results/stage1_k4_final_refit_development_data_v1}"
EXPRESSION_PARQUET="${EXPRESSION_PARQUET:-$DEVELOPMENT_DATA_ROOT/expression.parquet}"
EXPRESSION_METADATA="${EXPRESSION_METADATA:-$DEVELOPMENT_DATA_ROOT/extraction_report.json}"
DEVELOPMENT_EXTRACTED_MANIFEST="${DEVELOPMENT_EXTRACTED_MANIFEST:-$DEVELOPMENT_DATA_ROOT/manifest.parquet}"
DEVELOPMENT_FIREWALL_REPORT="${DEVELOPMENT_FIREWALL_REPORT:-$DEVELOPMENT_DATA_ROOT/firewall_report.json}"
DEVELOPMENT_DATA_SHA256S="${DEVELOPMENT_DATA_SHA256S:-$DEVELOPMENT_DATA_ROOT/FULL_SHA256SUMS}"
POOLED_CHECKPOINT="${POOLED_CHECKPOINT:-$SOURCE_ROOT/models/pooled/best_model.pt}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage2_utility_axis_pilot_f8ab3cd/axis/axis_definitions.npz}"
K45_ROOT="${K45_ROOT:-/media/volume/moe-reboot/results/stage1_organ_k45_retraining_191192e}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set EXPERIMENT_ROOT to a new persistent result root}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the deployed hexadecimal Git commit}"
MANIFEST="${MANIFEST:-$EXPERIMENT_ROOT/partitions/development_fit_manifest.parquet}"
EXPECTED_PROTOCOL_SHA256=718f4a876ba641e53aaff3ad75db8c70c727db0a086477b13c17487672cbb85b

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: CODE_COMMIT must be the full 40-character Git commit" >&2
  exit 1
}
[[ "$(git rev-parse HEAD 2>/dev/null)" == "$CODE_COMMIT" ]] || {
  echo "ERROR: deployed Git HEAD does not equal CODE_COMMIT" >&2
  exit 1
}
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo "ERROR: deployed tracked Git tree is dirty" >&2
  exit 1
}
EXPECTED_ROOT="/media/volume/moe-reboot/results/stage1_k4_final_refit_${CODE_COMMIT:0:7}"
[[ "$EXPERIMENT_ROOT" == "$EXPECTED_ROOT" ]] || {
  echo "ERROR: EXPERIMENT_ROOT must equal $EXPECTED_ROOT" >&2
  exit 1
}
[[ ! -L "$EXPERIMENT_ROOT" ]] || {
  echo "ERROR: EXPERIMENT_ROOT may not be a symlink" >&2
  exit 1
}

mkdir -p "$EXPERIMENT_ROOT"
[[ "$(realpath -m "$EXPERIMENT_ROOT")" == "$EXPECTED_ROOT" ]] || {
  echo "ERROR: EXPERIMENT_ROOT canonical path changed" >&2
  exit 1
}
STATUS="$EXPERIMENT_ROOT/WORKFLOW_STATUS"
LOCK="$EXPERIMENT_ROOT/workflow.lock"
if [[ -e "$EXPERIMENT_ROOT/FINAL_REFIT_COMPLETE" ]]; then
  [[ -e "$EXPERIMENT_ROOT/READY_FOR_VERIFIED_BACKUP" ]] || {
    echo "ERROR: completion marker exists without backup-ready marker" >&2
    exit 1
  }
  [[ -s "$STATUS" ]] && grep -q '^COMPLETE ' "$STATUS" || {
    echo "ERROR: completion marker exists without COMPLETE workflow status" >&2
    exit 1
  }
  [[ -s "$EXPERIMENT_ROOT/candidate/candidate_manifest.json" ]] || {
    echo "ERROR: completion marker exists without candidate manifest" >&2
    exit 1
  }
  [[ -s "$EXPERIMENT_ROOT/FULL_SHA256SUMS" ]] || {
    echo "ERROR: completion marker exists without checksum manifest" >&2
    exit 1
  }
  [[ -e "$EXPERIMENT_ROOT/candidate/FINAL_CANDIDATE_FROZEN" ]] || {
    echo "ERROR: completion marker exists without frozen-candidate marker" >&2
    exit 1
  }
  (cd "$EXPERIMENT_ROOT" && sha256sum -c FULL_SHA256SUMS >/dev/null) || {
    echo "ERROR: completed final-refit checksum validation failed" >&2
    exit 1
  }
  "$PYTHON_BIN" -c \
    'import sys; sys.path.insert(0,sys.argv[3]); from freeze_stage1_k4_final_candidate import validate_portable_candidate; validate_portable_candidate(sys.argv[1],expected_code_commit=sys.argv[2])' \
    "$EXPERIMENT_ROOT/candidate/candidate_manifest.json" "$CODE_COMMIT" \
    "$ROOT_DIR/evaluation" || {
    echo "ERROR: completed candidate manifest validation failed" >&2
    exit 1
  }
  echo "STAGE1_K4_FINAL_REFIT_ALREADY_COMPLETE"
  exit 0
fi
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "ERROR: workflow lock exists: $LOCK" >&2
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

set_status "RUNNING phase=preflight"
[[ "$(findmnt -n -o TARGET --target "$EXPERIMENT_ROOT")" == "/media/volume/moe-reboot" ]] || fail result_root_not_on_persistent_volume
[[ "$(df -Pk "$EXPERIMENT_ROOT" | awk 'NR==2 {print $4}')" -ge 5242880 ]] || fail insufficient_persistent_disk
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || fail protocol_hash
for path in \
  "$PROTOCOL" \
  "$EXPRESSION_PARQUET" \
  "$EXPRESSION_METADATA" \
  "$DEVELOPMENT_EXTRACTED_MANIFEST" \
  "$DEVELOPMENT_FIREWALL_REPORT" \
  "$DEVELOPMENT_DATA_SHA256S" \
  "$POOLED_CHECKPOINT" \
  "$AXIS_DEFINITIONS" \
  "$K45_ROOT/calibration_evaluation/report.json" \
  runs/prepare_stage1_k4_final_refit.sh \
  runs/run_stage1_k4_final_refit_worker.sh \
  evaluation/refit_stage1_k4_router.py \
  evaluation/freeze_stage1_k4_final_candidate.py; do
  [[ -s "$path" ]] || fail "missing_file=$path"
done
[[ -e "$DEVELOPMENT_DATA_ROOT/DEVELOPMENT_DATA_COMPLETE" ]] || fail development_data_incomplete
[[ "$(sha256sum "$DEVELOPMENT_DATA_SHA256S" | awk '{print $1}')" == "5bcd0c2973aecd7ac1ab119cddf37fd35b674b7a1c4f68b366449260c10c1ee2" ]] || fail development_data_checksum_manifest_hash
(cd "$DEVELOPMENT_DATA_ROOT" && sha256sum -c FULL_SHA256SUMS >/dev/null) || fail development_data_checksum_validation
"$PYTHON_BIN" -m py_compile \
  core/train_manifest.py \
  core/train_fixed_partition_banks.py \
  evaluation/build_stage1_k4_final_refit_manifest.py \
  evaluation/freeze_stage1_k4_random_mappings.py \
  evaluation/refit_stage1_k4_router.py \
  evaluation/freeze_stage1_k4_final_candidate.py \
  || fail python_compile
"$PYTHON_BIN" -c \
  'import torch; assert torch.cuda.is_available(), "CUDA unavailable"; assert torch.cuda.device_count() >= 1; p=torch.cuda.get_device_properties(0); assert "A100" in p.name, p.name; assert p.total_memory >= 39 * 1024**3, p.total_memory; print(f"CUDA_PREFLIGHT_OK device={p.name} memory={p.total_memory}")' \
  > "$EXPERIMENT_ROOT/cuda_preflight.log" 2>&1 \
  || fail cuda_a100_preflight
GPU_USED_MIB="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 0 | tr -d ' ')"
[[ "$GPU_USED_MIB" =~ ^[0-9]+$ && "$GPU_USED_MIB" -le 1024 ]] || fail gpu_not_idle
touch "$EXPERIMENT_ROOT/PREFLIGHT_COMPLETE"

set_status "RUNNING phase=prepare"
EXPERIMENT_ROOT="$EXPERIMENT_ROOT" \
K45_ROOT="$K45_ROOT" \
PROTOCOL="$PROTOCOL" \
PYTHON_BIN="$PYTHON_BIN" \
bash runs/prepare_stage1_k4_final_refit.sh \
  > "$EXPERIMENT_ROOT/prepare.log" 2>&1 \
  || fail prepare
[[ -s "$MANIFEST" ]] || fail missing_runtime_development_manifest

set_status "RUNNING phase=smoke"
EXPERIMENT_ROOT="$EXPERIMENT_ROOT" \
OUTPUT_ROOT="$EXPERIMENT_ROOT/smoke" \
RUN_SEEDS="17" \
MAX_UPDATES_OVERRIDE="2" \
SMOKE_ONLY="1" \
CODE_COMMIT="$CODE_COMMIT" \
PROTOCOL="$PROTOCOL" \
PYTHON_BIN="$PYTHON_BIN" \
DEVELOPMENT_DATA_ROOT="$DEVELOPMENT_DATA_ROOT" \
MANIFEST="$MANIFEST" \
bash runs/run_stage1_k4_final_refit_worker.sh \
  > "$EXPERIMENT_ROOT/smoke.log" 2>&1 \
  || fail smoke
"$PYTHON_BIN" -c \
  'import hashlib,json,pathlib,sys; root=pathlib.Path(sys.argv[1]); d=lambda p:hashlib.sha256(open(p,"rb").read()).hexdigest(); m=json.load(open(root/"seed17/run_metadata.json")); axes=["organ_k4_final","random_group_k4_final_p17","random_group_k4_final_p42","random_group_k4_final_p101","pooled_adapter"]; assert m["status"]=="complete" and m["mechanical_only"] is True and m["internal_efficacy_scoring"] is False and m["test_accessed"] is False and m["external_data_accessed"] is False; assert m["config"]["axes"]==axes and m["config"]["final_refit"] is True and m["config"]["calibration_evaluation_performed"] is False and m["config"]["use_amp"] is True and m["config"]["ordered_schedule_rows"]==16; assert m["hashes"]["fit_schedule_sha256"]==d(root/"seed17/fit_schedule.parquet"); banks=[json.load(open(root/"seed17/banks"/a/"run_metadata.json")) for a in axes]; assert all((root/"seed17/banks"/a/"COMPLETE").exists() and not (root/"seed17/banks"/a/"calibration_scores.npz").exists() for a in axes); assert all(b["external_data_accessed"] is False and b["artifacts"]["all_final_tensors_finite"] is True and b["artifacts"]["checkpoint_roundtrip_verified"] is True for b in banks)' \
  "$EXPERIMENT_ROOT/smoke" || fail smoke_contract
touch "$EXPERIMENT_ROOT/SMOKE_COMPLETE"

set_status "RUNNING phase=final_refit"
EXPERIMENT_ROOT="$EXPERIMENT_ROOT" \
OUTPUT_ROOT="$EXPERIMENT_ROOT/refit" \
RUN_SEEDS="17 42 101" \
CODE_COMMIT="$CODE_COMMIT" \
PROTOCOL="$PROTOCOL" \
PYTHON_BIN="$PYTHON_BIN" \
DEVELOPMENT_DATA_ROOT="$DEVELOPMENT_DATA_ROOT" \
MANIFEST="$MANIFEST" \
bash runs/run_stage1_k4_final_refit_worker.sh \
  > "$EXPERIMENT_ROOT/refit.log" 2>&1 \
  || fail final_refit
touch "$EXPERIMENT_ROOT/REFIT_COMPLETE"

set_status "RUNNING phase=router_refit"
if [[ -e "$EXPERIMENT_ROOT/router/COMPLETE" ]]; then
  "$PYTHON_BIN" -c \
    'import hashlib,json,sys; d=lambda p:hashlib.sha256(open(p,"rb").read()).hexdigest(); r=json.load(open(sys.argv[1])); assert r["status"]=="complete" and r["internal_efficacy_scoring"] is False and r["test_accessed"] is False and r["external_data_accessed"] is False; assert r["hashes"]["router_artifact_sha256"]==d(sys.argv[2]); assert r["hashes"]["protocol_sha256"]==d(sys.argv[3]); assert r["hashes"]["partition_manifest_sha256"]==d(sys.argv[4])' \
    "$EXPERIMENT_ROOT/router/router_report.json" \
    "$EXPERIMENT_ROOT/router/organ_k4_final_router.npz" "$PROTOCOL" \
    "$EXPERIMENT_ROOT/partitions/development_fit_manifest.parquet" \
    || fail existing_router_validation
else
  [[ ! -e "$EXPERIMENT_ROOT/router" ]] || fail incomplete_router_output
  "$PYTHON_BIN" evaluation/refit_stage1_k4_router.py \
    --protocol "$PROTOCOL" \
    --expression-parquet "$EXPRESSION_PARQUET" \
    --expression-metadata "$EXPRESSION_METADATA" \
    --source-manifest "$MANIFEST" \
    --partition-manifest "$EXPERIMENT_ROOT/partitions/development_fit_manifest.parquet" \
    --partition-report "$EXPERIMENT_ROOT/partitions/partition_report.json" \
    --axis-definitions "$AXIS_DEFINITIONS" \
    --output-dir "$EXPERIMENT_ROOT/router" \
    > "$EXPERIMENT_ROOT/router.log" 2>&1 \
    || fail router_refit
fi
touch "$EXPERIMENT_ROOT/ROUTER_FROZEN"

set_status "RUNNING phase=freeze_candidate"
if [[ -e "$EXPERIMENT_ROOT/candidate/FINAL_CANDIDATE_FROZEN" ]]; then
  "$PYTHON_BIN" -c \
    'import sys; sys.path.insert(0,sys.argv[3]); from freeze_stage1_k4_final_candidate import validate_portable_candidate; validate_portable_candidate(sys.argv[1],expected_code_commit=sys.argv[2])' \
    "$EXPERIMENT_ROOT/candidate/candidate_manifest.json" "$CODE_COMMIT" \
    "$ROOT_DIR/evaluation" || fail existing_candidate_validation
else
  [[ ! -e "$EXPERIMENT_ROOT/candidate" ]] || fail incomplete_candidate_output
  "$PYTHON_BIN" evaluation/freeze_stage1_k4_final_candidate.py \
    --protocol "$PROTOCOL" \
    --partition-manifest "$EXPERIMENT_ROOT/partitions/development_fit_manifest.parquet" \
    --partition-report "$EXPERIMENT_ROOT/partitions/partition_report.json" \
    --random-mappings "$EXPERIMENT_ROOT/random_mappings/random_control_mappings.json" \
    --router-artifact "$EXPERIMENT_ROOT/router/organ_k4_final_router.npz" \
    --router-report "$EXPERIMENT_ROOT/router/router_report.json" \
    --pooled-checkpoint "$POOLED_CHECKPOINT" \
    --k45-evaluation-report "$K45_ROOT/calibration_evaluation/report.json" \
    --axis-definitions "$AXIS_DEFINITIONS" \
    --development-expression "$EXPRESSION_PARQUET" \
    --development-expression-metadata "$EXPRESSION_METADATA" \
    --development-extracted-manifest "$DEVELOPMENT_EXTRACTED_MANIFEST" \
    --development-firewall-report "$DEVELOPMENT_FIREWALL_REPORT" \
    --development-data-sha256s "$DEVELOPMENT_DATA_SHA256S" \
    --seed-root "17=$EXPERIMENT_ROOT/refit/seed17" \
    --seed-root "42=$EXPERIMENT_ROOT/refit/seed42" \
    --seed-root "101=$EXPERIMENT_ROOT/refit/seed101" \
    --code-commit "$CODE_COMMIT" \
    --output-dir "$EXPERIMENT_ROOT/candidate" \
    > "$EXPERIMENT_ROOT/freeze_candidate.log" 2>&1 \
    || fail freeze_candidate
fi

set_status "RUNNING phase=checksum"
(
  cd "$EXPERIMENT_ROOT"
  find . -type f \
    ! -name FULL_SHA256SUMS \
    ! -name FULL_SHA256SUMS.tmp \
    ! -name WORKFLOW_STATUS \
    ! -name FINAL_REFIT_COMPLETE \
    ! -name READY_FOR_VERIFIED_BACKUP \
    -print0 \
    | sort -z \
    | xargs -0 sha256sum > FULL_SHA256SUMS.tmp
  mv FULL_SHA256SUMS.tmp FULL_SHA256SUMS
  sha256sum -c FULL_SHA256SUMS >/dev/null
) || fail checksum_validation
set_status COMPLETE
touch "$EXPERIMENT_ROOT/READY_FOR_VERIFIED_BACKUP"
FINAL_STATUS_WRITTEN=1
touch "$EXPERIMENT_ROOT/FINAL_REFIT_COMPLETE"
