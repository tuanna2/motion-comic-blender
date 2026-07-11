# Motion Comic Blender

JSON-driven 2D/2.5D motion-comic renderer for Blender. The engine builds a scene from reusable assets, applies deterministic motion presets, and renders an MP4 without an AI video model.

The MVP includes a 10-second fishing demo with procedural placeholder art, subtitles, camera motion, and reusable animations. Transparent PNG assets are supported for replacing the placeholders later.

## What is included

- Headless Blender rendering from storyboard JSON
- Orthographic 2D/2.5D scene composition
- Transparent PNG loader with alpha materials
- Versioned character library with `manifest.json` and `asset_ref`
- Layered character expressions, anchors, and mouth sprite swapping
- Procedural fishing character and fish for a zero-asset demo
- Motion presets: `enter`, `idle`, `talk`, `pull_rod`, `fish_jump`, `shake`, `impact`, `fall`
- Camera presets: `camera_zoom`, `camera_pan`
- Timed subtitles
- Direct H.264 MP4 output
- Pure-Python validation and unit tests

## Requirements

- macOS, Linux, or Windows
- Blender 4.2 or newer (including Blender 5.x)
- FFmpeg CLI (`brew install ffmpeg` on macOS)
- Python 3.11+ only for validation/tests; Blender supplies Python for rendering

No pip packages are required for the MVP. Blender renders lossless PNG frames,
then the external FFmpeg CLI encodes them to H.264 MP4. This works with Blender
5.x builds that do not expose `FFMPEG` as a direct render format.

## Render the demo on macOS

```bash
git clone https://github.com/tuanna2/motion-comic-blender.git
cd motion-comic-blender
chmod +x scripts/render_demo.sh
./scripts/render_demo.sh
```

Output:

```text
output/fishing-demo.mp4
output/fishing-demo.blend
```

If Blender is installed elsewhere:

```bash
BLENDER_BIN=/path/to/blender ./scripts/render_demo.sh
```

Equivalent command:

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b \
  -P scripts/render_storyboard.py \
  -- examples/fishing/storyboard.json \
  --output output/fishing-demo.mp4 \
  --save-blend output/fishing-demo.blend
```

Add `--keep-frames` if you want to retain the intermediate PNG sequence. By
default it is deleted after FFmpeg successfully creates the MP4. If encoding
fails, the frames are kept for recovery.

To build a `.blend` file without rendering the MP4:

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b \
  -P scripts/render_storyboard.py \
  -- examples/fishing/storyboard.json \
  --output output/fishing-demo.mp4 \
  --save-blend output/fishing-demo.blend \
  --no-render
```

## Validate JSON without Blender

```bash
python3 scripts/check_project.py examples/fishing/storyboard.json
python3 -m unittest discover -s tests -v
```

## Storyboard coordinates

The default camera sees a 16:9 world approximately spanning:

- X: `-8` to `8`
- Y: `-4.5` to `4.5`
- Z: layer order; higher values appear in front

Each scene has its own elements and relative timing. Scene durations are concatenated automatically.

## Reusable character library

Production characters live outside episode storyboards:

```text
assets/characters/angler/
├── manifest.json
└── generated/            # demo PNG layers generated locally
    ├── body.png
    ├── head.png
    ├── mouth_closed.png
    └── mouth_open.png
```

Generate the placeholder PNG layers without Pillow or other dependencies:

```bash
python3 scripts/generate_demo_assets.py
```

The manifest fixes part dimensions, offsets, layer order, expressions, and anchors. Episodes reference the immutable version instead of declaring each PNG again:

```json
{
  "id": "angler",
  "kind": "character",
  "asset_ref": "char_angler@1",
  "appearance": "default",
  "expression": "angry",
  "x": -2.8,
  "y": -3.25,
  "z": 2,
  "scale": 0.9
}
```

`char_angler@1` is used by both `examples/fishing/storyboard.json` and
`examples/fishing_episode_2/storyboard.json`. They render different scenes and
expressions from the exact same PNG layers. A reference without a version, such
as `char_angler`, resolves to the latest registered version; pinning `@1` is
recommended for reproducible episodes.

The asset library location is configured relative to each storyboard:

```json
"settings": {
  "asset_library": "../../assets"
}
```

To render the second episode after generating assets:

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b \
  -P scripts/render_storyboard.py \
  -- examples/fishing_episode_2/storyboard.json \
  --output output/fishing-episode-2.mp4
```

```json
{
  "version": "1.0",
  "title": "My episode",
  "settings": {"width": 1280, "height": 720, "fps": 30},
  "scenes": [
    {
      "id": "scene_1",
      "duration": 4,
      "background_color": "#7dd3fc",
      "elements": [
        {
          "id": "hero",
          "kind": "image",
          "asset": "assets/hero.png",
          "x": -2,
          "y": -1,
          "z": 2,
          "width": 2.5
        }
      ],
      "motions": [
        {
          "target": "hero",
          "preset": "enter",
          "start": 0,
          "end": 0.8,
          "params": {"from_x": -5}
        }
      ],
      "subtitles": [
        {"start": 1, "end": 3, "text": "Xin chào!"}
      ]
    }
  ]
}
```

Direct `kind: "image"` paths are resolved relative to the storyboard JSON file. Character part paths are resolved relative to their manifest file.

## Project structure

```text
motion_comic/              Blender/Python engine
  assets.py                PNG and procedural object factories
  builder.py               Timeline and render builder
  motions.py               Reusable animation presets
  registry.py              Versioned asset manifest discovery
  schema.py                JSON validation
examples/fishing/          Runnable fishing demo
scripts/render_storyboard.py
scripts/check_project.py
tests/                     Blender-independent unit tests
```

## MVP limitations

- Generated layered art is intentionally simple and exists only to verify the pipeline.
- TTS, audio mixing, lip-sync analysis, UI editing, and skeletal character rigs are planned next.
- Motions that animate the same property at overlapping times can overwrite one another; keep them sequential unless the overlap is intentional.
- Blender must include H.264/FFmpeg support, as standard Blender builds do.

## Next milestones

1. Edge-TTS voice generation and automatic audio placement
2. Mouth sprite/viseme switching
3. Prop attachment using character anchors
4. 20-30 production motion presets
5. Web storyboard editor and batch episode queue

## License

MIT
