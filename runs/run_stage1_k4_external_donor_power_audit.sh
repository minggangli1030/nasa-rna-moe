#!/usr/bin/env bash
# Build the conservative v3 sample sheet and its metadata-only donor/power audit.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the deployed 40-character Git commit}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set a new persistent donor-audit result root}"
CURATION_ROOT="${CURATION_ROOT:-/media/volume/moe-reboot/results/stage1_k4_external_curation_f307108}"
GEO_REVIEW_ROOT="${GEO_REVIEW_ROOT:-/media/volume/moe-reboot/results/stage1_k4_geo_review_a89e2e9}"
GEO_RESERVE_ROOT="${GEO_RESERVE_ROOT:-/media/volume/moe-reboot/results/stage1_k4_geo_reserve_review_119ed2d}"
SHORTLIST="${SHORTLIST:-artifacts/stage1_k4_external_scout/sample_review_shortlist.json}"
AMENDMENT="${AMENDMENT:-artifacts/stage1_k4_external_scout/sample_review_amendment_v3.json}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_k4_external_scout/donor_power_audit_protocol.json}"

EXPECTED_TRIAGE_SHA256=b2645444af6ceb65df5d4b927057934ee9c4c37c3ab6912a978cf1a0568d7085
EXPECTED_GEO_REVIEW_SHA256=19373eafa0e5d1fdf1127033a669c79232616adbe1d28fd26b6bd01c274cfc3b
EXPECTED_GEO_RESERVE_REVIEW_SHA256=9afb4067935f5602241f0d4355c8a052f72475d655607c981fbbb4ec6702cf84
EXPECTED_SHORTLIST_SHA256=e7569661edbccc7d0ad075a184851b969c019b12067c19a1458012d7aa1de3f8
EXPECTED_AMENDMENT_SHA256=de2d9e63588d777498fc736ef6da30f860fa14859f7c83bbbf44a7d3c441990a
EXPECTED_PROTOCOL_SHA256=d1afa13e634d0a750a5d659c9bd49f96a49aacd17dd3aff264dcff7b116caa14
EXPECTED_SAMPLE_REVIEW_SHA256=ab8a5751abbf680bb34e2e96cc8fe40e93016c06c9ecaaa37e7c273724d39418
EXPECTED_STUDY_REVIEW_SHA256=3b0d5d3c1036d6084f02f47ab7582793782fefaa6ceff89b8e2ddb3ae88b6e41

fail() {
  printf 'FAILED phase=%s %s\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
  exit 1
}

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
EXPECTED_ROOT="/media/volume/moe-reboot/results/stage1_k4_external_donor_power_audit_${CODE_COMMIT:0:7}"
[[ "$EXPERIMENT_ROOT" == "$EXPECTED_ROOT" ]] || {
  echo "ERROR: EXPERIMENT_ROOT must equal $EXPECTED_ROOT" >&2
  exit 1
}
[[ ! -e "$EXPERIMENT_ROOT" ]] || {
  echo "ERROR: donor-audit result root already exists" >&2
  exit 1
}

for specification in \
  "$CURATION_ROOT:CURATION_WORKBOOK_COMPLETE:METADATA_CURATION_COMPLETE" \
  "$GEO_REVIEW_ROOT:GEO_METADATA_FETCH_COMPLETE:GEO_METADATA_REVIEW_COMPLETE" \
  "$GEO_RESERVE_ROOT:GEO_RESERVE_METADATA_FETCH_COMPLETE:GEO_RESERVE_METADATA_REVIEW_COMPLETE"; do
  IFS=: read -r source_root marker_one marker_two <<< "$specification"
  for marker in "$marker_one" "$marker_two"; do
    [[ -f "$source_root/$marker" ]] || {
      echo "ERROR: source result is incomplete: $source_root/$marker" >&2
      exit 1
    }
  done
  (cd "$source_root" && sha256sum -c FULL_SHA256SUMS >/dev/null)
done

for specification in \
  "$SHORTLIST:$EXPECTED_SHORTLIST_SHA256:shortlist" \
  "$AMENDMENT:$EXPECTED_AMENDMENT_SHA256:amendment" \
  "$PROTOCOL:$EXPECTED_PROTOCOL_SHA256:protocol"; do
  IFS=: read -r path expected_hash label <<< "$specification"
  [[ "$(sha256sum "$path" | awk '{print $1}')" == "$expected_hash" ]] || {
    echo "ERROR: $label hash mismatch" >&2
    exit 1
  }
done

TRIAGE="$CURATION_ROOT/curation/sample_triage.parquet"
GEO_REVIEW="$GEO_REVIEW_ROOT/geo_review/selected_study_review.csv"
GEO_RESERVE_REVIEW="$GEO_RESERVE_ROOT/geo_review/selected_study_review.csv"
for specification in \
  "$TRIAGE:$EXPECTED_TRIAGE_SHA256:sample-triage" \
  "$GEO_REVIEW:$EXPECTED_GEO_REVIEW_SHA256:GEO-study-review" \
  "$GEO_RESERVE_REVIEW:$EXPECTED_GEO_RESERVE_REVIEW_SHA256:GEO-reserve-review"; do
  IFS=: read -r path expected_hash label <<< "$specification"
  [[ "$(sha256sum "$path" | awk '{print $1}')" == "$expected_hash" ]] || {
    echo "ERROR: source $label hash mismatch" >&2
    exit 1
  }
done

mkdir -p "$EXPERIMENT_ROOT"
[[ "$(findmnt -n -o TARGET --target "$EXPERIMENT_ROOT")" == "/media/volume/moe-reboot" ]] || {
  echo "ERROR: result root is not on persistent storage" >&2
  exit 1
}
STATUS="$EXPERIMENT_ROOT/DONOR_POWER_AUDIT_STATUS"
trap 'fail unexpected_exit' ERR

printf 'RUNNING phase=build_conservative_sample_review %s\n' \
  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/build_stage1_k4_external_sample_review.py \
  --sample-triage "$TRIAGE" \
  --expected-triage-sha256 "$EXPECTED_TRIAGE_SHA256" \
  --geo-study-review "$GEO_REVIEW" \
  --expected-geo-review-sha256 "$EXPECTED_GEO_REVIEW_SHA256" \
  --supplemental-geo-study-review "$GEO_RESERVE_REVIEW" \
  --expected-supplemental-geo-review-sha256 "$EXPECTED_GEO_RESERVE_REVIEW_SHA256" \
  --shortlist "$SHORTLIST" \
  --expected-shortlist-sha256 "$EXPECTED_SHORTLIST_SHA256" \
  --shortlist-amendment "$AMENDMENT" \
  --expected-shortlist-amendment-sha256 "$EXPECTED_AMENDMENT_SHA256" \
  --code-commit "$CODE_COMMIT" \
  --output-dir "$EXPERIMENT_ROOT/sample_review_v3" \
  > "$EXPERIMENT_ROOT/sample_review_v3.log" 2>&1

SAMPLES="$EXPERIMENT_ROOT/sample_review_v3/provisional_sample_review.csv"
STUDIES="$EXPERIMENT_ROOT/sample_review_v3/provisional_study_review.csv"
SOURCE_REPORT="$EXPERIMENT_ROOT/sample_review_v3/sample_review_report.json"
[[ "$(sha256sum "$SAMPLES" | awk '{print $1}')" == "$EXPECTED_SAMPLE_REVIEW_SHA256" ]] \
  || fail sample_review_hash_validation
[[ "$(sha256sum "$STUDIES" | awk '{print $1}')" == "$EXPECTED_STUDY_REVIEW_SHA256" ]] \
  || fail study_review_hash_validation
touch "$EXPERIMENT_ROOT/CONSERVATIVE_SAMPLE_REVIEW_COMPLETE"

printf 'RUNNING phase=donor_power_audit %s\n' \
  "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/build_stage1_k4_external_donor_power_audit.py \
  --samples "$SAMPLES" \
  --studies "$STUDIES" \
  --source-report "$SOURCE_REPORT" \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$EXPECTED_PROTOCOL_SHA256" \
  --code-commit "$CODE_COMMIT" \
  --output-dir "$EXPERIMENT_ROOT/donor_power_audit" \
  > "$EXPERIMENT_ROOT/donor_power_audit.log" 2>&1

"$PYTHON_BIN" - "$EXPERIMENT_ROOT/donor_power_audit/donor_power_audit_report.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
if report.get("ready_for_protocol_drafting") is not True:
    raise SystemExit("donor audit did not reach protocol-drafting readiness")
for forbidden in (
    "ready_for_lockbox_freeze",
    "ready_for_expression_access",
    "expression_values_read",
):
    if report.get(forbidden) is not False:
        raise SystemExit(f"firewall violation: {forbidden}")
PY
touch "$EXPERIMENT_ROOT/DONOR_POWER_AUDIT_COMPLETE"
touch "$EXPERIMENT_ROOT/READY_FOR_PROTOCOL_DRAFTING"

printf 'RUNNING phase=checksum %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
(
  cd "$EXPERIMENT_ROOT"
  find . -type f \
    ! -name FULL_SHA256SUMS \
    ! -name FULL_SHA256SUMS.tmp \
    ! -name DONOR_POWER_AUDIT_STATUS \
    ! -name METADATA_DONOR_AUDIT_COMPLETE \
    -print0 \
    | sort -z \
    | xargs -0 sha256sum > FULL_SHA256SUMS.tmp
  mv FULL_SHA256SUMS.tmp FULL_SHA256SUMS
  sha256sum -c FULL_SHA256SUMS >/dev/null
)
trap - ERR
printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
touch "$EXPERIMENT_ROOT/METADATA_DONOR_AUDIT_COMPLETE"
