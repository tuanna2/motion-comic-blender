"""Blender object factories for flat 2D sprites and procedural demo assets."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bpy


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


def create_element(scene_id: str, element: dict[str, Any], asset_root: Path) -> AssetBundle:
    local_id = str(element["id"])
    name = f"{scene_id}.{local_id}"
    kind = element["kind"]
    location = (
        float(element.get("x", 0)),
        float(element.get("y", 0)),
        float(element.get("z", 1)),
    )
    if kind == "fishing_character":
        return create_fishing_character(name, element)
    if kind == "fish":
        return create_fish(name, element)
    if kind == "image":
        obj = create_image(
            name,
            (asset_root / str(element["asset"])).resolve(),
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

