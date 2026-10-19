#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUNDLE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
OUTPUT=${1:-"$PWD/drawclock-title.svg"}
TITLE=${2:-"DrawClock title example"}
"$BUNDLE_DIR/drawclock" -i "$SCRIPT_DIR/../auto-layout/01-linear.json" -l "$BUNDLE_DIR/libraries" -o "$OUTPUT" --title "$TITLE"
test -s "$OUTPUT"
printf 'Generated %s\n' "$OUTPUT"
