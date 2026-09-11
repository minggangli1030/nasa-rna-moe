#!/usr/bin/env bash
# Run the frozen, read-only Stage 2 organ-expert representation audit.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the deployed full Git commit}"
SOURCE_ROOT="${SOURCE_ROOT:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_529c0c3}"
TRAINING_ROOT="${TRAINING_ROOT:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_training_98e2cba}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"
OUTPUT_ROOT="${OUTPUT_ROOT:?set OUTPUT_ROOT to a new persistent output root}"
PROTOCOL="${PROTOCOL:-artifacts/stage2_organ_expert_mechanism/representation_pivot_protocol.json}"
CANDIDATE_LEDGER="${CANDIDATE_LEDGER:-artifacts/stage1_gtex_to_archs4/candidate_ledger.json}"
EXPECTED_PROTOCOL_SHA256="${EXPECTED_PROTOCOL_SHA256:?set EXPECTED_PROTOCOL_SHA256}"

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
  echo "ERROR: representation protocol hash mismatch" >&2
  exit 1
}
[[ ! -e "$OUTPUT_ROOT" ]] || {
  echo "ERROR: output root already exists: $OUTPUT_ROOT" >&2
  exit 1
}
mkdir -p "$OUTPUT_ROOT"
STATUS="$OUTPUT_ROOT/REPRESENTATION_STATUS"
trap 'rc=$?; if [[ $rc -ne 0 ]]; then printf "FAILED exit=%s %s\n" "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"; fi' EXIT

"$PYTHON_BIN" -m py_compile \
  evaluation/extract_stage2_expert_residual_programs.py \
  evaluation/evaluate_stage2_expert_residual_programs.py

printf 'RUNNING phase=extract %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
"$PYTHON_BIN" evaluation/extract_stage2_expert_residual_programs.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --candidate-ledger "$CANDIDATE_LEDGER" \
  --training-root "$TRAINING_ROOT" \
  --expression-parquet "$SOURCE_ROOT/expression/expression.parquet" \
  --extraction-report "$SOURCE_ROOT/expression/extraction_report.json" \
  --manifest "$SOURCE_ROOT/manifest/gtex_training_manifest.parquet" \
  --manifest-report "$SOURCE_ROOT/manifest/manifest_report.json" \
  --axis-definitions "$AXIS_DEFINITIONS" \
  --output-dir "$OUTPUT_ROOT/extraction" \
  --code-commit "$CODE_COMMIT" \
  --device cuda \
  > "$OUTPUT_ROOT/extraction.log" 2>&1

printf 'RUNNING phase=evaluate %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
"$PYTHON_BIN" evaluation/evaluate_stage2_expert_residual_programs.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --seed-cache "$OUTPUT_ROOT/extraction/seed17_gene_scores.npz" \
  --seed-cache "$OUTPUT_ROOT/extraction/seed42_gene_scores.npz" \
  --seed-cache "$OUTPUT_ROOT/extraction/seed101_gene_scores.npz" \
  --output-dir "$OUTPUT_ROOT/evaluation" \
  --code-commit "$CODE_COMMIT" \
  > "$OUTPUT_ROOT/evaluation.log" 2>&1

printf 'COMPLETE decision=%s %s\n' \
  "$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["decision"])' "$OUTPUT_ROOT/evaluation/evaluation_report.json")" \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
touch "$OUTPUT_ROOT/COMPLETE"
