#!/bin/bash
# Commit and push the validated code/protocol after overnight evaluation finishes.
set -u

cd "$(dirname "$0")/.."
BACKUP_DIR=${BACKUP_DIR:-$(pwd)/backups/20k_v3_final}
POLL_SECONDS=${POLL_SECONDS:-120}
PUSH_RETRY_SECONDS=${PUSH_RETRY_SECONDS:-300}
LOG="$BACKUP_DIR/git_backup_watcher.log"
SUCCESS="$BACKUP_DIR/GIT_BACKUP_PUSHED"

mkdir -p "$BACKUP_DIR"
touch "$LOG"

log() {
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$LOG"
}

[ -f "$SUCCESS" ] && exit 0
log "Git watcher started; waiting for validated evaluation results."
until [ -f "$BACKUP_DIR/EVALUATION_COMPLETE_AND_VALIDATED" ]; do
    sleep "$POLL_SECONDS"
done

log "Evaluation is validated; staging repository code, docs, scripts, and tests."
git add -A -- \
    .gitignore \
    CLAUDE.md \
    PROGESS.md \
    README.md \
    core/train_single.py \
    evaluation \
    runs \
    tests

if ! git diff --cached --check >> "$LOG" 2>&1; then
    log "ERROR staged diff failed whitespace validation; push not attempted"
    exit 1
fi

if ! git diff --cached --quiet; then
    if ! git commit -m "Fix interspecies evaluation and automate V3 backup" >> "$LOG" 2>&1; then
        log "ERROR git commit failed; inspect $LOG"
        exit 1
    fi
    log "Created commit $(git rev-parse --short HEAD)."
else
    log "No staged changes; using existing commit $(git rev-parse --short HEAD)."
fi

branch=$(git branch --show-current)
if [ -z "$branch" ]; then
    log "ERROR repository is in detached HEAD state"
    exit 1
fi

until git push origin "$branch" >> "$LOG" 2>&1; do
    log "RETRY git push failed; retrying in ${PUSH_RETRY_SECONDS}s"
    sleep "$PUSH_RETRY_SECONDS"
done

printf '%s\t%s\t%s\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$branch" "$(git rev-parse HEAD)" \
    > "$SUCCESS"
log "GIT BACKUP PUSHED branch=$branch commit=$(git rev-parse HEAD)"
