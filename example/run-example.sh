#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUNDLE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
OUTPUT=${1:-"$PWD/drawclock-example.svg"}
TITLE=${2:-"DrawClock release example"}

"$BUNDLE_DIR/drawclock" \
  -i "$SCRIPT_DIR/auto-layout/34-configurable-text-and-frequency.json" \
  -l "$BUNDLE_DIR/libraries" \
  -o "$OUTPUT" \
  --title "$TITLE" \
  --crossing-style arc \
  --description-align center \
  --description-anchor top-left \
  --horizontal-spacing 180 \
  --name-align center \
  --frequency-headers "Work frequency" "SCAN" "BIST" "Custom" \
  --frequency-align center

test -s "$OUTPUT"
printf 'Generated %s\n' "$OUTPUT"
