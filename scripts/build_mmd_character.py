#!/usr/bin/env python3
"""Compile one PMX character into the runtime-only .blend format.

Run through Blender, not the system Python:
blender --background --python scripts/build_mmd_character.py -- --manifest path/manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile PMX with Blender MMD Tools")
    parser.add_argument("--manifest", required=True, help="mmd_character manifest.json")
    parser.add_argument("--keep-physics", action="store_true")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])


def require_mmd_tools() -> None:
    if not hasattr(bpy.ops, "mmd_tools") or not hasattr(bpy.ops.mmd_tools, "import_model"):
        raise RuntimeError(
            "MMD Tools is not enabled. Install MMD-Blender/blender_mmd_tools v4 and enable it."
        )


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("type") != "mmd_character":
        raise ValueError("manifest type must be mmd_character")
    source = data.get("source")
    if not isinstance(source, str) or not source:
        raise ValueError("mmd_character manifest needs a source PMX or PMD for compilation")
    model_path = (manifest_path.parent / source).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(
            f"MMD model source not found: {model_path}. "
            "For the learning demo run scripts/download_learning_mmd_model.py first."
        )
    output_path = (manifest_path.parent / str(data["blend"])).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    require_mmd_tools()
    reset_scene()
    before = set(bpy.data.objects)
    bpy.ops.mmd_tools.import_model(filepath=str(model_path), scale=float(data.get("import_scale", 0.08)))
    imported = [obj for obj in bpy.data.objects if obj not in before]
    armatures = [obj for obj in imported if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("MMD Tools imported no armature")
    armature = armatures[0]
    armature.name = str(data["armature"])

    runtime_collection = bpy.data.collections.new(str(data["collection"]))
    bpy.context.scene.collection.children.link(runtime_collection)
    imported_set = set(imported)
    for obj in imported:
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        runtime_collection.objects.link(obj)
        if not args.keep_physics and bool(data.get("disable_physics", True)):
            rigid_body = getattr(obj, "rigid_body", None)
            if rigid_body is not None:
                rigid_body.kinematic = True

    root_name = data.get("root_object")
    if isinstance(root_name, str) and root_name:
        roots = [obj for obj in imported if obj.parent not in imported_set]
        if roots:
            roots[0].name = root_name

    bpy.ops.wm.save_as_mainfile(filepath=str(output_path), compress=True)
    print(f"Compiled MMD character: {output_path}")
    print(f"Armature: {armature.name}; objects: {len(imported)}; physics: {'on' if args.keep_physics else 'off'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
