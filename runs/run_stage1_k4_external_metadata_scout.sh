#!/usr/bin/env bash
# Metadata-only feasibility scout for a future untouched external confirmation set.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-/home/exouser/moe-env/bin/python3}"
CODE_COMMIT="${CODE_COMMIT:?set CODE_COMMIT to the deployed 40-character Git commit}"
EXPERIMENT_ROOT="${EXPERIMENT_ROOT:?set a new persistent metadata-scout result root}"
PROTOCOL="${PROTOCOL:-artifacts/stage1_k4_external_scout/protocol.json}"
ONTOLOGY="${ONTOLOGY:-data/ontology/uberon_organ_map.json}"
HISTORICAL_H5="${HISTORICAL_H5:-/media/volume/moe-reboot/archs4/human_matrix_v11.h5}"
CURRENT_URL="https://s3.k8s.maayanlab.cloud/archs4/files/human_gene_v2.latest.h5"
EXPECTED_PROTOCOL_SHA256=1ab183ba9d31851a2f605d51d29eb9a282b7581b63a56e6eacdd9693276dc1c4
EXPECTED_HISTORICAL_ACCESSION_SHA256=784035aa00284f2a8c0c500a391f88d9c6986621c22dd7f622a06284d731eba0
EXPECTED_HISTORICAL_MAPPING_SHA256=ffce20e908770672571d3e75755cb00643c330da8899424255b6a245e9936523

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
EXPECTED_ROOT="/media/volume/moe-reboot/results/stage1_k4_external_scout_${CODE_COMMIT:0:7}"
[[ "$EXPERIMENT_ROOT" == "$EXPECTED_ROOT" ]] || {
  echo "ERROR: EXPERIMENT_ROOT must equal $EXPECTED_ROOT" >&2
  exit 1
}
[[ ! -e "$EXPERIMENT_ROOT" ]] || {
  echo "ERROR: metadata-scout result root already exists" >&2
  exit 1
}
mkdir -p "$EXPERIMENT_ROOT"
[[ "$(findmnt -n -o TARGET --target "$EXPERIMENT_ROOT")" == "/media/volume/moe-reboot" ]] || {
  echo "ERROR: result root is not on persistent storage" >&2
  exit 1
}
[[ "$(df -Pk "$EXPERIMENT_ROOT" | awk 'NR==2 {print $4}')" -ge 10485760 ]] || {
  echo "ERROR: metadata scout requires at least 10 GiB free" >&2
  exit 1
}
[[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" == "$EXPECTED_PROTOCOL_SHA256" ]] || {
  echo "ERROR: metadata-scout protocol hash mismatch" >&2
  exit 1
}
for path in "$PROTOCOL" "$ONTOLOGY" "$HISTORICAL_H5" \
  preprocessing/export_archs4_sample_metadata.py \
  preprocessing/export_archs4_remote_sample_metadata.py \
  evaluation/build_stage1_k4_external_scout.py; do
  [[ -s "$path" ]] || {
    echo "ERROR: required metadata-scout input is missing: $path" >&2
    exit 1
  }
done

STATUS="$EXPERIMENT_ROOT/SCOUT_STATUS"
printf 'RUNNING phase=historical_metadata %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" preprocessing/export_archs4_sample_metadata.py \
  --human-h5 "$HISTORICAL_H5" \
  --output "$EXPERIMENT_ROOT/historical_v11_metadata.parquet" \
  > "$EXPERIMENT_ROOT/historical_export.log" 2>&1

printf 'RUNNING phase=current_metadata %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" preprocessing/export_archs4_remote_sample_metadata.py \
  --human-h5-url "$CURRENT_URL" \
  --expected-content-length 62257385524 \
  --expected-etag '"86ec41d970158f18d065bb9f89248ce5-928"' \
  --expected-last-modified 'Tue, 07 Jul 2026 08:43:19 GMT' \
  --output "$EXPERIMENT_ROOT/current_metadata.parquet" \
  --report "$EXPERIMENT_ROOT/current_metadata_report.json" \
  > "$EXPERIMENT_ROOT/current_export.log" 2>&1
touch "$EXPERIMENT_ROOT/CURRENT_METADATA_COMPLETE"

printf 'RUNNING phase=filter_and_label %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
"$PYTHON_BIN" evaluation/build_stage1_k4_external_scout.py \
  --current-metadata "$EXPERIMENT_ROOT/current_metadata.parquet" \
  --current-report "$EXPERIMENT_ROOT/current_metadata_report.json" \
  --historical-metadata "$EXPERIMENT_ROOT/historical_v11_metadata.parquet" \
  --expected-historical-accession-sha256 "$EXPECTED_HISTORICAL_ACCESSION_SHA256" \
  --expected-historical-series-mapping-sha256 "$EXPECTED_HISTORICAL_MAPPING_SHA256" \
  --ontology "$ONTOLOGY" \
  --protocol "$PROTOCOL" \
  --code-commit "$CODE_COMMIT" \
  --output-dir "$EXPERIMENT_ROOT/scout" \
  > "$EXPERIMENT_ROOT/scout.log" 2>&1
touch "$EXPERIMENT_ROOT/SCOUT_RESULTS_COMPLETE"

printf 'RUNNING phase=checksum %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
(
  cd "$EXPERIMENT_ROOT"
  find . -type f \
    ! -name FULL_SHA256SUMS \
    ! -name FULL_SHA256SUMS.tmp \
    ! -name SCOUT_STATUS \
    ! -name METADATA_SCOUT_COMPLETE \
    -print0 \
    | sort -z \
    | xargs -0 sha256sum > FULL_SHA256SUMS.tmp
  mv FULL_SHA256SUMS.tmp FULL_SHA256SUMS
  sha256sum -c FULL_SHA256SUMS >/dev/null
)
printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
touch "$EXPERIMENT_ROOT/READY_FOR_REVIEW"
touch "$EXPERIMENT_ROOT/METADATA_SCOUT_COMPLETE"
