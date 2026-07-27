#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/minggangli/Projects/nasa-rna-moe"
EXPECTED_H5_SIZE="62257385524"
PARTIAL="$ROOT/data/archs4/current/human_gene_v2.latest.h5.partial"
H5="$ROOT/data/archs4/current/human_gene_v2.latest.h5"
STATE_DIR="$ROOT/artifacts/stage1_gtex_to_archs4"
STATUS="$STATE_DIR/continuation_status.txt"
PROTOCOL="$STATE_DIR/lockbox_protocol.json"
RUN_DIR="$STATE_DIR/lockbox_run_73f9bd1"
IMPLEMENTATION_COMMIT="73f9bd1d6fff097811f879766e9a68a05aebe850"
REMOTE_WORKTREE="/media/volume/moe-reboot/worktrees/gtex_archs4_lockbox_75b37af"
REMOTE_RUN="/media/volume/moe-reboot/results/lockbox_run_73f9bd1"

mkdir -p "$STATE_DIR"

fail() {
  printf 'FAILED %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
}
trap fail ERR

printf 'WAITING_FOR_ARCHS4_DOWNLOAD %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
while true; do
  if [[ -f "$PARTIAL" ]]; then
    size="$(stat -f %z "$PARTIAL")"
    if [[ "$size" == "$EXPECTED_H5_SIZE" ]]; then
      break
    fi
    if (( size > EXPECTED_H5_SIZE )); then
      printf 'FAILED_OVERSIZE %s %s\n' "$size" "$(date -u +%FT%TZ)" > "$STATUS"
      exit 1
    fi
  fi
  if ! /bin/kill -0 45284 2>/dev/null; then
    printf 'FAILED_DOWNLOAD_STOPPED %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
    exit 1
  fi
  sleep 60
done

mv "$PARTIAL" "$H5"
printf 'HASHING_ARCHS4_SOURCE %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
H5_SHA256="$(shasum -a 256 "$H5" | awk '{print $1}')"

printf 'FREEZING_PROTOCOL %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
cd "$ROOT"
python3 evaluation/freeze_gtex_to_archs4_protocol.py \
  --candidate-ledger artifacts/stage1_gtex_to_archs4/candidate_ledger.json \
  --random-mappings artifacts/stage1_gtex_to_archs4/random_control_mappings.json \
  --sample-review backups/stage1_gtex_to_archs4_k8_sample_review_419d011/provisional_sample_review.csv \
  --study-review backups/stage1_gtex_to_archs4_k8_sample_review_419d011/provisional_study_review.csv \
  --sample-review-report backups/stage1_gtex_to_archs4_k8_sample_review_419d011/sample_review_report.json \
  --donor-audit-samples backups/stage1_gtex_to_archs4_k8_donor_audit_419d011/audited_sample_donor_keys.csv \
  --donor-audit-studies backups/stage1_gtex_to_archs4_k8_donor_audit_419d011/study_donor_audit.csv \
  --donor-audit-report backups/stage1_gtex_to_archs4_k8_donor_audit_419d011/donor_power_audit_report.json \
  --human-h5 "$H5" \
  --human-h5-sha256 "$H5_SHA256" \
  --code-commit "$IMPLEMENTATION_COMMIT" \
  --output "$PROTOCOL" > "$STATE_DIR/protocol_freeze_stdout.json"
PROTOCOL_SHA256="$(shasum -a 256 "$PROTOCOL" | awk '{print $1}')"

printf 'EXTRACTING_LOCKBOX %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
python3 runs/launch_gtex_to_archs4_lockbox.py \
  --phase extract \
  --protocol "$PROTOCOL" \
  --expected-protocol-sha256 "$PROTOCOL_SHA256" \
  --candidate-ledger artifacts/stage1_gtex_to_archs4/candidate_ledger.json \
  --random-mappings artifacts/stage1_gtex_to_archs4/random_control_mappings.json \
  --sample-review backups/stage1_gtex_to_archs4_k8_sample_review_419d011/provisional_sample_review.csv \
  --study-review backups/stage1_gtex_to_archs4_k8_sample_review_419d011/provisional_study_review.csv \
  --sample-review-report backups/stage1_gtex_to_archs4_k8_sample_review_419d011/sample_review_report.json \
  --donor-audit-samples backups/stage1_gtex_to_archs4_k8_donor_audit_419d011/audited_sample_donor_keys.csv \
  --donor-audit-studies backups/stage1_gtex_to_archs4_k8_donor_audit_419d011/study_donor_audit.csv \
  --donor-audit-report backups/stage1_gtex_to_archs4_k8_donor_audit_419d011/donor_power_audit_report.json \
  --human-h5 "$H5" \
  --canonical-genes data/ensembl/canonical_genes_shared.txt \
  --human-exon-lengths data/gencode/gencode_v49_gene_exon_lengths.csv \
  --training-root backups/stage1_gtex_to_archs4_training_98e2cba \
  --output-dir "$RUN_DIR" \
  --code-commit "$IMPLEMENTATION_COMMIT" > "$STATE_DIR/extraction_launcher_stdout.json"
cp "$PROTOCOL" "$RUN_DIR/protocol.json"

printf 'TRANSFERRING_HANDOFF %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
scp -r "$RUN_DIR" "moe-reboot:/media/volume/moe-reboot/results/"

printf 'SCORING_ON_GPU %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
ssh -o BatchMode=yes -o ConnectTimeout=10 moe-reboot \
  "cd '$REMOTE_WORKTREE' && /home/exouser/moe-env/bin/python3 runs/launch_gtex_to_archs4_lockbox.py \
  --phase score \
  --protocol '$REMOTE_RUN/protocol.json' \
  --expected-protocol-sha256 '$PROTOCOL_SHA256' \
  --candidate-ledger artifacts/stage1_gtex_to_archs4/candidate_ledger.json \
  --random-mappings artifacts/stage1_gtex_to_archs4/random_control_mappings.json \
  --training-root /media/volume/moe-reboot/results/stage1_gtex_to_archs4_training_98e2cba \
  --output-dir '$REMOTE_RUN' \
  --code-commit '$IMPLEMENTATION_COMMIT' \
  --device auto" > "$STATE_DIR/remote_scoring_stdout.json"

printf 'COMPLETE %s\n' "$(date -u +%FT%TZ)" > "$STATUS"
trap - ERR
