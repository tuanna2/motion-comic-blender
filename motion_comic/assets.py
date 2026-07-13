"""Blender object factories for flat 2D sprites and procedural demo assets."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bpy

from .registry import AssetRegistry
from .rig import order_rig_parts, point2


def hex_color(value: str) -> tuple[float, float, float, float]:
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) == 6:
        raw += "ff"
    if len(raw) != 8:
        raise ValueError(f"invalid color {value!r}")
    return tuple(int(raw[i : i + 2], 16) / 255.0 for i in range(0, 8, 2))  # type: ignore[return-value]


def flat_material(name: str, color: str):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = hex_color(color)
    emission.inputs["Strength"].default_value = 1.0
    material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def image_material(name: str, image):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    texture = nodes.new("ShaderNodeTexImage")
    emission = nodes.new("ShaderNodeEmission")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    texture.image = image
    material.node_tree.links.new(texture.outputs["Color"], emission.inputs["Color"])
    material.node_tree.links.new(texture.outputs["Alpha"], mix.inputs[0])
    material.node_tree.links.new(transparent.outputs[0], mix.inputs[1])
    material.node_tree.links.new(emission.outputs[0], mix.inputs[2])
    material.node_tree.links.new(mix.outputs[0], output.inputs["Surface"])
    if hasattr(material, "surface_render_method"):
        material.surface_render_method = "DITHERED"
    elif hasattr(material, "blend_method"):
        material.blend_method = "BLEND"
    return material


def plane_mesh(name: str):
    mesh = bpy.data.meshes.new(name=f"{name}.mesh")
    mesh.from_pydata(
        [(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)],
        [],
        [(0, 1, 2, 3)],
    )
    uv_layer = mesh.uv_layers.new(name="UVMap")
    uv_by_vertex = ((0, 0), (1, 0), (1, 1), (0, 1))
    for loop in mesh.loops:
        uv_layer.data[loop.index].uv = uv_by_vertex[loop.vertex_index]
    mesh.update()
    return mesh


def polygon_mesh(name: str, vertices: list[tuple[float, float]]):
    mesh = bpy.data.meshes.new(name=f"{name}.mesh")
    mesh.from_pydata([(x, y, 0) for x, y in vertices], [], [tuple(range(len(vertices)))])
    mesh.update()
    return mesh


def create_flat_object(
    name: str,
    *,
    color: str,
    location=(0.0, 0.0, 0.0),
    scale=(1.0, 1.0, 1.0),
    rotation: float = 0.0,
    shape: str = "rectangle",
):
    if shape == "disc":
        vertices = [
            (math.cos(2 * math.pi * i / 48), math.sin(2 * math.pi * i / 48))
            for i in range(48)
        ]
        mesh = polygon_mesh(name, vertices)
    else:
        mesh = plane_mesh(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.scale = scale
    obj.rotation_euler[2] = math.radians(rotation)
    obj.data.materials.append(flat_material(f"{name}.material", color))
    return obj


def create_text(name: str, text: str, *, color: str, location, size: float = 1.0):
    curve = bpy.data.curves.new(type="FONT", name=f"{name}.font")
    curve.body = text
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = 0.0
    obj = bpy.data.objects.new(name, curve)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.data.materials.append(flat_material(f"{name}.material", color))
    return obj


def create_image(name: str, path: Path, *, location, width: float, height: float | None = None):
    if not path.is_file():
        raise FileNotFoundError(f"image asset not found: {path}")
    image = bpy.data.images.load(str(path), check_existing=True)
    image_width, image_height = image.size
    aspect = image_height / image_width if image_width else 1.0
    resolved_height = height if height is not None else width * aspect
    obj = bpy.data.objects.new(name, plane_mesh(name))
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.scale = (width, resolved_height, 1.0)
    obj.data.materials.append(image_material(f"{name}.material", image))
    return obj


@dataclass
class AssetBundle:
    root: Any
    renderables: list[Any] = field(default_factory=list)
    parts: dict[str, Any] = field(default_factory=dict)
    initial_visibility: dict[str, bool] = field(default_factory=dict)
    anchors: dict[str, tuple[float, float]] = field(default_factory=dict)
    anchor_parents: dict[str, Any] = field(default_factory=dict)
    backend: str = "sprite2d"
    armature: Any | None = None
    morphs: dict[str, Any] = field(default_factory=dict)
    action_set: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _parent(child, parent, location) -> None:
    child.parent = parent
    child.location = location


def create_fishing_character(name: str, element: dict[str, Any]) -> AssetBundle:
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (float(element.get("x", -3)), float(element.get("y", -1)), float(element.get("z", 2)))
    root.scale = (float(element.get("scale", 1)),) * 3

    shirt = str(element.get("color", "#2563eb"))
    skin = str(element.get("skin_color", "#f2b38a"))
    body = create_flat_object(f"{name}.body", color=shirt, scale=(0.72, 1.08, 1), shape="disc")
    head = create_flat_object(f"{name}.head", color=skin, scale=(0.64, 0.64, 1), shape="disc")
    eye_l = create_flat_object(f"{name}.eye_l", color="#111827", scale=(0.07, 0.09, 1), shape="disc")
    eye_r = create_flat_object(f"{name}.eye_r", color="#111827", scale=(0.07, 0.09, 1), shape="disc")
    mouth = create_flat_object(f"{name}.mouth", color="#7f1d1d", scale=(0.18, 0.055, 1))
    arm = create_flat_object(f"{name}.arm_front", color=skin, scale=(0.65, 0.12, 1), rotation=-18)
    rod = create_flat_object(f"{name}.rod", color="#422006", scale=(1.9, 0.035, 1), rotation=34)
    leg_l = create_flat_object(f"{name}.leg_l", color="#1e293b", scale=(0.18, 0.72, 1), rotation=5)
    leg_r = create_flat_object(f"{name}.leg_r", color="#1e293b", scale=(0.18, 0.72, 1), rotation=-5)

    _parent(body, root, (0, 0.15, 0.04))
    _parent(head, root, (0, 1.28, 0.08))
    _parent(eye_l, root, (-0.22, 1.42, 0.12))
    _parent(eye_r, root, (0.22, 1.42, 0.12))
    _parent(mouth, root, (0, 1.12, 0.13))
    _parent(arm, root, (0.68, 0.35, 0.10))
    _parent(rod, root, (1.62, 1.0, 0.09))
    _parent(leg_l, root, (-0.3, -1.35, 0.03))
    _parent(leg_r, root, (0.3, -1.35, 0.02))

    renderables = [body, head, eye_l, eye_r, mouth, arm, rod, leg_l, leg_r]
    return AssetBundle(
        root=root,
        renderables=renderables,
        parts={"mouth": mouth, "arm_front": arm, "rod": rod, "head": head},
    )


def create_fish(name: str, element: dict[str, Any]) -> AssetBundle:
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (float(element.get("x", 3)), float(element.get("y", -2)), float(element.get("z", 3)))
    root.scale = (float(element.get("scale", 1)),) * 3
    color = str(element.get("color", "#f59e0b"))
    body = create_flat_object(f"{name}.body", color=color, scale=(0.85, 0.42, 1), shape="disc")
    tail = create_flat_object(
        f"{name}.tail",
        color=color,
        location=(0, 0, 0),
        scale=(0.5, 0.5, 1),
        shape="rectangle",
        rotation=45,
    )
    eye = create_flat_object(f"{name}.eye", color="#111827", scale=(0.075, 0.075, 1), shape="disc")
    _parent(body, root, (0, 0, 0.03))
    _parent(tail, root, (-0.82, 0, 0.02))
    _parent(eye, root, (0.45, 0.13, 0.05))
    return AssetBundle(root=root, renderables=[body, tail, eye], parts={"tail": tail, "eye": eye})


def create_layered_character(
    name: str,
    element: dict[str, Any],
    asset_registry: AssetRegistry,
) -> AssetBundle:
    manifest = asset_registry.resolve(str(element["asset_ref"]), "layered_character")
    data = manifest.data
    appearance_id = str(element.get("appearance", data.get("default_appearance", "default")))
    appearance = data["appearances"].get(appearance_id)
    if not isinstance(appearance, dict):
        raise ValueError(f"unknown appearance {appearance_id!r} for {manifest.reference}")
    part_definitions = appearance.get("parts")
    if not isinstance(part_definitions, list) or not part_definitions:
        raise ValueError(f"appearance {appearance_id!r} has no parts in {manifest.path}")

    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (
        float(element.get("x", 0)),
        float(element.get("y", 0)),
        float(element.get("z", 2)),
    )
    scale = float(element.get("scale", 1.0)) * float(data.get("default_scale", 1.0))
    root.scale = (scale,) * 3

    expression_id = str(element.get("expression", data.get("default_expression", "normal")))
    expressions = data.get("expressions", {})
    expression_parts = set(data.get("expression_parts", []))
    selected_parts = expressions.get(expression_id)
    if selected_parts is None:
        raise ValueError(f"unknown expression {expression_id!r} for {manifest.reference}")
    if not isinstance(selected_parts, list):
        raise ValueError(f"expression {expression_id!r} must be an array in {manifest.path}")
    visible_expression_parts = set(selected_parts)

    renderables: list[Any] = []
    parts: dict[str, Any] = {}
    controllers: dict[str, Any] = {}
    initial_visibility: dict[str, bool] = {}
    for part in order_rig_parts(part_definitions):
        if not isinstance(part, dict) or not isinstance(part.get("id"), str):
            raise ValueError(f"invalid character part in {manifest.path}")
        part_id = str(part["id"])
        asset = part.get("asset")
        if not isinstance(asset, str):
            raise ValueError(f"part {part_id!r} is missing asset in {manifest.path}")
        parent_id = part.get("parent")
        parent_controller = root if parent_id is None else controllers[str(parent_id)]
        obj = create_image(
            f"{name}.{part_id}_sprite",
            (manifest.directory / asset).resolve(),
            location=(0, 0, 0),
            width=float(part.get("width", 1.0)),
            height=float(part["height"]) if "height" in part else None,
        )
        joint = part.get("joint")
        if joint is not None:
            joint_x, joint_y = point2(joint, f"part {part_id!r} joint")
            controller = bpy.data.objects.new(f"{name}.{part_id}_ctrl", None)
            bpy.context.scene.collection.objects.link(controller)
            controller.empty_display_type = "CIRCLE"
            controller.empty_display_size = 0.12
            controller["motion_comic_part"] = part_id
            _parent(controller, parent_controller, (joint_x, joint_y, 0))
            controller.rotation_euler.z = math.radians(float(part.get("rotation", 0)))
            sprite_offset = part.get("sprite_offset", part.get("offset", [0, 0]))
            offset_x, offset_y = point2(sprite_offset, f"part {part_id!r} sprite_offset")
            _parent(obj, controller, (offset_x, offset_y, float(part.get("z", 0))))
            controllers[part_id] = controller
            parts[part_id] = controller
            parts[f"{part_id}_sprite"] = obj
        else:
            offset_x, offset_y = point2(part.get("offset", [0, 0]), f"part {part_id!r} offset")
            _parent(obj, parent_controller, (offset_x, offset_y, float(part.get("z", 0))))
            obj.rotation_euler.z = math.radians(float(part.get("rotation", 0)))
            parts[part_id] = obj
        renderables.append(obj)
        initial_visibility[obj.name] = part_id not in expression_parts or part_id in visible_expression_parts

    anchors: dict[str, tuple[float, float]] = {}
    anchor_parents: dict[str, Any] = {}
    for anchor_id, definition in data.get("anchors", {}).items():
        anchor_name = str(anchor_id)
        if isinstance(definition, dict):
            anchors[anchor_name] = point2(definition.get("position"), f"anchor {anchor_name!r}")
            parent_id = definition.get("parent")
            if parent_id is not None:
                if str(parent_id) not in controllers:
                    raise ValueError(f"anchor {anchor_name!r} references unknown controller {parent_id!r}")
                anchor_parents[anchor_name] = controllers[str(parent_id)]
        elif isinstance(definition, list):
            anchors[anchor_name] = point2(definition, f"anchor {anchor_name!r}")

    # Generic aliases let existing motion presets work with any manifest whose
    # concrete part names follow the documented mouth/arm/rod convention.
    if "mouth_closed" in parts:
        parts["mouth"] = parts["mouth_closed"]
    return AssetBundle(
        root=root,
        renderables=renderables,
        parts=parts,
        initial_visibility=initial_visibility,
        anchors=anchors,
        anchor_parents=anchor_parents,
    )


def create_sprite_prop(
    name: str,
    element: dict[str, Any],
    asset_registry: AssetRegistry,
) -> AssetBundle:
    manifest = asset_registry.resolve(str(element["asset_ref"]), "sprite_prop")
    data = manifest.data
    obj = create_image(
        name,
        (manifest.directory / str(data["asset"])).resolve(),
        location=(
            float(element.get("x", 0)),
            float(element.get("y", 0)),
            float(element.get("z", 3)),
        ),
        width=float(element.get("width", data.get("width", 1.0))),
        height=(
            float(element["height"])
            if "height" in element
            else float(data["height"])
            if "height" in data
            else None
        ),
    )
    obj.rotation_euler.z = math.radians(float(element.get("rotation", data.get("rotation", 0))))
    scale = float(element.get("scale", 1.0)) * float(data.get("default_scale", 1.0))
    obj.scale = tuple(axis * scale for axis in obj.scale)
    anchors: dict[str, tuple[float, float]] = {}
    for anchor_id, point in data.get("anchors", {}).items():
        if isinstance(point, list) and len(point) >= 2:
            anchors[str(anchor_id)] = (float(point[0]), float(point[1]))
    return AssetBundle(root=obj, renderables=[obj], anchors=anchors)


def create_element(
    scene_id: str,
    element: dict[str, Any],
    storyboard_dir: Path,
    asset_registry: AssetRegistry | None = None,
) -> AssetBundle:
    local_id = str(element["id"])
    name = f"{scene_id}.{local_id}"
    kind = element["kind"]
    location = (
        float(element.get("x", 0)),
        float(element.get("y", 0)),
        float(element.get("z", 1)),
    )
    if kind == "character":
        if asset_registry is None:
            raise ValueError("character elements require a configured asset library")
        manifest = asset_registry.resolve(str(element["asset_ref"]))
        if manifest.asset_type == "layered_character":
            return create_layered_character(name, element, asset_registry)
        if manifest.asset_type == "mmd_character":
            from .mmd_assets import create_mmd_character

            return create_mmd_character(name, element, asset_registry, manifest=manifest)
        raise ValueError(
            f"character asset {manifest.reference} has unsupported type {manifest.asset_type!r}"
        )
    if kind == "prop":
        if asset_registry is None:
            raise ValueError("prop elements require a configured asset library")
        return create_sprite_prop(name, element, asset_registry)
    if kind == "fishing_character":
        return create_fishing_character(name, element)
    if kind == "fish":
        return create_fish(name, element)
    if kind == "image":
        obj = create_image(
            name,
            (storyboard_dir / str(element["asset"])).resolve(),
            location=location,
            width=float(element.get("width", 2.0)),
            height=float(element["height"]) if "height" in element else None,
        )
    elif kind == "text":
        obj = create_text(
            name,
            str(element.get("text", "")),
            color=str(element.get("color", "#ffffff")),
            location=location,
            size=float(element.get("size", 1.0)),
        )
    else:
        obj = create_flat_object(
            name,
            color=str(element.get("color", "#ffffff")),
            location=location,
            scale=(float(element.get("width", 2)), float(element.get("height", 2)), 1),
            rotation=float(element.get("rotation", 0)),
            shape="disc" if kind == "disc" else "rectangle",
        )
    scale = float(element.get("scale", 1.0))
    obj.scale = tuple(axis * scale for axis in obj.scale)
    return AssetBundle(root=obj, renderables=[obj])
