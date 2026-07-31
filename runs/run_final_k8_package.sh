#!/usr/bin/env bash
# Build the immutable no-refit package for the validated three-seed K8 family.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the exact deployed commit}"
OUTPUT_ROOT="${OUTPUT_ROOT:?set OUTPUT_ROOT to a new persistent result root}"
TRAINING_ROOT="${TRAINING_ROOT:-/media/volume/moe-reboot/results/stage1_gtex_to_archs4_training_98e2cba}"
PROTOCOL="${PROTOCOL:-artifacts/final_model/final_k8_package_protocol.json}"
LEDGER="${LEDGER:-artifacts/stage1_gtex_to_archs4/candidate_ledger.json}"
EXPECTED_PROTOCOL_SHA256=7243f5345ae6fc2b522905d139ec82036f7854c1dd167e33f64814d8ca495500

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid CODE_COMMIT" >&2; exit 1; }
[[ "$(git rev-parse HEAD)" == "$CODE_COMMIT" ]] || { echo "commit mismatch" >&2; exit 1; }
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo "dirty tracked tree" >&2; exit 1; }
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || {
  echo "protocol hash mismatch" >&2; exit 1;
}
[[ ! -e "$OUTPUT_ROOT" ]] || { echo "output root exists" >&2; exit 1; }
mkdir -p "$(dirname "$OUTPUT_ROOT")"

"$PYTHON_BIN" -m py_compile evaluation/freeze_final_k8_package.py
"$PYTHON_BIN" evaluation/freeze_final_k8_package.py \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --candidate-ledger "$LEDGER" \
  --training-root "$TRAINING_ROOT" \
  --output-dir "$OUTPUT_ROOT" \
  --code-commit "$CODE_COMMIT" \
  > "${OUTPUT_ROOT}.log" 2>&1

(cd "$OUTPUT_ROOT" && sha256sum -c FULL_SHA256SUMS)
"$PYTHON_BIN" -c \
  'import json,pathlib,sys; r=json.load(open(pathlib.Path(sys.argv[1])/"package_manifest.json")); assert r["status"]=="complete" and r["seeds"]==[17,42,101]; assert r["weights_updated"] is False and r["training_performed"] is False and r["efficacy_scoring_performed"] is False; assert r["archs4_expression_accessed"] is False and r["osdr_accessed"] is False and r["best_seed_selection"] is False; assert all(v["pooled"]["all_tensors_finite"] and v["organ_k8"]["all_tensors_finite"] for v in r["checkpoint_health"].values())' \
  "$OUTPUT_ROOT"
