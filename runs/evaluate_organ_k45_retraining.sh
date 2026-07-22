#!/usr/bin/env bash
# Evaluate the completed K4/K5 retraining matrix on calibration only.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_organ_k45_retraining/protocol.json}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set EXPERIMENT_ROOT to the persistent experiment root}"
PARTITION_ROOT="${PARTITION_ROOT:-$EXPERIMENT_ROOT/partitions}"
PARTITION_REPORT="${PARTITION_REPORT:-$PARTITION_ROOT/partition_report.json}"
ROUTER_ARTIFACT="${ROUTER_ARTIFACT:-/media/volume/moe-reboot/results/stage1_organ_k_confirmation_53ec6c4/router/organ_k_router.npz}"
ROUTER_REPORT="${ROUTER_REPORT:-/media/volume/moe-reboot/results/stage1_organ_k_confirmation_53ec6c4/router/router_report.json}"
PACKED_ROOT="${PACKED_ROOT:-$EXPERIMENT_ROOT/packed}"
OUTPUT_DIR="${OUTPUT_DIR:-$EXPERIMENT_ROOT/calibration_evaluation}"
BOOTSTRAP_REPS="${BOOTSTRAP_REPS:-2000}"
BOOTSTRAP_SEED="${BOOTSTRAP_SEED:-616161}"
mkdir -p "$EXPERIMENT_ROOT"
STATUS="$EXPERIMENT_ROOT/EVALUATION_STATUS"
LOCK="$EXPERIMENT_ROOT/evaluation.lock"
if ! mkdir "$LOCK" 2>/dev/null; then echo "ERROR: evaluation lock exists: $LOCK" >&2; exit 1; fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT
fail() { printf 'FAILED reason=%s %s\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"; exit 1; }
require_file() { [[ -s "$1" ]] || fail "missing_file=$1"; }
require_marker() { [[ -e "$1" ]] || fail "missing_marker=$1"; }
for path in "$PROTOCOL" "$PARTITION_REPORT" "$ROUTER_ARTIFACT" "$ROUTER_REPORT" evaluation/evaluate_organ_k45_retraining.py; do require_file "$path"; done
for seed in 17 42 101; do require_marker "$PACKED_ROOT/seed$seed/COMPLETE"; done
printf 'RUNNING phase=calibration_only %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
bank_args=()
for seed in 17 42 101; do bank_args+=(--bank-run "$seed=$PACKED_ROOT/seed$seed"); done
"$PYTHON_BIN" evaluation/evaluate_organ_k45_retraining.py \
  --protocol "$PROTOCOL" --partition-report "$PARTITION_REPORT" \
  --router-artifact "$ROUTER_ARTIFACT" --router-report "$ROUTER_REPORT" \
  "${bank_args[@]}" --output-dir "$OUTPUT_DIR" \
  --bootstrap-reps "$BOOTSTRAP_REPS" --bootstrap-seed "$BOOTSTRAP_SEED" \
  > "$EXPERIMENT_ROOT/evaluation.log" 2>&1 || fail calibration_evaluation
touch "$EXPERIMENT_ROOT/EVALUATION_COMPLETE"
printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
cat "$OUTPUT_DIR/report.json"
