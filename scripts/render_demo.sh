#!/usr/bin/env bash
set -euo pipefail

BLENDER_BIN="${BLENDER_BIN:-/Applications/Blender.app/Contents/MacOS/Blender}"

if [[ ! -x "$BLENDER_BIN" ]]; then
  echo "Blender not found at: $BLENDER_BIN" >&2
  echo "Set BLENDER_BIN to your Blender executable." >&2
  exit 1
fi

mkdir -p output
"$BLENDER_BIN" -b \
  -P scripts/render_storyboard.py \
  -- examples/fishing/storyboard.json \
  --output output/fishing-demo.mp4 \
  --save-blend output/fishing-demo.blend

