#!/usr/bin/env bash
# Run the frozen multi-scale, tissue-attribute representation audit.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT}"
EXPECTED_PROTOCOL_SHA256="${EXPECTED_PROTOCOL_SHA256:?set EXPECTED_PROTOCOL_SHA256}"
OUTPUT_ROOT="${OUTPUT_ROOT:?set OUTPUT_ROOT}"
SOURCE_ROOT="${SOURCE_ROOT:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_529c0c3}"
PARENT_ROOT="${PARENT_ROOT:-/media/volume/moe-reboot/results/stage2_representation_pivot_d90550e}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"
PROTOCOL="${PROTOCOL:-artifacts/stage2_organ_expert_mechanism/multiscale_attribute_protocol.json}"

[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || exit 2
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || exit 2
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || exit 2
[[ ! -e "$OUTPUT_ROOT" ]] || exit 2
mkdir -p "$OUTPUT_ROOT"
STATUS="$OUTPUT_ROOT/MULTISCALE_STATUS"
trap 'rc=$?; if [[ $rc -ne 0 ]]; then printf "FAILED exit=%s %s\n" "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"; fi' EXIT
printf 'RUNNING %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"

"$PYTHON_BIN" -m py_compile evaluation/evaluate_stage2_multiscale_attributes.py
"$PYTHON_BIN" evaluation/evaluate_stage2_multiscale_attributes.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --seed-cache "$PARENT_ROOT/extraction/seed17_gene_scores.npz" \
  --seed-cache "$PARENT_ROOT/extraction/seed42_gene_scores.npz" \
  --seed-cache "$PARENT_ROOT/extraction/seed101_gene_scores.npz" \
  --expression-parquet "$SOURCE_ROOT/expression/expression.parquet" \
  --manifest "$SOURCE_ROOT/manifest/gtex_training_manifest.parquet" \
  --axis-definitions "$AXIS_DEFINITIONS" \
  --output-dir "$OUTPUT_ROOT/evaluation" \
  --code-commit "$CODE_COMMIT" \
  > "$OUTPUT_ROOT/evaluation.log" 2>&1

printf 'COMPLETE decision=%s %s\n' \
  "$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1]))["decision"])' "$OUTPUT_ROOT/evaluation/evaluation_report.json")" \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
touch "$OUTPUT_ROOT/COMPLETE"
