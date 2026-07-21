#!/usr/bin/env bash
# Build the one frozen train-only utility-axis definition; never reads test.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
PROTOCOL="${PROTOCOL:-artifacts/stage2_utility_axis_pilot/protocol.json}"
SOURCE_ROOT="${SOURCE_ROOT:-results/stage1_organ_k5_train_20260717T165507Z}"
EXPRESSION_PARQUET="${EXPRESSION_PARQUET:-$SOURCE_ROOT/expression/expression.parquet}"
EXPRESSION_METADATA="${EXPRESSION_METADATA:-$SOURCE_ROOT/expression/extraction_report.json}"
MANIFEST="${MANIFEST:-$SOURCE_ROOT/expression/manifest.parquet}"
POOLED_CHECKPOINT="${POOLED_CHECKPOINT:-$SOURCE_ROOT/models/pooled/best_model.pt}"
OUTPUT_DIR="${OUTPUT_DIR:-results/stage2_utility_axis_pilot/axis}"
PREFLIGHT_ONLY="${PREFLIGHT_ONLY:-0}"
EXPECTED_EXPRESSION_SHA256=148776bc2d5bbe4a969103de7abab932b7467c804934fc697366ae2c209c0821
EXPECTED_MANIFEST_SHA256=bc4e8e4e36ab0e869fd885197842dc797edad5a08b8093beb21185dbeda7f9cc
EXPECTED_CHECKPOINT_SHA256=080a8a36d2090c3a823cd3995d758d1205b0ad02c1c38c06e6763c5a7ebfd789

STATUS="${OUTPUT_DIR}.status"
LOCK="${OUTPUT_DIR}.lock"
mkdir -p "$(dirname "$OUTPUT_DIR")"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "ERROR: discovery lock exists: $LOCK" >&2
  exit 1
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

set_status() {
  printf '%s %s\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
}
fail() {
  set_status "FAILED reason=$1"
  exit 1
}
require_file() {
  [[ -s "$1" ]] || fail "missing_file=$1"
}

for path in "$PROTOCOL" "$EXPRESSION_PARQUET" "$EXPRESSION_METADATA" "$MANIFEST" "$POOLED_CHECKPOINT" evaluation/build_utility_axis_partitions.py core/train_latent_moe.py; do
  require_file "$path"
done
[[ "$(sha256sum "$EXPRESSION_PARQUET" | awk '{print $1}')" == "$EXPECTED_EXPRESSION_SHA256" ]] || fail expression_hash
[[ "$(sha256sum "$MANIFEST" | awk '{print $1}')" == "$EXPECTED_MANIFEST_SHA256" ]] || fail manifest_hash
[[ "$(sha256sum "$POOLED_CHECKPOINT" | awk '{print $1}')" == "$EXPECTED_CHECKPOINT_SHA256" ]] || fail checkpoint_hash
"$PYTHON_BIN" -m py_compile evaluation/build_utility_axis_partitions.py core/train_fixed_partition_moe.py core/train_fixed_partition_banks.py
"$PYTHON_BIN" -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p["candidate_family"]["primary"] == "head_gradient_k2"; assert p["data"]["test_access_before_pass"] is False; assert p["gene_firewall"]["require_probe_score_disjoint"] is True' "$PROTOCOL"

if [[ "$PREFLIGHT_ONLY" == "1" ]]; then
  echo "UTILITY_AXIS_DISCOVERY_PREFLIGHT_OK"
  echo "python=$PYTHON_BIN"
  echo "output=$OUTPUT_DIR"
  exit 0
fi

[[ ! -e "$OUTPUT_DIR" ]] || fail "output_exists=$OUTPUT_DIR"
set_status "RUNNING phase=axis_discovery"
"$PYTHON_BIN" evaluation/build_utility_axis_partitions.py \
  --expression-parquet "$EXPRESSION_PARQUET" \
  --expression-metadata "$EXPRESSION_METADATA" \
  --manifest "$MANIFEST" \
  --pooled-checkpoint "$POOLED_CHECKPOINT" \
  --protocol "$PROTOCOL" \
  --output-dir "$OUTPUT_DIR" \
  --axis-seed 314159 \
  --primary-candidate head_gradient_k2 \
  --k-values 2 3 \
  --probe-fraction 0.10 \
  --score-fraction 0.30 \
  --pca-components 32 \
  --cluster-restarts 3 \
  --batch-size 8 \
  --device auto \
  > "${OUTPUT_DIR}.log" 2>&1 \
  || fail axis_discovery
[[ -f "$OUTPUT_DIR/COMPLETE" ]] || fail missing_complete_marker
set_status COMPLETE
cat "$OUTPUT_DIR/partition_report.json"
