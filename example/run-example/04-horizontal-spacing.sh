#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUNDLE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
OUTPUT=${1:-"$PWD/drawclock-horizontal-spacing.svg"}
SPACING=${2:-10}
"$BUNDLE_DIR/drawclock" -i "$SCRIPT_DIR/../auto-layout/33-description-colors.json" -l "$BUNDLE_DIR/libraries" -o "$OUTPUT" --horizontal-spacing "$SPACING"
test -s "$OUTPUT"
printf 'Generated %s\n' "$OUTPUT"
