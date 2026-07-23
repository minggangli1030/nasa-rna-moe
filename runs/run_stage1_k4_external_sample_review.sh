#!/usr/bin/env bash
# Resolve the provisional external-study shortlist to an exact metadata-only sample sheet.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the deployed 40-character Git commit}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set a new persistent sample-review result root}"
CURATION_ROOT="${CURATION_ROOT:-/media/volume/moe-reboot/results/stage1_k4_external_curation_f307108}"
GEO_REVIEW_ROOT="${GEO_REVIEW_ROOT:-/media/volume/moe-reboot/results/stage1_k4_geo_review_a89e2e9}"
SHORTLIST="${SHORTLIST:-artifacts/stage1_k4_external_scout/sample_review_shortlist.json}"
EXPECTED_TRIAGE_SHA256=b2645444af6ceb65df5d4b927057934ee9c4c37c3ab6912a978cf1a0568d7085
EXPECTED_GEO_REVIEW_SHA256=19373eafa0e5d1fdf1127033a669c79232616adbe1d28fd26b6bd01c274cfc3b
EXPECTED_SHORTLIST_SHA256=e7569661edbccc7d0ad075a184851b969c019b12067c19a1458012d7aa1de3f8

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
EXPECTED_ROOT="/media/volume/moe-reboot/results/stage1_k4_external_sample_review_${CODE_COMMIT:0:7}"
[[ "$EXPERIMENT_ROOT" == "$EXPECTED_ROOT" ]] || {
  echo "ERROR: EXPERIMENT_ROOT must equal $EXPECTED_ROOT" >&2
  exit 1
}
[[ ! -e "$EXPERIMENT_ROOT" ]] || {
  echo "ERROR: sample-review result root already exists" >&2
  exit 1
}
for specification in \
  "$CURATION_ROOT:CURATION_WORKBOOK_COMPLETE:METADATA_CURATION_COMPLETE" \
  "$GEO_REVIEW_ROOT:GEO_METADATA_FETCH_COMPLETE:GEO_METADATA_REVIEW_COMPLETE"; do
  IFS=: read -r source_root marker_one marker_two <<< "$specification"
  for marker in "$marker_one" "$marker_two"; do
    [[ -f "$source_root/$marker" ]] || {
      echo "ERROR: source result is incomplete: $source_root/$marker" >&2
      exit 1
    }
  done
  (
    cd "$source_root"
    sha256sum -c FULL_SHA256SUMS >/dev/null
  )
done
[[ "$(sha256sum "$SHORTLIST" | awk '{print $1}')" == "$EXPECTED_SHORTLIST_SHA256" ]] || {
  echo "ERROR: provisional shortlist hash mismatch" >&2
  exit 1
}
TRIAGE="$CURATION_ROOT/curation/sample_triage.parquet"
GEO_REVIEW="$GEO_REVIEW_ROOT/geo_review/selected_study_review.csv"
[[ "$(sha256sum "$TRIAGE" | awk '{print $1}')" == "$EXPECTED_TRIAGE_SHA256" ]] || {
  echo "ERROR: source sample-triage hash mismatch" >&2
  exit 1
}
[[ "$(sha256sum "$GEO_REVIEW" | awk '{print $1}')" == "$EXPECTED_GEO_REVIEW_SHA256" ]] || {
  echo "ERROR: source GEO study-review hash mismatch" >&2
  exit 1
}

mkdir -p "$EXPERIMENT_ROOT"
[[ "$(findmnt -n -o TARGET --target "$EXPERIMENT_ROOT")" == "/media/volume/moe-reboot" ]] || {
  echo "ERROR: result root is not on persistent storage" >&2
  exit 1
}
STATUS="$EXPERIMENT_ROOT/SAMPLE_REVIEW_STATUS"
printf 'RUNNING phase=resolve_provisional_selectors %s\n' \
  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/build_stage1_k4_external_sample_review.py \
  --sample-triage "$TRIAGE" \
  --expected-triage-sha256 "$EXPECTED_TRIAGE_SHA256" \
  --geo-study-review "$GEO_REVIEW" \
  --expected-geo-review-sha256 "$EXPECTED_GEO_REVIEW_SHA256" \
  --shortlist "$SHORTLIST" \
  --expected-shortlist-sha256 "$EXPECTED_SHORTLIST_SHA256" \
  --code-commit "$CODE_COMMIT" \
  --output-dir "$EXPERIMENT_ROOT/sample_review" \
  > "$EXPERIMENT_ROOT/sample_review.log" 2>&1
touch "$EXPERIMENT_ROOT/PROVISIONAL_SAMPLE_SHEET_COMPLETE"

printf 'RUNNING phase=checksum %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
(
  cd "$EXPERIMENT_ROOT"
  find . -type f \
    ! -name FULL_SHA256SUMS \
    ! -name FULL_SHA256SUMS.tmp \
    ! -name SAMPLE_REVIEW_STATUS \
    ! -name METADATA_SAMPLE_REVIEW_COMPLETE \
    -print0 \
    | sort -z \
    | xargs -0 sha256sum > FULL_SHA256SUMS.tmp
  mv FULL_SHA256SUMS.tmp FULL_SHA256SUMS
  sha256sum -c FULL_SHA256SUMS >/dev/null
)
printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
touch "$EXPERIMENT_ROOT/READY_FOR_MANUAL_SAMPLE_REVIEW"
touch "$EXPERIMENT_ROOT/METADATA_SAMPLE_REVIEW_COMPLETE"
