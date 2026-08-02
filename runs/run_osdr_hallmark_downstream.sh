#!/usr/bin/env bash
# Execute frozen D2 Hallmark-50 downstream-feature evaluation.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set exact deployed commit}"
OUTPUT_DIR="${OUTPUT_DIR:?set a new persistent output directory}"
PROTOCOL="${PROTOCOL:-artifacts/final_evaluation/hallmark_downstream/protocol.json}"
EXPECTED_PROTOCOL_SHA256="${EXPECTED_PROTOCOL_SHA256:?set frozen D2 protocol SHA256}"
COHORT_ROOT="${COHORT_ROOT:-/media/volume/moe-reboot/results/stage1_osdr_downstream_5884756/osdr_cohort}"
ROUTER="${ROUTER:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_training_98e2cba/router/gtex_k8_target_hidden_router.npz}"
HALLMARK_GMT="${HALLMARK_GMT:-data/msigdb/h.all.v2026.1.Hs.symbols.gmt}"

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || exit 2
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || exit 2
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || exit 2
[[ ! -e "$OUTPUT_DIR" ]] || exit 2

extra=()
if [[ "${SMOKE:-0}" == "1" ]]; then
  extra+=(--smoke)
fi

"$PYTHON_BIN" -m evaluation.evaluate_osdr_hallmark_downstream \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --cohort-root "$COHORT_ROOT" \
  --hallmark-gmt "$HALLMARK_GMT" \
  --router "$ROUTER" \
  --output-dir "$OUTPUT_DIR" \
  "${extra[@]}"

(cd "$OUTPUT_DIR" && sha256sum -c IMMUTABLE_SHA256SUMS)
