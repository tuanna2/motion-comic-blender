#!/usr/bin/env bash
set -euo pipefail

BLENDER_BIN="${BLENDER_BIN:-/Applications/Blender.app/Contents/MacOS/Blender}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -x "$BLENDER_BIN" ]]; then
  echo "Blender not found at: $BLENDER_BIN" >&2
  echo "Set BLENDER_BIN to your Blender executable." >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "FFmpeg CLI was not found. Install it with: brew install ffmpeg" >&2
  exit 1
fi

mkdir -p output
if ! "$PYTHON_BIN" -c 'import edge_tts' >/dev/null 2>&1; then
  echo "edge-tts is not installed for $PYTHON_BIN" >&2
  echo "Run: $PYTHON_BIN -m pip install -e '.[tts]'" >&2
  exit 1
fi

"$PYTHON_BIN" scripts/generate_demo_assets.py
"$PYTHON_BIN" scripts/generate_voice.py \
  examples/fishing/storyboard.json \
  --output-dir output/fishing-voice \
  --cache-dir output/.voice-cache
"$BLENDER_BIN" -b \
  -P scripts/render_storyboard.py \
  -- examples/fishing/storyboard.json \
  --output output/fishing-demo.mp4 \
  --save-blend output/fishing-demo.blend \
  --audio output/fishing-voice/voice.wav \
  --lip-sync output/fishing-voice/lip_sync.json
