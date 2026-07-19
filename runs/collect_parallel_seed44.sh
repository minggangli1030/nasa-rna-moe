#!/usr/bin/env bash
# Persist the RAM-backed seed-44 worker output, then let the frozen central
# coordinator validate all three reports and make its one decision.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SOURCE_HOST="${SOURCE_HOST:-moe-reboot2}"
DEST_HOST="${DEST_HOST:-moe-reboot}"
SOURCE_DIR="${SOURCE_DIR:-/dev/shm/stage1_organ_k5_train_seed44_v1}"
DEST_ROOT="${DEST_ROOT:-/home/exouser/nasa-rna-moe/results}"
DEST_FINAL="$DEST_ROOT/stage1_organ_k5_train_seed44_v1"
DEST_INCOMING="$DEST_ROOT/.stage1_organ_k5_train_seed44_v1.transfer"
STATE_DIR="${STATE_DIR:-backups/stage1_organ_k5_seed44_parallel}"
POLL_SECONDS="${POLL_SECONDS:-60}"
STATUS="$STATE_DIR/STATUS"

mkdir -p "$STATE_DIR"

set_status() {
  printf '%s %s\n' "$1" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
}

fail() {
  set_status "FAILED reason=$1"
  exit 1
}

set_status "WAITING source=$SOURCE_HOST:$SOURCE_DIR"
while ! ssh -o BatchMode=yes -o ConnectTimeout=15 "$SOURCE_HOST" \
  "test -f '$SOURCE_DIR/COMPLETE'"; do
  if ssh -o BatchMode=yes -o ConnectTimeout=15 "$SOURCE_HOST" \
    "test -f '$SOURCE_DIR/FAILED'"; then
    fail "source_failed"
  fi
  sleep "$POLL_SECONDS"
done

ssh -o BatchMode=yes -o ConnectTimeout=15 "$SOURCE_HOST" \
  "test -s '$SOURCE_DIR/evaluation/report.json' && test -s '$SOURCE_DIR/mechanical_health.json'" \
  || fail "source_missing_validated_outputs"

if ssh -o BatchMode=yes -o ConnectTimeout=15 "$DEST_HOST" \
  "test -e '$DEST_FINAL' || test -e '$DEST_INCOMING'"; then
  fail "destination_exists"
fi

set_status "TRANSFERRING destination=$DEST_HOST:$DEST_INCOMING"
ssh -o BatchMode=yes -o ConnectTimeout=15 "$DEST_HOST" "mkdir -p '$DEST_INCOMING'"
ssh -o BatchMode=yes -o ConnectTimeout=15 "$SOURCE_HOST" \
  "tar -C '$SOURCE_DIR' -cf - ." \
  | ssh -o BatchMode=yes -o ConnectTimeout=15 "$DEST_HOST" \
      "tar -C '$DEST_INCOMING' -xf -" \
  || fail "transfer"

set_status "VERIFYING checksums"
source_checksums="$(ssh -o BatchMode=yes -o ConnectTimeout=15 "$SOURCE_HOST" \
  "cd '$SOURCE_DIR' && find . -type f -print0 | sort -z | xargs -0 sha256sum")" \
  || fail "source_checksums"
destination_checksums="$(ssh -o BatchMode=yes -o ConnectTimeout=15 "$DEST_HOST" \
  "cd '$DEST_INCOMING' && find . -type f -print0 | sort -z | xargs -0 sha256sum")" \
  || fail "destination_checksums"
[[ "$source_checksums" == "$destination_checksums" ]] || fail "checksum_mismatch"

ssh -o BatchMode=yes -o ConnectTimeout=15 "$DEST_HOST" \
  "test -f '$DEST_INCOMING/COMPLETE' && test -s '$DEST_INCOMING/evaluation/report.json' && mv '$DEST_INCOMING' '$DEST_FINAL'" \
  || fail "atomic_install"

set_status "RESUMING central_coordinator"
ssh -o BatchMode=yes -o ConnectTimeout=15 "$DEST_HOST" '
  pid="$(ps -eo pid=,stat=,args= | awk '\''$2 ~ /^T/ && $0 ~ /bash runs\/run_organ_k5_replication_seeds[.]sh$/ {print $1}'\'')"
  test -n "$pid"
  test "$(printf "%s\n" "$pid" | wc -l)" -eq 1
  kill -CONT "$pid"
' || fail "resume_coordinator"

set_status "COMPLETE installed=$DEST_HOST:$DEST_FINAL"
