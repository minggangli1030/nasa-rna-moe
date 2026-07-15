#!/bin/bash
# Back up live V3 snapshots now, then final checkpoints as each run completes.
set -u

cd "$(dirname "$0")/.."
LOCAL_REPO=$(pwd)
CENTRAL_HOST=${CENTRAL_HOST:-moe-reboot}
REMOTE_REPO=${REMOTE_REPO:-/home/exouser/nasa-rna-moe}
POLL_SECONDS=${POLL_SECONDS:-120}
BACKUP_DIR=${BACKUP_DIR:-$LOCAL_REPO/backups/20k_v3_final}
CHECKPOINT_DIR=${CHECKPOINT_DIR:-$LOCAL_REPO/checkpoints}
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=30)
RUNS=(
    "moe-reboot2|human_20k_v3|/home/exouser/train_human_20k_v3.log"
    "moe-reboot-partial|mouse_20k_v3|/home/exouser/train_mouse_20k_v3.log"
    "moe-reboot|mixed_20k_v3|/home/exouser/train_mixed_20k_v3.log"
)

mkdir -p "$BACKUP_DIR" "$CHECKPOINT_DIR"
WATCH_LOG="$BACKUP_DIR/backup_watcher.log"
MANIFEST="$BACKUP_DIR/checkpoint_manifest.tsv"
touch "$WATCH_LOG" "$MANIFEST"

log() {
    printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$WATCH_LOG"
}

local_md5() {
    if command -v md5 >/dev/null 2>&1; then
        md5 -q "$1"
    else
        md5sum "$1" | awk '{print $1}'
    fi
}

remote_md5() {
    local host=$1
    local path=$2
    ssh "${SSH_OPTS[@]}" "$host" "test -s '$path' && md5sum '$path'" 2>/dev/null |
        awk '{print $1}'
}

download_verified() {
    local host=$1
    local remote_path=$2
    local local_path=$3
    local expected tmp actual
    expected=$(remote_md5 "$host" "$remote_path")
    if [ -z "$expected" ]; then
        log "WAIT $host: source unavailable: $remote_path"
        return 1
    fi

    mkdir -p "$(dirname "$local_path")"
    if [ -s "$local_path" ] && [ "$(local_md5 "$local_path")" = "$expected" ]; then
        log "VERIFIED existing $local_path md5=$expected"
        return 0
    fi

    tmp="$local_path.download.$$"
    rm -f "$tmp"
    log "COPY $host:$remote_path -> $local_path"
    if ! scp "${SSH_OPTS[@]}" "$host:$remote_path" "$tmp"; then
        rm -f "$tmp"
        log "RETRY scp failed for $host:$remote_path"
        return 1
    fi
    actual=$(local_md5 "$tmp")
    if [ "$actual" != "$expected" ]; then
        rm -f "$tmp"
        log "RETRY checksum mismatch for $host:$remote_path expected=$expected actual=$actual"
        return 1
    fi
    mv "$tmp" "$local_path"
    log "VERIFIED $local_path md5=$actual bytes=$(stat -f '%z' "$local_path" 2>/dev/null || stat -c '%s' "$local_path")"
}

mirror_final_to_central() {
    local run=$1
    local local_path=$2
    local expected remote_tmp actual
    expected=$(local_md5 "$local_path")
    remote_tmp="$REMOTE_REPO/checkpoints/$run/best_model.pt.uploading"
    if ! ssh "${SSH_OPTS[@]}" "$CENTRAL_HOST" \
        "mkdir -p '$REMOTE_REPO/checkpoints/$run'"; then
        return 1
    fi
    log "MIRROR $run final checkpoint to $CENTRAL_HOST persistent storage"
    if ! scp "${SSH_OPTS[@]}" "$local_path" "$CENTRAL_HOST:$remote_tmp"; then
        return 1
    fi
    if ! ssh "${SSH_OPTS[@]}" "$CENTRAL_HOST" \
        "mv '$remote_tmp' '$REMOTE_REPO/checkpoints/$run/best_model.pt' && sync"; then
        return 1
    fi
    actual=$(remote_md5 "$CENTRAL_HOST" "$REMOTE_REPO/checkpoints/$run/best_model.pt")
    [ "$actual" = "$expected" ] || {
        log "RETRY central checksum mismatch for $run expected=$expected actual=$actual"
        return 1
    }
    log "VERIFIED central $run md5=$actual"
}

archive_metadata() {
    local host=$1
    local run=$2
    local training_log=$3
    local output tmp
    output="$BACKUP_DIR/$run.metadata.tar.gz"
    tmp="$output.download.$$"
    rm -f "$tmp"
    if ! ssh "${SSH_OPTS[@]}" "$host" \
        "cd '$REMOTE_REPO' && tar -czf - --exclude='*.pt' 'checkpoints/$run' '$training_log'" \
        > "$tmp"; then
        rm -f "$tmp"
        log "RETRY metadata archive failed for $run"
        return 1
    fi
    tar -tzf "$tmp" >/dev/null || {
        rm -f "$tmp"
        log "RETRY metadata archive is corrupt for $run"
        return 1
    }
    mv "$tmp" "$output"
    log "VERIFIED metadata archive $output"
}

run_state() {
    local host=$1
    local training_log=$2
    ssh "${SSH_OPTS[@]}" "$host" \
        "if grep -aFq 'Training complete!' '$training_log' 2>/dev/null && ! pgrep -af '[t]rain_single.py' >/dev/null; then echo READY; elif pgrep -af '[t]rain_single.py' >/dev/null; then echo RUNNING; else echo STOPPED_WITHOUT_COMPLETE; fi" \
        2>/dev/null || echo UNREACHABLE
}

backup_pre_completion_snapshot() {
    local host=$1
    local run=$2
    local marker="$BACKUP_DIR/$run.PRE_COMPLETION_SNAPSHOT_VERIFIED"
    [ -f "$marker" ] && return 0
    if download_verified "$host" \
        "$REMOTE_REPO/checkpoints/$run/best_model.pre_completion_snapshot.pt" \
        "$CHECKPOINT_DIR/$run/best_model.pre_completion_snapshot.pt"; then
        touch "$marker"
        log "SAFE SNAPSHOT $run is now off-instance"
        return 0
    fi
    return 1
}

backup_final() {
    local host=$1
    local run=$2
    local training_log=$3
    local local_path="$CHECKPOINT_DIR/$run/best_model.pt"
    local md5 epoch val_loss

    download_verified "$host" "$REMOTE_REPO/checkpoints/$run/best_model.pt" "$local_path" || return 1
    archive_metadata "$host" "$run" "$training_log" || return 1
    if [ "$host" != "$CENTRAL_HOST" ]; then
        mirror_final_to_central "$run" "$local_path" || return 1
    fi

    md5=$(local_md5 "$local_path")
    epoch=$(ssh "${SSH_OPTS[@]}" "$host" \
        "python3 -c \"import json;print(json.load(open('$REMOTE_REPO/checkpoints/$run/global_best_val_loss.json'))['epoch'])\"" 2>/dev/null || echo unknown)
    val_loss=$(ssh "${SSH_OPTS[@]}" "$host" \
        "python3 -c \"import json;print(json.load(open('$REMOTE_REPO/checkpoints/$run/global_best_val_loss.json'))['val_loss'])\"" 2>/dev/null || echo unknown)
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$run" "$host" "$md5" "$epoch" "$val_loss" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
        >> "$MANIFEST"
    touch "$BACKUP_DIR/$run.SAFE_TO_SHELVE"
    ssh "${SSH_OPTS[@]}" "$host" \
        "touch '$REMOTE_REPO/$run.SAFE_TO_SHELVE'" 2>/dev/null || true
    log "SAFE TO SHELVE $host ($run): final md5=$md5 epoch=$epoch val_loss=$val_loss"
}

log "Watcher started; first securing pre-completion snapshots."
while :; do
    remaining=0
    for specification in "${RUNS[@]}"; do
        IFS='|' read -r host run training_log <<< "$specification"
        final_marker="$BACKUP_DIR/$run.SAFE_TO_SHELVE"
        [ -f "$final_marker" ] && continue
        remaining=$((remaining + 1))

        backup_pre_completion_snapshot "$host" "$run" || true
        state=$(run_state "$host" "$training_log")
        case "$state" in
            READY)
                log "READY $host ($run); starting final backup"
                backup_final "$host" "$run" "$training_log" || \
                    log "RETRY final backup incomplete for $host ($run)"
                ;;
            RUNNING)
                log "RUNNING $host ($run)"
                ;;
            STOPPED_WITHOUT_COMPLETE)
                log "ALERT $host ($run) stopped without completion marker; do not shelve"
                ;;
            *)
                log "WAIT $host ($run) unreachable or unknown state: $state"
                ;;
        esac
    done

    if [ "$remaining" -eq 0 ]; then
        log "ALL THREE FINAL CHECKPOINTS VERIFIED; every instance is safe to shelve."
        touch "$BACKUP_DIR/ALL_SAFE_TO_SHELVE"
        exit 0
    fi
    sleep "$POLL_SECONDS"
done
