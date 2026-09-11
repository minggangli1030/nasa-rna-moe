#!/usr/bin/env bash
# Execute frozen replacement D1b GTEx-to-OSDR organ-transfer audit.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set exact deployed commit}"
OUTPUT_DIR="${OUTPUT_DIR:?set new persistent output directory}"
PROTOCOL="${PROTOCOL:-artifacts/final_evaluation/cross_species_organ_transfer/protocol.json}"
EXPECTED_PROTOCOL_SHA256="${EXPECTED_PROTOCOL_SHA256:?set frozen protocol SHA256}"
GTEX_SOURCE="${GTEX_SOURCE:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_529c0c3}"
GTEX_CACHE_ROOT="${GTEX_CACHE_ROOT:-/media/volume/moe-reboot/results/stage2b_diagnostics_20d000e}"
OSDR_COHORT="${OSDR_COHORT:-/media/volume/moe-reboot/results/stage1_osdr_downstream_5884756/osdr_cohort}"
OSDR_FEATURES="${OSDR_FEATURES:-/media/volume/moe-reboot/results/final_organ_embedding_3f681fd/features}"

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || exit 2
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || exit 2
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || exit 2
[[ ! -e "$OUTPUT_DIR" ]] || exit 2

extra=()
if [[ "${SMOKE:-0}" == "1" ]]; then extra+=(--smoke); fi

"$PYTHON_BIN" -m evaluation.audit_cross_species_organ_transfer \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --gtex-expression "$GTEX_SOURCE/expression/expression.parquet" \
  --gtex-manifest "$GTEX_SOURCE/manifest/gtex_training_manifest.parquet" \
  --gtex-cache "17=$GTEX_CACHE_ROOT/seed17/canonical_cache.npz" \
  --gtex-cache "42=$GTEX_CACHE_ROOT/seed42/canonical_cache.npz" \
  --gtex-cache "101=$GTEX_CACHE_ROOT/seed101_secondary/canonical_cache.npz" \
  --osdr-cohort-root "$OSDR_COHORT" \
  --osdr-feature-root "$OSDR_FEATURES" \
  --output-dir "$OUTPUT_DIR" \
  "${extra[@]}"

(cd "$OUTPUT_DIR" && sha256sum -c IMMUTABLE_SHA256SUMS)
