#!/usr/bin/env bash
# Build a metadata-only connected-study workbook for manual external-cohort curation.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the deployed 40-character Git commit}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set a new persistent curation result root}"
SOURCE_ROOT="${SOURCE_ROOT:-/media/volume/moe-reboot/results/stage1_k4_external_scout_182207b}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_k4_external_scout/protocol.json}"
ONTOLOGY="${ONTOLOGY:-data/ontology/uberon_organ_map.json}"
EXPECTED_PROTOCOL_SHA256=904be7aa9a4e36ab323cef9680bbdcd3cbdf9b3e241d8c32db7831cb25e83187
EXPECTED_CANDIDATE_SHA256=5f8977f25b9c6b8c1bc3d565ac0b57562df6c36d06eb46e098b963074cc6ee16

[[ "$CODE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: CODE_COMMIT must be a full hexadecimal commit" >&2
  exit 1
}
[[ "$(git rev-parse HEAD 2>/dev/null)" == "$CODE_COMMIT" ]] || {
  echo "ERROR: deployed HEAD differs from CODE_COMMIT" >&2
  exit 1
}
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || {
  echo "ERROR: deployed tracked tree is dirty" >&2
  exit 1
}
EXPECTED_ROOT="/media/volume/moe-reboot/results/stage1_k4_external_curation_${CODE_COMMIT:0:7}"
[[ "$EXPERIMENT_ROOT" == "$EXPECTED_ROOT" ]] || {
  echo "ERROR: EXPERIMENT_ROOT must equal $EXPECTED_ROOT" >&2
  exit 1
}
[[ ! -e "$EXPERIMENT_ROOT" ]] || {
  echo "ERROR: curation result root already exists" >&2
  exit 1
}
for marker in CURRENT_METADATA_COMPLETE SCOUT_RESULTS_COMPLETE METADATA_SCOUT_COMPLETE; do
  [[ -f "$SOURCE_ROOT/$marker" ]] || {
    echo "ERROR: source scout is incomplete: $marker" >&2
    exit 1
  }
done
(
  cd "$SOURCE_ROOT"
  sha256sum -c FULL_SHA256SUMS >/dev/null
)
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || {
  echo "ERROR: external-curation protocol hash mismatch" >&2
  exit 1
}
[[ "$(sha256sum "$SOURCE_ROOT/scout/candidate_metadata.parquet" | awk '{print $1}')" == "$EXPECTED_CANDIDATE_SHA256" ]] || {
  echo "ERROR: source candidate metadata hash mismatch" >&2
  exit 1
}

mkdir -p "$EXPERIMENT_ROOT"
[[ "$(findmnt -n -o TARGET --target "$EXPERIMENT_ROOT")" == "/media/volume/moe-reboot" ]] || {
  echo "ERROR: result root is not on persistent storage" >&2
  exit 1
}
STATUS="$EXPERIMENT_ROOT/CURATION_STATUS"
printf 'RUNNING phase=build_workbook %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/build_stage1_k4_external_curation.py \
  --candidate-metadata "$SOURCE_ROOT/scout/candidate_metadata.parquet" \
  --scout-report "$SOURCE_ROOT/scout/scout_report.json" \
  --expected-candidate-sha256 "$EXPECTED_CANDIDATE_SHA256" \
  --ontology "$ONTOLOGY" \
  --code-commit "$CODE_COMMIT" \
  --output-dir "$EXPERIMENT_ROOT/curation" \
  > "$EXPERIMENT_ROOT/curation.log" 2>&1
touch "$EXPERIMENT_ROOT/CURATION_WORKBOOK_COMPLETE"

printf 'RUNNING phase=checksum %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
(
  cd "$EXPERIMENT_ROOT"
  find . -type f \
    ! -name FULL_SHA256SUMS \
    ! -name FULL_SHA256SUMS.tmp \
    ! -name CURATION_STATUS \
    ! -name METADATA_CURATION_COMPLETE \
    -print0 \
    | sort -z \
    | xargs -0 sha256sum > FULL_SHA256SUMS.tmp
  mv FULL_SHA256SUMS.tmp FULL_SHA256SUMS
  sha256sum -c FULL_SHA256SUMS >/dev/null
)
printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
touch "$EXPERIMENT_ROOT/READY_FOR_MANUAL_STUDY_REVIEW"
touch "$EXPERIMENT_ROOT/METADATA_CURATION_COMPLETE"
