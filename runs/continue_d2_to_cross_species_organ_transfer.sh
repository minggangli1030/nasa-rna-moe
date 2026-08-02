#!/usr/bin/env bash
# Wait for frozen D2, then run the frozen replacement D1b smoke and full audit.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

STATUS_FILE="${STATUS_FILE:-/media/volume/moe-reboot/results/cross_species_organ_transfer_continuation.status}"
D2_STATUS="${D2_STATUS:-/media/volume/moe-reboot/results/osdr_hallmark_downstream_f38b125_retry1.status}"
D2_FULL="${D2_FULL:-/media/volume/moe-reboot/results/osdr_hallmark_downstream_full_f38b125_retry1}"
SMOKE_OUTPUT="${SMOKE_OUTPUT:-/media/volume/moe-reboot/results/cross_species_organ_transfer_smoke}"
FULL_OUTPUT="${FULL_OUTPUT:-/media/volume/moe-reboot/results/cross_species_organ_transfer_full}"
PROTOCOL_SHA256=c7309e52e3e291c71198e8c291caba2ea9b4c3bb000b904a2b00da3a6527c54a
CODE_COMMIT="$(git rev-parse HEAD)"

echo "WAITING_FOR_D2" > "$STATUS_FILE"
for _ in $(seq 1 2880); do
  state="$(cat "$D2_STATUS" 2>/dev/null || true)"
  if [[ "$state" == "COMPLETE" ]]; then
    break
  fi
  if ! pgrep -f '[e]valuate_osdr_hallmark_downstream' >/dev/null; then
    echo "BLOCKED_D2_NOT_RUNNING_STATE_${state:-missing}" > "$STATUS_FILE"
    exit 3
  fi
  sleep 60
done

[[ "$(cat "$D2_STATUS" 2>/dev/null || true)" == "COMPLETE" ]] || {
  echo "BLOCKED_D2_TIMEOUT" > "$STATUS_FILE"
  exit 4
}
(cd "$D2_FULL" && sha256sum -c IMMUTABLE_SHA256SUMS)

echo "REPLACEMENT_SMOKE_RUNNING" > "$STATUS_FILE"
CODE_COMMIT="$CODE_COMMIT" \
OUTPUT_DIR="$SMOKE_OUTPUT" \
EXPECTED_PROTOCOL_SHA256="$PROTOCOL_SHA256" \
SMOKE=1 \
runs/run_cross_species_organ_transfer.sh

[[ -f "$SMOKE_OUTPUT/COMPLETE" ]]
(cd "$SMOKE_OUTPUT" && sha256sum -c IMMUTABLE_SHA256SUMS)
echo "REPLACEMENT_SMOKE_COMPLETE" > "$STATUS_FILE"

CODE_COMMIT="$CODE_COMMIT" \
OUTPUT_DIR="$FULL_OUTPUT" \
EXPECTED_PROTOCOL_SHA256="$PROTOCOL_SHA256" \
runs/run_cross_species_organ_transfer.sh

[[ -f "$FULL_OUTPUT/COMPLETE" ]]
(cd "$FULL_OUTPUT" && sha256sum -c IMMUTABLE_SHA256SUMS)
echo "COMPLETE" > "$STATUS_FILE"
