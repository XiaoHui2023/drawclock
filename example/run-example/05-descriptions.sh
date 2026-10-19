#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUNDLE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
OUTPUT=${1:-"$PWD/drawclock-descriptions.svg"}
"$BUNDLE_DIR/drawclock" -i "$SCRIPT_DIR/../auto-layout/34-configurable-text-and-table.json" -l "$BUNDLE_DIR/libraries" -o "$OUTPUT" --description-align center --description-anchor top-left --description-offset-x 5 --description-offset-y -7
test -s "$OUTPUT"
printf 'Generated %s\n' "$OUTPUT"
