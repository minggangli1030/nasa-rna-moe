#!/bin/bash
# Append a validated timestamped result addendum to report.md.
set -u

cd "$(dirname "$0")/.."
BACKUP_DIR=${BACKUP_DIR:-$(pwd)/backups/20k_v3_final}
POLL_SECONDS=${POLL_SECONDS:-120}
LOG="$BACKUP_DIR/report_watcher.log"
SUCCESS="$BACKUP_DIR/REPORT_READY"

mkdir -p "$BACKUP_DIR"
touch "$LOG"

log() {
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$LOG"
}

[ -f "$SUCCESS" ] && exit 0
log "Report watcher started; waiting for validated corrected evaluation."
until [ -f "$BACKUP_DIR/EVALUATION_COMPLETE_AND_VALIDATED" ]; do
    sleep "$POLL_SECONDS"
done

if ! python3 evaluation/draft_interspecies_report.py \
    --results-root results \
    --report report.md >> "$LOG" 2>&1; then
    log "ERROR report generation failed; Git backup remains blocked"
    exit 1
fi

test -s report.md || {
    log "ERROR report.md is empty after generation"
    exit 1
}
touch "$SUCCESS"
log "REPORT READY: timestamped corrected results and future plan appended to report.md"
