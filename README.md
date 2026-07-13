# Motion Comic Blender

JSON-driven 2D/2.5D motion-comic renderer for Blender. The engine builds a scene from reusable assets, applies deterministic motion presets, and renders an MP4 without an AI video model.

The MVP includes a 10-second fishing demo with procedural placeholder art,
Vietnamese speech, word-timed lip sync, subtitles, camera motion, and reusable
animations. Transparent PNG assets are supported for replacing the placeholders later.

## What is included

- Headless Blender rendering from storyboard JSON
- Orthographic 2D/2.5D scene composition
- Transparent PNG loader with alpha materials
- Versioned character library with `manifest.json` and `asset_ref`
- MMD character backend with precompiled PMX collections and NLA Action libraries
- Layered character expressions, anchors, and mouth sprite swapping
- Hierarchical two-arm 2D character rig with head, shoulders, elbows, hips, and knees
- Reusable scene templates with named slots and automatic collision-safe placement
- Scene anchors for water/ground positions and prop attachment to character anchors
- Procedural fishing character and fish for a zero-asset demo
- Semantic catalog with 305 character, interaction, fight, camera, and effect actions
- Backward-compatible specialized presets such as `pull_rod` and `fish_jump`
- Timed subtitles
- Cached Edge-TTS voice generation and WordBoundary-driven mouth animation
- FFmpeg audio timeline mixing and H.264/AAC MP4 output
- Direct FFmpeg pipe encoding without retaining thousands of PNG frames
- Batch queue with shared cache, resume, retries, parallel workers, and status JSON
- Series registry with fixed character identities and distinct voice profiles
- Local AI story-creation UI with prompt copy and result validation
- Pure-Python validation and unit tests

## Requirements

- macOS, Linux, or Windows
- Blender 4.2 or newer (including Blender 5.x)
- FFmpeg CLI (`brew install ffmpeg` on macOS)
- Python 3.11+ for validation, asset generation, and Edge-TTS
- Internet access when synthesizing uncached dialogue

Blender streams each completed frame through an external FFmpeg pipe into an
H.264/AAC MP4. Only one temporary PNG exists at a time. This works with Blender
5.x builds that do not expose `FFMPEG` as a direct render format. Edge-TTS runs in the system Python before
Blender, so no package needs to be installed into Blender's bundled Python.

## Render the demo on macOS

```bash
git clone https://github.com/tuanna2/motion-comic-blender.git
cd motion-comic-blender
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[tts]'
chmod +x scripts/render_demo.sh
./scripts/render_demo.sh
```

Output:

```text
output/fishing-demo.mp4
output/fishing-demo.blend
output/fishing-voice/voice.wav
output/fishing-voice/lip_sync.json
```

If Blender is installed elsewhere:

```bash
BLENDER_BIN=/path/to/blender ./scripts/render_demo.sh
```

Equivalent command:

```bash
python3 scripts/generate_demo_assets.py
python3 scripts/generate_voice.py \
  examples/fishing/storyboard.json \
  --output-dir output/fishing-voice \
  --cache-dir output/.voice-cache

/Applications/Blender.app/Contents/MacOS/Blender -b \
  -P scripts/render_storyboard.py \
  -- examples/fishing/storyboard.json \
  --output output/fishing-demo.mp4 \
  --save-blend output/fishing-demo.blend \
  --audio output/fishing-voice/voice.wav \
  --lip-sync output/fishing-voice/lip_sync.json
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

## Scene templates and automatic layout

Scene templates keep production coordinates out of episode storyboards. The
demo uses `scene_river_bank@1`, whose manifest defines `left`, `center`,
`right`, `far_left`, and `far_right` slots plus named water anchors.

```json
{
  "id": "river_intro",
  "template_ref": "scene_river_bank@1",
  "elements": [
    {
      "id": "angler",
      "kind": "character",
      "asset_ref": "char_angler@1",
      "slot": "left"
    }
  ]
}
```

Use `"slot": "auto"` to select the next free slot from the template's
`auto_order`. Reusing an occupied slot raises a validation error unless the
element explicitly sets `"allow_overlap": true`. Explicit `x`, `y`, `z`, or
`scale` values override only that slot default.

Non-character objects can use named scene anchors:

```json
{
  "id": "monster_fish",
  "kind": "fish",
  "scene_anchor": "water_right"
}
```

## Attaching props to character anchors

The straw-hat demo is a reusable `sprite_prop` manifest. It is positioned
relative to the character's `head` anchor, so it follows every root motion,
shake, entrance, and fall automatically.

```json
{
  "id": "angler_hat",
  "kind": "prop",
  "asset_ref": "prop_straw_hat@1",
  "attach": {
    "target": "angler",
    "anchor": "head",
    "offset": [0, 0.5],
    "z": 0.3
  }
}
```

Scene layouts live under `assets/scenes/`, props under `assets/props/`, and
characters under `assets/characters/`. All three use versioned manifests.

## Hierarchical 2D character rig

Each moving PNG part owns a Blender Empty controller. Child controllers use
coordinates relative to their parent, so rotating a shoulder moves the elbow,
hand, and fishing rod together; rotating the head also moves its eyes, mouth,
and attached hat.

```text
body
├── head
├── arm_left_upper
│   └── forearm_left
├── arm_upper
│   └── forearm
│       └── rod
├── leg_left_upper
│   └── leg_left_lower
└── leg_right_upper
    └── leg_right_lower
```

A rigged part in the character manifest declares the controller pivot with
`joint`, the parent controller with `parent`, and its PNG position relative to
that pivot with `sprite_offset`:

```json
{
  "id": "forearm",
  "asset": "generated/forearm.png",
  "parent": "arm_upper",
  "joint": [0.76, 0],
  "sprite_offset": [0.36, 0],
  "width": 0.78
}
```

Storyboard motions stay semantic and do not contain per-frame coordinates:

```json
{
  "target": "angler",
  "action": "walk",
  "start": 0,
  "end": 1.2,
  "params": {"from_x": -4, "cycles": 3}
}
```

`walk` drives both hip/knee chains, `wave` drives shoulder/elbow, `look` and
`nod` drive the neck, and `pull_rod` coordinates body lean, head compensation,
shoulder, elbow, rod, and root translation. Custom motions can also target a
registered controller such as `angler.head` from Python.

## Edge-TTS and lip sync

Global voice defaults live in `settings.tts`. Every spoken subtitle declares
the element ID that owns the mouth with `speaker`. A subtitle may override any
voice setting, which supports multiple characters in the same scene.

```json
{
  "settings": {
    "tts": {
      "voice": "vi-VN-HoaiMyNeural",
      "rate": "+8%",
      "volume": "+0%",
      "pitch": "+0Hz"
    }
  },
  "scenes": [
    {
      "id": "scene_1",
      "duration": 4,
      "elements": [{"id": "angler", "kind": "character", "asset_ref": "char_angler@1"}],
      "subtitles": [
        {
          "start": 1,
          "end": 3,
          "text": "Hôm nay nhất định phải bắt được cá lớn!",
          "speaker": "angler"
        }
      ]
    }
  ]
}
```

`generate_voice.py` streams audio and `WordBoundary` metadata from Edge-TTS.
Each line is cached using a hash of its text, voice, rate, volume, and pitch.
It then produces:

- `voice.wav`: all lines positioned on the complete episode timeline
- `lip_sync.json`: mouth-open intervals grouped by scene and speaker

Blender consumes only the local sidecar. It swaps `mouth_closed` and
`mouth_open` at the generated frames; characters with one mouth sprite use a
scale-animation fallback. FFmpeg finally muxes `voice.wav` into the rendered
MP4 as AAC. The old `talk` motion remains available for silent previews.

Run `generate_voice.py --force` to bypass the cache. Change only one dialogue
line and only that line is synthesized again.

## Semantic action catalog

Stage 5 accepts every action key through the readable `action` field. The 305
registered keys cover movement, body poses, two-hand gestures, interactions,
dialogue acting, four emotion groups, thinking, fights, daily activity,
motion-comic simulation, cameras, effects, and the legacy presets.

```json
{
  "target": "hero",
  "action": "punch",
  "start": 1.2,
  "end": 2.5,
  "params": {"with": "rival", "recoil": 1.0}
}
```

Interactions use `params.with` to identify the second character. Fight actions
compose wind-up, fast pose shift, contact, recoil, and settle instead of trying
to reproduce every intermediate drawing. Camera and effect actions can be
placed on the same timeline:

```json
[
  {"target": "hero", "action": "punch", "start": 1.2, "end": 2.5, "params": {"with": "rival"}},
  {"target": "camera", "action": "impact_flash", "start": 1.8, "end": 2.2},
  {"target": "camera", "action": "camera_shake", "start": 1.8, "end": 2.5}
]
```

The character now has two shoulder/elbow chains plus dynamic `normal`, `happy`,
`angry`, `sad`, `surprised`, `blush`, and `crying` face layers. Procedural
symbols and overlays cover question/exclamation marks, anger, speed, dust,
screen flashes, auras, blush, and tears.

Print the complete catalog for an LLM storyboard prompt or editor:

```bash
python3 scripts/list_actions.py --format json
python3 scripts/list_actions.py --category fight --format markdown
```

See `docs/ACTIONS.md` and the 20-second
`examples/action_showcase/storyboard.json` for multi-character examples.

Elements such as impact labels can be visible for only part of a scene:

```json
{
  "id": "impact_text",
  "kind": "text",
  "text": "CÁ KHỔNG LỒ!",
  "visible_start": 2.2,
  "visible_end": 3.2
}
```

## Batch production

`examples/batch.json` accepts either a ready `storyboard` or an AI-friendly
`episode_plan`. Plans are compiled before TTS/render. A batch shares the TTS
cache and the content-addressed MMD model/action cache, skips existing MP4
outputs, retries failures, and preserves status across restarts.

Preview commands without starting Blender:

```bash
python3 scripts/render_batch.py examples/batch.json --dry-run
```

Render sequentially, which is recommended for a base Mac mini M4:

```bash
python3 scripts/render_batch.py examples/batch.json
```

Use `--workers 2` only when memory allows two Blender processes. Use `--force`
to replace existing videos and `--force-voice` to bypass cached TTS. Progress
is resumable from existing outputs and recorded at:

```text
output/batch/batch_status.json
```

## Create a complete story with the fixed cast

The production pipeline includes a five-character MMD urban mystery/rebirth
series. Start the local prompt UI:

```bash
python3 scripts/story_creator_ui.py
```

Then open:

```text
http://127.0.0.1:8765
```

Choose 10-30 minutes, narration mode, protagonist, genre, and premise. The UI
generates two prompts: complete story source, then compact scene/visual-beat
planning. The deterministic compiler assigns MMD assets, voices, slots,
locations, action recipes and camera defaults. The render UI shows frame
progress and live logs and supports Cancel/Resume.

The five IDs resolve to MMD manifests now. For the learning MVP they reuse the
compiled demo model with deterministic tint and scale variants; replace each
manifest's `source`/`blend` with a licensed final PMX to make face, hair and
clothes truly unique without changing storyboards.

See `docs/SERIES.md`, `schemas/series.schema.json`, and
`schemas/story_source.schema.json`.

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
          "action": "enter_scene",
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
  action_catalog.py        305 semantic action registrations
  effects.py               Procedural symbols, flashes, and auras
  rig.py                   Rig hierarchy validation and ordering
  batch.py                 Batch validation and command planning
  cache.py                 Content-addressed MMD model/action cache
  compiler.py              Episode-plan to storyboard compiler
  action_recipes.py        Reusable high-level action composition
  spaces.py                Scene-space floor/wall/accent/light builder
  series.py                Fixed cast and story-source validation
  story_prompt.py          AI story prompt generation
  voice.py                 TTS jobs, cache keys, word cues, and audio mixing
  lipsync.py               Lip-sync sidecar validation and frame conversion
  registry.py              Versioned asset manifest discovery
  layout.py                Slot, scene-anchor, and auto-layout resolution
  schema.py                JSON validation
examples/fishing/          Runnable fishing demo
examples/action_showcase/  Multi-character action demo
examples/production/       AI episode-plan and MMD production example
scripts/render_storyboard.py
scripts/generate_voice.py
scripts/render_batch.py
scripts/list_actions.py
scripts/story_creator_ui.py
scripts/compile_episode.py
scripts/generate_story_prompt.py
scripts/check_story_source.py
scripts/check_project.py
tests/                     Blender-independent unit tests
```

## Production pipeline C-F

- C: five fixed MMD character manifests, distinct voice profiles, reusable
  action recipes, and five scene-space templates.
- D: AI outputs a compact episode plan; the compiler owns assets, voices,
  timing estimates, slots, spaces, recipe expansion, and final validation.
- E: persisted UI jobs expose live log/frame progress, Cancel, and Resume after
  process or UI restarts.
- F: batch accepts storyboard or episode plan and shares TTS plus compiled
  MMD model/action caches across episodes.

Compile the included production plan without Blender:

```bash
python3 scripts/compile_episode.py examples/production/episode_plan.json \
  --output output/production/storyboard.json
python3 scripts/check_project.py output/production/storyboard.json
```

## MVP limitations

- Generated layered art is intentionally simple and exists only to verify the pipeline.
- Lip sync currently uses open/closed mouth sprites at word timing, not phoneme-specific visemes.
- Complex item transfer, permanent hand attachment, and true hand/foot IK are approximated with poses.
- `screen_blur`, `freeze_frame`, and `slow_motion` are deterministic visual holds and do not retime audio yet.
- Edge-TTS is an unofficial online integration and may change or become unavailable; cached lines remain renderable.
- For a commercial production dependency, evaluate a provider with explicit service terms and availability guarantees.
- The five starter MMD identities currently share one learning model geometry;
  tint/scale makes them distinguishable, but production still needs five
  separately licensed PMX character designs.
- IK controls, mesh deformation, sound effects, music ducking, and visual timeline editing are planned next.
- Motions that animate the same property at overlapping times can overwrite one another; keep them sequential unless the overlap is intentional.
- Blender must include H.264/FFmpeg support, as standard Blender builds do.

## Next milestones

1. Phoneme-specific visemes and reusable facial pose sets
2. Sound effects, music tracks, loudness normalization, and ducking
3. Optional hand/foot IK, prop attachment events, and reusable body pose library
4. Content templates, automatic action scheduling, and render-farm workers
5. Web storyboard, dialogue, action, and pose editor

## License

MIT
## Direct MP4 rendering

Direct encoding is now the default. Blender renders one temporary PNG at a time and streams it
straight into external FFmpeg, so a long episode no longer leaves tens of thousands of frames on
disk. This works even on Blender builds that do not expose `FFMPEG` in
`scene.render.image_settings.file_format`.

```bash
blender --background --python scripts/render_storyboard.py -- \
  examples/fishing/storyboard.json --output output/fishing.mp4
```

Use `--render-mode frames --keep-frames` only for resumable or frame-level debugging. Render logs
report progress every five seconds of video.

Camera location, rotation, and orthographic scale are reset at the beginning of every scene. This
prevents repeated pan/follow actions from accumulating until the camera leaves the background.
Background planes use overscan to keep shake and modest pan actions covered.

## MMD character backend

The JSON runner supports `mmd_character` and `action_library` manifests alongside the existing
layered PNG backend. Precompiled Blender Actions are composed through NLA tracks; PMX/VMD import is
an offline asset-build step. MikuMikuRig is optional for interactive authoring and is not a runtime
dependency. See [docs/MMD.md](docs/MMD.md).
