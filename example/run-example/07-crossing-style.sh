#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BUNDLE_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
OUTPUT=${1:-"$PWD/drawclock-crossing-style.svg"}
STYLE=${2:-arc}
"$BUNDLE_DIR/drawclock" -i "$SCRIPT_DIR/../auto-layout/05-dense-cross-root.json" -l "$BUNDLE_DIR/libraries" -o "$OUTPUT" --crossing-style "$STYLE"
test -s "$OUTPUT"
printf 'Generated %s\n' "$OUTPUT"
