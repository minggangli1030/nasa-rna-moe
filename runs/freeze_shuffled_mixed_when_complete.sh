#!/bin/bash
# Freeze and checksum the completed shuffled pooled checkpoint on persistent storage.
set -uo pipefail
cd "$(dirname "$0")/.."

TRAIN_EXIT=results/mixed_20k_v3_shuffled_train.exit_code
SOURCE=checkpoints/mixed_20k_v3_shuffled
DESTINATION=checkpoints/mixed_20k_v3_shuffled_frozen
TEMP_DESTINATION=checkpoints/mixed_20k_v3_shuffled_frozen.incomplete
STATUS=results/mixed_20k_v3_shuffled_freeze.status
EXIT_CODE=results/mixed_20k_v3_shuffled_freeze.exit_code
COMPLETE=results/mixed_20k_v3_shuffled_freeze.COMPLETE

if [ -f "$COMPLETE" ]; then
    exit 0
fi

printf 'WAITING_FOR_TRAINING %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
while [ ! -f "$TRAIN_EXIT" ]; do
    sleep 300
done

train_rc=$(cat "$TRAIN_EXIT")
if [ "$train_rc" != "0" ] || [ ! -f "$SOURCE/best_model.pt" ]; then
    printf 'BLOCKED training_rc=%s source=%s %s\n' \
        "$train_rc" "$SOURCE" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    printf '1\n' > "$EXIT_CODE"
    exit 1
fi
if [ -e "$DESTINATION" ] || [ -e "$TEMP_DESTINATION" ]; then
    printf 'BLOCKED destination_exists %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    printf '1\n' > "$EXIT_CODE"
    exit 1
fi

printf 'FREEZING %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
mkdir -p "$TEMP_DESTINATION"
cp -a "$SOURCE"/. "$TEMP_DESTINATION"/
(
    cd "$TEMP_DESTINATION" || exit 1
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
    sha256sum -c SHA256SUMS
) > results/mixed_20k_v3_shuffled_freeze.log 2>&1
rc=$?

if [ "$rc" -eq 0 ]; then
    printf '%s\n' "source=$(readlink -f "$SOURCE")" > "$TEMP_DESTINATION/FREEZE_METADATA.txt"
    printf '%s\n' "completed_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')" >> "$TEMP_DESTINATION/FREEZE_METADATA.txt"
    mv "$TEMP_DESTINATION" "$DESTINATION"
    printf 'COMPLETE %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
    touch "$COMPLETE"
else
    printf 'FAILED rc=%s %s\n' "$rc" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > "$STATUS"
fi
printf '%s\n' "$rc" > "$EXIT_CODE"
exit "$rc"
