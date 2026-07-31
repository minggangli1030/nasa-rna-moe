#!/usr/bin/env bash
# Extract and evaluate the frozen downstream-facing organ-MoE embedding contract.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the exact deployed commit}"
OUTPUT_ROOT="${OUTPUT_ROOT:?set OUTPUT_ROOT to a new persistent result root}"
TRAINING_ROOT="${TRAINING_ROOT:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_training_98e2cba}"
COHORT_ROOT="${COHORT_ROOT:-/media/volume/moe-reboot/results/stage1_osdr_downstream_5884756/osdr_cohort}"
PROTOCOL="${PROTOCOL:-artifacts/final_evaluation/final_organ_embedding_development/protocol.json}"
LEDGER="${LEDGER:-artifacts/stage1_gtex_to_archs4/candidate_ledger.json}"
EXPECTED_PROTOCOL_SHA256=3730da5059691065855c88f25cb79636e07887b7ed7f127e467256e9b848910a

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid CODE_COMMIT" >&2; exit 1; }
[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || { echo "commit mismatch" >&2; exit 1; }
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo "dirty tracked tree" >&2; exit 1; }
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || {
  echo "protocol hash mismatch" >&2; exit 1;
}
[[ ! -e "$OUTPUT_ROOT" ]] || { echo "output root exists" >&2; exit 1; }
mkdir -p "$OUTPUT_ROOT"
STATUS="$OUTPUT_ROOT/EMBEDDING_STATUS"
trap 'rc=$?; if [[ $rc -ne 0 ]]; then printf "FAILED exit=%s %s\n" "$rc" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"; fi' EXIT
printf '%s\n' "$CODE_COMMIT" > "$OUTPUT_ROOT/CODE_COMMIT"
printf '%s\n' "$EXPECTED_PROTOCOL_SHA256" > "$OUTPUT_ROOT/PROTOCOL_SHA256"

"$PYTHON_BIN" -m py_compile \
  core/final_organ_embedding.py \
  evaluation/cache_final_organ_embedding_development.py \
  evaluation/evaluate_stage1_osdr_downstream.py

printf 'RUNNING phase=features %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
"$PYTHON_BIN" evaluation/cache_final_organ_embedding_development.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --candidate-ledger "$LEDGER" \
  --training-root "$TRAINING_ROOT" \
  --cohort-root "$COHORT_ROOT" \
  --output-dir "$OUTPUT_ROOT/features" \
  --batch-size 2 \
  --device cuda:0 \
  > "$OUTPUT_ROOT/features.log" 2>&1

printf 'RUNNING phase=evaluation_smoke %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
"$PYTHON_BIN" evaluation/evaluate_stage1_osdr_downstream.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --cohort-root "$COHORT_ROOT" \
  --feature-root "$OUTPUT_ROOT/features" \
  --output-dir "$OUTPUT_ROOT/evaluation_smoke" \
  --outer-folds 3 \
  --inner-folds 2 \
  --smoke \
  > "$OUTPUT_ROOT/evaluation_smoke.log" 2>&1

printf 'RUNNING phase=evaluation_full %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
"$PYTHON_BIN" evaluation/evaluate_stage1_osdr_downstream.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --cohort-root "$COHORT_ROOT" \
  --feature-root "$OUTPUT_ROOT/features" \
  --output-dir "$OUTPUT_ROOT/evaluation_full" \
  --outer-folds 5 \
  --inner-folds 3 \
  > "$OUTPUT_ROOT/evaluation_full.log" 2>&1

(
  cd "$OUTPUT_ROOT"
  find . -type f ! -name IMMUTABLE_SHA256SUMS ! -name EMBEDDING_STATUS -print0 \
    | sort -z | xargs -0 sha256sum > IMMUTABLE_SHA256SUMS
)
printf 'COMPLETE %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$STATUS"
