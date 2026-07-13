#!/usr/bin/env python3
"""Import VMD files on a reference PMX skeleton and save reusable Blender Actions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.mmd_environment import ensure_mmd_tools, mmd_tools_error  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile VMD files into an Action library")
    parser.add_argument("--manifest", required=True, help="action_library manifest.json")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])


def require_mmd_tools() -> None:
    environment = ensure_mmd_tools()
    if not environment.ready:
        raise RuntimeError(mmd_tools_error(environment))
    if environment.enabled_module:
        print(f"Enabled MMD Tools module: {environment.enabled_module}")


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("type") != "action_library":
        raise ValueError("manifest type must be action_library")
    reference_model = data.get("reference_model")
    if not isinstance(reference_model, str) or not reference_model:
        raise ValueError("action_library manifest needs reference_model PMX or PMD")
    model_path = (manifest_path.parent / reference_model).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(
            f"reference MMD model not found: {model_path}. "
            "For the learning demo run scripts/download_learning_mmd_model.py first."
        )
    output_path = (manifest_path.parent / str(data["blend"])).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    require_mmd_tools()

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mmd_tools.import_model(filepath=str(model_path), scale=float(data.get("import_scale", 0.08)))
    armature = next((obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"), None)
    if armature is None:
        raise RuntimeError("reference PMX imported no armature")

    compiled: set[str] = set()
    for semantic_key, definition in data["actions"].items():
        if not isinstance(definition, dict) or "source" not in definition:
            continue
        source_path = (manifest_path.parent / str(definition["source"])).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"VMD source for {semantic_key!r} not found: {source_path}")
        bpy.ops.object.select_all(action="DESELECT")
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.mmd_tools.import_vmd(
            filepath=str(source_path),
            scale=float(data.get("motion_scale", data.get("import_scale", 0.08))),
        )
        action = getattr(armature.animation_data, "action", None)
        if action is None:
            raise RuntimeError(f"VMD {source_path} created no armature Action")
        action.name = str(definition["action"])
        action.use_fake_user = True
        compiled.add(action.name)
        armature.animation_data.action = None

    if not compiled:
        raise RuntimeError("no action entry declared a source VMD")
    # Runtime .blend only needs Actions; remove the authoring skeleton and PMX meshes.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path), compress=True)
    print(f"Compiled {len(compiled)} MMD actions: {output_path}")
    for name in sorted(compiled):
        print(f"- {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
