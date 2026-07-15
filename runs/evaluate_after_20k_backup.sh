#!/bin/bash
# Wait for verified final backups, launch corrected evaluation, and pull results.
set -u

cd "$(dirname "$0")/.."
LOCAL_REPO=$(pwd)
CENTRAL_HOST=${CENTRAL_HOST:-moe-reboot}
REMOTE_REPO=${REMOTE_REPO:-/home/exouser/nasa-rna-moe}
POLL_SECONDS=${POLL_SECONDS:-120}
BACKUP_DIR=${BACKUP_DIR:-$LOCAL_REPO/backups/20k_v3_final}
LOCAL_RESULTS=${LOCAL_RESULTS:-$LOCAL_REPO/results}
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=30)
LOG="$BACKUP_DIR/evaluation_watcher.log"

mkdir -p "$BACKUP_DIR" "$LOCAL_RESULTS"
touch "$LOG"

log() {
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$LOG"
}

log "Evaluation watcher started; waiting for ALL_SAFE_TO_SHELVE."
until [ -f "$BACKUP_DIR/ALL_SAFE_TO_SHELVE" ]; do
    sleep "$POLL_SECONDS"
done

worker_idle() {
    local host=$1
    ssh "${SSH_OPTS[@]}" "$host" \
        "if pgrep -af '[t]rain_single.py' >/dev/null; then exit 1; fi; if command -v nvidia-smi >/dev/null 2>&1; then test -z \"\$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d '[:space:]')\"; fi"
}

while :; do
    all_idle=1
    for host in moe-reboot2 moe-reboot-partial; do
        if worker_idle "$host"; then
            log "IDLE $host has no training PID or GPU compute process."
        else
            all_idle=0
            log "WAIT $host is not yet fully idle."
        fi
    done
    [ "$all_idle" -eq 1 ] && break
    sleep "$POLL_SECONDS"
done
touch "$BACKUP_DIR/WORKER_INSTANCES_IDLE"
log "All final checkpoints are verified and worker instances are idle; launching corrected evaluation on $CENTRAL_HOST."

if ! ssh "${SSH_OPTS[@]}" "$CENTRAL_HOST" \
    "cd '$REMOTE_REPO' && test -x runs/run_corrected_interspecies_eval_once.sh && tmux new-session -d -s corrected_interspecies_eval 'cd $REMOTE_REPO && bash runs/run_corrected_interspecies_eval_once.sh'"; then
    log "ERROR failed to launch remote corrected evaluation tmux session"
    exit 1
fi

while :; do
    if ssh "${SSH_OPTS[@]}" "$CENTRAL_HOST" \
        "test -f '$REMOTE_REPO/results/corrected_interspecies_eval.exit_code'"; then
        rc=$(ssh "${SSH_OPTS[@]}" "$CENTRAL_HOST" \
            "cat '$REMOTE_REPO/results/corrected_interspecies_eval.exit_code'")
        break
    fi
    if ! ssh "${SSH_OPTS[@]}" "$CENTRAL_HOST" \
        "tmux has-session -t corrected_interspecies_eval 2>/dev/null"; then
        log "ERROR remote evaluation session exited without an exit-code artifact"
        exit 1
    fi
    log "Corrected evaluation is running on $CENTRAL_HOST."
    sleep "$POLL_SECONDS"
done

if [ "$rc" != "0" ]; then
    log "ERROR corrected evaluation failed with rc=$rc; results remain on $CENTRAL_HOST"
    exit 1
fi
log "Remote corrected evaluation completed; copying result bundle locally."

for name in \
    interspecies_headroom_5k_v2_corrected \
    interspecies_headroom_20k_v3_corrected \
    interspecies_headroom_5k_v2_strict_study_disjoint \
    interspecies_headroom_20k_v3_strict_study_disjoint; do
    rm -rf "$LOCAL_RESULTS/$name.download"
    scp -r "${SSH_OPTS[@]}" \
        "$CENTRAL_HOST:$REMOTE_REPO/results/$name" "$LOCAL_RESULTS/$name.download" || exit 1
    rm -rf "$LOCAL_RESULTS/$name"
    mv "$LOCAL_RESULTS/$name.download" "$LOCAL_RESULTS/$name"
done

for name in \
    interspecies_scale_change_full.json \
    interspecies_scale_change_strict_study_disjoint.json \
    corrected_interspecies_eval_driver.log \
    corrected_interspecies_eval.status \
    corrected_interspecies_eval.exit_code; do
    scp "${SSH_OPTS[@]}" "$CENTRAL_HOST:$REMOTE_REPO/results/$name" "$LOCAL_RESULTS/$name"
done

python3 evaluation/validate_corrected_eval_outputs.py \
    --results-root "$LOCAL_RESULTS" \
    --output "$LOCAL_RESULTS/corrected_interspecies_eval.validation.json" || {
        log "ERROR local result validation failed"
        exit 1
    }
touch "$BACKUP_DIR/EVALUATION_COMPLETE_AND_VALIDATED"
log "EVALUATION COMPLETE AND VALIDATED; results are local and persistent."
