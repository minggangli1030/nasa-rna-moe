#!/usr/bin/env bash
# Execute the frozen read-only D1 OSDR encoder-validity audit.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set exact deployed commit}"
OUTPUT_DIR="${OUTPUT_DIR:?set a new persistent output directory}"
PROTOCOL="${PROTOCOL:-artifacts/final_evaluation/encoder_validity_audit/protocol_v2.json}"
EXPECTED_PROTOCOL_SHA256=e959ef694a83d2b8b2df6f50d20101ea467967bb30d6c1120b3fac44983b819f
OSDR_ROOT="${OSDR_ROOT:-/media/volume/moe-reboot/results/stage1_osdr_downstream_5884756/osdr_cohort}"
OSDR_FEATURE_ROOT="${OSDR_FEATURE_ROOT:-/media/volume/moe-reboot/results/final_organ_embedding_3f681fd/features}"
GTEX_SOURCE="${GTEX_SOURCE:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_529c0c3}"
GTEX_CACHE_ROOT="${GTEX_CACHE_ROOT:-/media/volume/moe-reboot/results/stage2b_diagnostics_20d000e}"
AXIS_DEFINITIONS="${AXIS_DEFINITIONS:-/media/volume/moe-reboot/results/stage1_k4_final_refit_e8c0383/candidate/bundle/axis_definitions.npz}"

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || exit 2
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || exit 2
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || exit 2
[[ ! -e "$OUTPUT_DIR" ]] || exit 2

"$PYTHON_BIN" -m py_compile evaluation/audit_osdr_encoder_validity.py
"$PYTHON_BIN" -c \
  'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"]=="frozen_before_encoder_validity_audit"; assert p["firewalls"]["model_training"] is False; assert p["firewalls"]["archs4_expression_access"] is False' \
  "$PROTOCOL"

extra=()
if [[ "${SMOKE:-0}" == "1" ]]; then
  extra+=(--smoke)
fi

"$PYTHON_BIN" evaluation/audit_osdr_encoder_validity.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --osdr-feature-root "$OSDR_FEATURE_ROOT" \
  --osdr-cohort-root "$OSDR_ROOT" \
  --gtex-expression "$GTEX_SOURCE/expression/expression.parquet" \
  --gtex-manifest "$GTEX_SOURCE/manifest/gtex_training_manifest.parquet" \
  --gtex-extraction-report "$GTEX_SOURCE/expression/extraction_report.json" \
  --axis-definitions "$AXIS_DEFINITIONS" \
  --canonical-genes data/ensembl/canonical_genes_shared.txt \
  --training-ortholog-map data/ensembl/orthologs_one2one.txt \
  --osdr-ortholog-table data/osdr/human_mouse_orthologs.csv \
  --mouse-exon-lengths data/gencode/gencode_v49_mouse_gene_exon_lengths.csv \
  --gtex-cache "17=$GTEX_CACHE_ROOT/seed17/canonical_cache.npz" \
  --gtex-cache "42=$GTEX_CACHE_ROOT/seed42/canonical_cache.npz" \
  --gtex-cache "101=$GTEX_CACHE_ROOT/seed101_secondary/canonical_cache.npz" \
  --output-dir "$OUTPUT_DIR" \
  "${extra[@]}"

(cd "$OUTPUT_DIR" && sha256sum -c IMMUTABLE_SHA256SUMS)
