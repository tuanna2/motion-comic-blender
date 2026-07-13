# MMD Tools, MikuMikuRig, and JSON/NLA runtime

The MMD integration keeps authoring and production rendering separate:

```text
PMX + VMD -> MMD Tools -> compiled .blend -> storyboard JSON -> NLA -> MP4
                      optional MikuMikuRig ^
```

MMD Tools is required only while compiling PMX/VMD assets. MikuMikuRig is optional and is
intended for interactive Rigify-based cleanup and authoring. Production rendering does not call
either add-on; it appends collections and Actions from precompiled `.blend` files.

The add-ons are external GPL dependencies and are not vendored into this MIT repository.

## 1. Install authoring add-ons

Install a Blender 4.2-5.1 compatible MMD Tools v4 release from
`MMD-Blender/blender_mmd_tools`. Optionally install `XiaoFFGe/MikuMikuRig` when motions need
manual controller cleanup. Enable the add-ons in the same Blender installation used for builds.

Check the environment:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python scripts/check_mmd_environment.py
```

## 2. Prepare files without committing licensed model data

For a learning-only demo, download the pinned Miku v2 PMD model directly from the Three.js
upstream mirror after reviewing its bundled rules and Piapro's non-commercial terms:

```bash
python3 scripts/download_learning_mmd_model.py --accept-noncommercial-license
```

This downloads the model, eye texture, upstream asset notice, and original Japanese readme into
the ignored `assets/characters/mmd_demo/source/` directory. The model is not copied into this Git
repository. The sample manifests already point to `character.pmd`; MMD Tools supports both PMD
and PMX.

Use the sample manifests as templates:

```text
assets/characters/mmd_demo/
  manifest.json
  source/character.pmx
  compiled/character.blend

assets/actions/humanoid_mmd/
  manifest.json
  source/reference.pmx
  source/idle.vmd
  source/walk.vmd
  ...
  compiled/humanoid_actions.blend
```

The repository intentionally contains no PMX, model textures, or compiled model `.blend` files.
Confirm the model, texture, and any additional motion licenses before production use.

The repository now includes a small redistributable sample VMD set under
`assets/actions/humanoid_mmd/source/`. Its provenance and exact filename mapping are recorded in
`assets/actions/humanoid_mmd/SOURCE.md`. A PMX reference model is still not bundled.

## 3. Compile once

```bash
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender

"$BLENDER" --background --python scripts/build_mmd_character.py -- \
  --manifest assets/characters/mmd_demo/manifest.json

"$BLENDER" --background --python scripts/build_mmd_actions.py -- \
  --manifest assets/actions/humanoid_mmd/manifest.json
```

Physics is disabled by default for deterministic headless rendering. Pass `--keep-physics` only
while compiling a character if the production environment deliberately supports it.

## 4. Render through the same JSON runner

The AI-facing element remains unchanged. The manifest selects the backend:

```json
{"id":"hero","kind":"character","asset_ref":"char_mmd_demo@1","x":-2,"y":0,"z":0,"scale":1}
```

Select the MMD coordinate system:

```json
"settings": {"scene_mode":"mmd_3d"}
```

In `mmd_3d`, X is horizontal, Y is depth, and Z is height. The camera is reset at every scene
boundary. Semantic motions create NLA strips using the character's `action_set`. Base, upper,
face, and additive tracks may overlap, so `walk` and `wave` can run together. Unmapped semantic
actions follow manifest fallback rules.

```bash
"$BLENDER" --background --python scripts/render_storyboard.py -- \
  examples/mmd/storyboard.json --output output/mmd-demo.mp4
```

Direct MP4 is the default: Blender renders one temporary PNG, pipes it to FFmpeg, then overwrites
it for the next frame. It does not retain thousands of frame files. For resumable/debug output:

```bash
"$BLENDER" --background --python scripts/render_storyboard.py -- \
  examples/mmd/storyboard.json --output output/mmd-demo.mp4 \
  --render-mode frames --keep-frames
```

## 5. Lip-sync

Map `mouth_open` in the character manifest to the PMX shape-key name, commonly `あ`. Existing
Edge-TTS word boundaries then keyframe that morph from 0 to 1. This MVP is mouth-open/closed
lip-sync; phoneme-specific A/I/U/E/O morphs can be added later.
