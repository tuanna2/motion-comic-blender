"""Append precompiled MMD character collections for deterministic runtime rendering."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import bpy

from .assets import AssetBundle, hex_color
from .cache import cached_artifact
from .registry import AssetManifest, AssetRegistry


class MMDAssetError(ValueError):
    """Raised when a compiled MMD character cannot be loaded safely."""


def _mix_color(base, tint, strength: float):
    return tuple(base[index] * (1.0 - strength) + tint[index] * strength for index in range(3))


def _apply_material_tint(objects, value: str | None, strength: float) -> None:
    """Create per-character material copies and apply a subtle identity tint."""
    if not value or strength <= 0:
        return
    tint = hex_color(value)
    strength = min(1.0, max(0.0, strength))
    for obj in objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            material = slot.material
            if material is None:
                continue
            material = material.copy()
            slot.material = material
            diffuse = tuple(material.diffuse_color)
            mixed = _mix_color(diffuse, tint, strength)
            material.diffuse_color = (*mixed, diffuse[3])
            if not material.use_nodes or material.node_tree is None:
                continue
            for node in material.node_tree.nodes:
                if node.type != "BSDF_PRINCIPLED":
                    continue
                base_input = node.inputs.get("Base Color")
                if base_input is None:
                    continue
                base = tuple(base_input.default_value)
                mixed = _mix_color(base, tint, strength)
                base_input.default_value = (*mixed, base[3])


def _matches_blender_name(actual: str, requested: str) -> bool:
    return actual == requested or actual.startswith(f"{requested}.")


def _find_object(objects, requested: str, *, object_type: str | None = None):
    matches = [
        obj
        for obj in objects
        if _matches_blender_name(obj.name, requested)
        and (object_type is None or obj.type == object_type)
    ]
    if not matches:
        suffix = f" with type {object_type}" if object_type else ""
        raise MMDAssetError(f"object {requested!r}{suffix} was not found in compiled collection")
    return matches[0]


def _append_collection(blend_path: Path, collection_name: str):
    if not blend_path.is_file():
        raise MMDAssetError(f"compiled MMD blend not found: {blend_path}")
    runtime_blend = cached_artifact(blend_path)
    with bpy.data.libraries.load(str(runtime_blend), link=False) as (source, target):
        if collection_name not in source.collections:
            available = ", ".join(source.collections) or "none"
            raise MMDAssetError(
                f"collection {collection_name!r} is missing from {runtime_blend}; available: {available}"
            )
        target.collections = [collection_name]
    collection = target.collections[0]
    if collection is None:
        raise MMDAssetError(f"failed to append collection {collection_name!r} from {runtime_blend}")
    bpy.context.scene.collection.children.link(collection)
    return collection


def _collect_shape_keys(objects, morph_definitions: dict[str, Any]) -> dict[str, list[Any]]:
    resolved: dict[str, list[Any]] = {}
    for semantic_name, raw_names in morph_definitions.items():
        if raw_names is None:
            continue
        names = [raw_names] if isinstance(raw_names, str) else raw_names
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise MMDAssetError(f"morph {semantic_name!r} must be a string, array, or null")
        blocks: list[Any] = []
        for obj in objects:
            shape_keys = getattr(getattr(obj, "data", None), "shape_keys", None)
            if shape_keys is None:
                continue
            for morph_name in names:
                block = shape_keys.key_blocks.get(morph_name)
                if block is not None:
                    blocks.append(block)
        if not blocks:
            raise MMDAssetError(
                f"morph {semantic_name!r} did not match any shape key: {', '.join(names)}"
            )
        resolved[str(semantic_name)] = blocks
    return resolved


def create_mmd_character(
    name: str,
    element: dict[str, Any],
    asset_registry: AssetRegistry,
    *,
    manifest: AssetManifest | None = None,
) -> AssetBundle:
    """Append a compiled character; importing PMX/VMD is intentionally not a runtime step."""
    manifest = manifest or asset_registry.resolve(str(element["asset_ref"]), "mmd_character")
    data = manifest.data
    blend_path = (manifest.directory / str(data["blend"])).resolve()
    collection = _append_collection(blend_path, str(data["collection"]))
    objects = list(collection.all_objects)
    armature = _find_object(objects, str(data["armature"]), object_type="ARMATURE")

    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (
        float(element.get("x", 0)),
        float(element.get("y", 0)),
        float(element.get("z", 0)),
    )
    scale = float(element.get("scale", 1.0)) * float(data.get("scale", 1.0))
    root.scale = (scale, scale, scale)
    root.rotation_euler.z = math.radians(float(element.get("rotation", 0)))

    requested_root = data.get("root_object")
    if isinstance(requested_root, str) and requested_root:
        candidates = [_find_object(objects, requested_root)]
    else:
        candidates = [obj for obj in objects if obj.parent is None]
    for obj in candidates:
        obj.parent = root

    if bool(data.get("disable_physics", True)):
        for obj in objects:
            rigid_body = getattr(obj, "rigid_body", None)
            if rigid_body is not None:
                rigid_body.kinematic = True

    _apply_material_tint(
        objects,
        str(data["material_tint"]) if data.get("material_tint") else None,
        float(data.get("material_tint_strength", 0.0)),
    )

    morphs = _collect_shape_keys(objects, dict(data.get("morphs", {})))
    # MMD Tools stores collision/physics helpers as hidden mesh objects in the
    # same collection. They must stay hidden; treating them as scene
    # renderables makes _show_during() reveal them as large black geometry.
    renderables = [
        obj
        for obj in objects
        if obj.type in {"MESH", "CURVE", "SURFACE"} and not obj.hide_render
    ]
    return AssetBundle(
        root=root,
        renderables=renderables,
        backend="mmd",
        armature=armature,
        morphs=morphs,
        action_set=str(data["action_set"]),
        metadata={"manifest": manifest, "collection": collection},
    )
