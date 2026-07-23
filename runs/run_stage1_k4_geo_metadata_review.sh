#!/usr/bin/env bash
# Fetch pinned GEO series-level metadata for the top manual curation candidates.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the deployed 40-character Git commit}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set a new persistent GEO-review result root}"
SOURCE_ROOT="${SOURCE_ROOT:-/media/volume/moe-reboot/results/stage1_k4_external_curation_f307108}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_k4_external_scout/geo_review_protocol.json}"
EXPECTED_PROTOCOL_SHA256=49881dd7ba65396bcb2929a3765f3eaef9692b87445bdf79e2f9444b76892a03
EXPECTED_WORKBOOK_SHA256=965b4a2f40f28d94a1de7317fbaa4c97ae4014426195b287c125e92dc5c7b5e0

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
EXPECTED_ROOT="/media/volume/moe-reboot/results/stage1_k4_geo_review_${CODE_COMMIT:0:7}"
[[ "$EXPERIMENT_ROOT" == "$EXPECTED_ROOT" ]] || {
  echo "ERROR: EXPERIMENT_ROOT must equal $EXPECTED_ROOT" >&2
  exit 1
}
[[ ! -e "$EXPERIMENT_ROOT" ]] || {
  echo "ERROR: GEO-review result root already exists" >&2
  exit 1
}
for marker in CURATION_WORKBOOK_COMPLETE METADATA_CURATION_COMPLETE; do
  [[ -f "$SOURCE_ROOT/$marker" ]] || {
    echo "ERROR: source curation is incomplete: $marker" >&2
    exit 1
  }
done
(
  cd "$SOURCE_ROOT"
  sha256sum -c FULL_SHA256SUMS >/dev/null
)
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || {
  echo "ERROR: GEO-review protocol hash mismatch" >&2
  exit 1
}
WORKBOOK="$SOURCE_ROOT/curation/study_curation_workbook.csv"
[[ "$(sha256sum "$WORKBOOK" | awk '{print $1}')" == "$EXPECTED_WORKBOOK_SHA256" ]] || {
  echo "ERROR: source curation workbook hash mismatch" >&2
  exit 1
}

mkdir -p "$EXPERIMENT_ROOT"
[[ "$(findmnt -n -o TARGET --target "$EXPERIMENT_ROOT")" == "/media/volume/moe-reboot" ]] || {
  echo "ERROR: result root is not on persistent storage" >&2
  exit 1
}
STATUS="$EXPERIMENT_ROOT/GEO_REVIEW_STATUS"
printf 'RUNNING phase=fetch_series_metadata %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/fetch_stage1_k4_geo_metadata.py \
  --workbook "$WORKBOOK" \
  --expected-workbook-sha256 "$EXPECTED_WORKBOOK_SHA256" \
  --code-commit "$CODE_COMMIT" \
  --per-organ 20 \
  --request-delay-seconds 0.4 \
  --output-dir "$EXPERIMENT_ROOT/geo_review" \
  > "$EXPERIMENT_ROOT/geo_review.log" 2>&1
touch "$EXPERIMENT_ROOT/GEO_METADATA_FETCH_COMPLETE"

printf 'RUNNING phase=checksum %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
(
  cd "$EXPERIMENT_ROOT"
  find . -type f \
    ! -name FULL_SHA256SUMS \
    ! -name FULL_SHA256SUMS.tmp \
    ! -name GEO_REVIEW_STATUS \
    ! -name GEO_METADATA_REVIEW_COMPLETE \
    -print0 \
    | sort -z \
    | xargs -0 sha256sum > FULL_SHA256SUMS.tmp
  mv FULL_SHA256SUMS.tmp FULL_SHA256SUMS
  sha256sum -c FULL_SHA256SUMS >/dev/null
)
printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
touch "$EXPERIMENT_ROOT/READY_FOR_MANUAL_GEO_REVIEW"
touch "$EXPERIMENT_ROOT/GEO_METADATA_REVIEW_COMPLETE"
