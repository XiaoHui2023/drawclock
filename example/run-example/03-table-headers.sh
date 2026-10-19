#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUNDLE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
OUTPUT=${1:-"$PWD/drawclock-table-headers.svg"}
"$BUNDLE_DIR/drawclock" -i "$SCRIPT_DIR/../auto-layout/34-configurable-text-and-table.json" -l "$BUNDLE_DIR/libraries" -o "$OUTPUT" --table-headers "Work" "SCAN" "BIST" "Custom" --table-align center
test -s "$OUTPUT"
printf 'Generated %s\n' "$OUTPUT"
