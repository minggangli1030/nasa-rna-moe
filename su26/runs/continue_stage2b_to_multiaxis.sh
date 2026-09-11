#!/usr/bin/env bash
# Fail-closed primary-VM continuation from immutable Stage 2B caches to B0-B4
# evaluation and the first multiaxis inventory. This script never accesses
# calibration or ARCHS4 expression and never updates a neural checkpoint.
set -euo pipefail

CODE_COMMIT="20d000e0b8055f60d7dee8796b52834bd829ab43"
PROTOCOL_SHA256="db7cd772345272876cd01a603deb720b46c36d0cfb5252e3d245e7e58f5182be"
WORKTREE="/media/volume/moe-reboot/worktrees/stage2b_diagnostics_20d000e"
RESULT_ROOT="/media/volume/moe-reboot/results/stage2b_diagnostics_20d000e"
PROTOCOL="/media/volume/moe-reboot/results/stage2b_diagnostic_protocol_20d000e.json"
SOURCE_ROOT="/media/volume/moe-reboot/results/stage1_gtex_to_archs4_529c0c3"
MANIFEST="$SOURCE_ROOT/manifest/gtex_training_manifest.parquet"
AXIS_DEFINITIONS="/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz"
BASIS_BUNDLE="$WORKTREE/artifacts/stage2_organ_expert_mechanism/aligned_program_basis.npz"
PYTHON_BIN="/home/exouser/moe-env/bin/python3"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREPARE_SCRIPT="$SCRIPT_DIR/prepare_multiaxis_smoke.py"

SEED17="$RESULT_ROOT/seed17"
SEED42="$RESULT_ROOT/seed42"
SEED101="$RESULT_ROOT/seed101_secondary"
EVALUATION="$RESULT_ROOT/b0_b4"
INVENTORY="$RESULT_ROOT/multiaxis_tier0_inventory"
STATUS="$RESULT_ROOT/CONTINUATION_STATUS"
LOG="$RESULT_ROOT/continuation_to_multiaxis.log"

exec > >(tee -a "$LOG") 2>&1

status() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee "$STATUS"
}

fail() {
  status "CRITICAL $*"
  exit 1
}

verify_seed() {
  local seed="$1"
  local root="$2"
  [[ -f "$root/COMPLETE" ]] || fail "seed $seed lacks COMPLETE"
  (
    cd "$root"
    sha256sum -c IMMUTABLE_SHA256SUMS
  ) || fail "seed $seed immutable checksum failure"
  "$PYTHON_BIN" - "$root/run_metadata.json" "$seed" "$PROTOCOL_SHA256" <<'PY'
import json
import sys

path, expected_seed, expected_protocol = sys.argv[1:]
record = json.load(open(path))
assert record["status"] == "complete"
assert record["mechanical_only"] is False
assert int(record["rows"]) == 7369
assert int(record["seed"]) == int(expected_seed)
assert record["protocol_sha256"] == expected_protocol
assert record["determinism"] == "bitwise_identical"
PY
}

status "WAITING seed42_complete"
while [[ ! -f "$SEED42/COMPLETE" ]]; do
  if ! pgrep -f "extract_stage2b_canonical_training_cache.py extract.*--seed 42" >/dev/null; then
    fail "seed42 incomplete and extraction process absent"
  fi
  sleep 20
done

status "VERIFYING three_seed_caches"
[[ "$(git -C "$WORKTREE" rev-parse HEAD)" == "$CODE_COMMIT" ]] \
  || fail "worktree commit mismatch"
[[ -z "$(git -C "$WORKTREE" status --porcelain --untracked-files=no)" ]] \
  || fail "tracked worktree changes detected"
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$PROTOCOL_SHA256" ]] \
  || fail "protocol hash mismatch"
verify_seed 17 "$SEED17"
verify_seed 42 "$SEED42"
verify_seed 101 "$SEED101"

if [[ -e "$EVALUATION" && ! -f "$EVALUATION/COMPLETE" ]]; then
  fail "incomplete B0-B4 output already exists at $EVALUATION"
fi
if [[ ! -e "$EVALUATION" ]]; then
  status "RUNNING frozen_b0_b4_evaluation"
  cd "$WORKTREE"
  "$PYTHON_BIN" evaluation/evaluate_stage2b_diagnostics.py \
    --protocol "$PROTOCOL" \
    --expected-protocol-sha256 "$PROTOCOL_SHA256" \
    --manifest "$MANIFEST" \
    --axis-definitions "$AXIS_DEFINITIONS" \
    --basis-bundle "$BASIS_BUNDLE" \
    --cache-root "17=$SEED17" \
    --cache-root "42=$SEED42" \
    --cache-root "101=$SEED101" \
    --output-dir "$EVALUATION"
fi
(
  cd "$EVALUATION"
  sha256sum -c IMMUTABLE_SHA256SUMS
) || fail "B0-B4 immutable checksum failure"

if [[ -e "$INVENTORY" && ! -f "$INVENTORY/COMPLETE" ]]; then
  fail "incomplete multiaxis inventory already exists at $INVENTORY"
fi
if [[ ! -e "$INVENTORY" ]]; then
  status "RUNNING multiaxis_tier0_inventory"
  "$PYTHON_BIN" "$PREPARE_SCRIPT" \
    --manifest "$MANIFEST" \
    --b0-b4-report "$EVALUATION/b0_b4_report.json" \
    --output-dir "$INVENTORY"
fi
(
  cd "$INVENTORY"
  sha256sum -c IMMUTABLE_SHA256SUMS
) || fail "multiaxis inventory immutable checksum failure"

status "COMPLETE b0_b4_and_multiaxis_tier0"
