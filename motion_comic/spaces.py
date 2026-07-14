"""Create reusable layered 2D or lightweight MMD scene spaces."""

from __future__ import annotations

import math
from typing import Any

import bpy

from .assets import AssetBundle, create_flat_object, hex_color


def _plane(name: str, color: str, *, location, scale, vertical: bool = False):
    obj = create_flat_object(name, color=color, location=location, scale=scale)
    if vertical:
        obj.rotation_euler.x = math.radians(90)
    return obj


def create_scene_space(
    scene_id: str,
    environment: dict[str, Any],
    *,
    world_width: float,
    world_height: float,
    scene_mode: str,
) -> AssetBundle:
    """Build a deterministic floor, horizon, wall accents, and MMD lighting."""
    background = str(environment.get("background", "#111827"))
    floor_color = str(environment.get("floor", background))
    horizon = str(environment.get("horizon", background))
    accents = [str(value) for value in environment.get("accents", [])]
    renderables = []

    if scene_mode == "mmd_3d":
        depth = float(environment.get("depth", 14))
        renderables.append(
            _plane(
                f"{scene_id}.space.back_wall",
                background,
                location=(0, 6, world_height / 2),
                scale=(world_width * 1.5, world_height * 1.5, 1),
                vertical=True,
            )
        )
        renderables.append(
            _plane(
                f"{scene_id}.space.floor",
                floor_color,
                location=(0, 0, -0.04),
                scale=(world_width * 1.6, depth, 1),
            )
        )
        renderables.append(
            _plane(
                f"{scene_id}.space.horizon",
                horizon,
                location=(0, 5.7, world_height * 0.28),
                scale=(world_width * 1.3, world_height * 0.18, 1),
                vertical=True,
            )
        )
        for index, color in enumerate(accents[:4]):
            x = (-0.38 + index * 0.25) * world_width
            renderables.append(
                _plane(
                    f"{scene_id}.space.accent.{index}",
                    color,
                    location=(x, 5.5, world_height * (0.35 + 0.12 * (index % 2))),
                    scale=(world_width * 0.08, world_height * (0.22 + 0.05 * (index % 2)), 1),
                    vertical=True,
                )
            )

        lighting = environment.get("lighting", {})
        if isinstance(lighting, dict):
            energy = float(lighting.get("energy", 700))
            for suffix, color, location, value in (
                ("key", lighting.get("key", "#ffffff"), (-4, -4, 8), energy),
                ("fill", lighting.get("fill", "#bfdbfe"), (5, 1, 5), energy * 0.45),
            ):
                light_data = bpy.data.lights.new(f"{scene_id}.space.{suffix}", type="AREA")
                light_data.energy = value
                light_data.color = hex_color(str(color))[:3]
                light_data.shape = "DISK"
                light_data.size = 5
                light = bpy.data.objects.new(light_data.name, light_data)
                bpy.context.scene.collection.objects.link(light)
                light.location = location
                light.rotation_euler = (math.radians(30), 0, math.radians(25 if suffix == "key" else -35))
                renderables.append(light)
    else:
        renderables.append(
            _plane(
                f"{scene_id}.space.background",
                background,
                location=(0, 0, -2),
                scale=(world_width * 1.5, world_height * 1.5, 1),
            )
        )
        renderables.append(
            _plane(
                f"{scene_id}.space.floor",
                floor_color,
                location=(0, -world_height * 0.34, -1.8),
                scale=(world_width * 1.5, world_height * 0.32, 1),
            )
        )
        renderables.append(
            _plane(
                f"{scene_id}.space.horizon",
                horizon,
                location=(0, -world_height * 0.08, -1.85),
                scale=(world_width * 1.5, world_height * 0.08, 1),
            )
        )
        for index, color in enumerate(accents[:4]):
            renderables.append(
                _plane(
                    f"{scene_id}.space.accent.{index}",
                    color,
                    location=((-0.35 + index * 0.25) * world_width, world_height * 0.18, -1.75),
                    scale=(world_width * 0.07, world_height * (0.22 + 0.04 * (index % 2)), 1),
                )
            )
    return AssetBundle(root=renderables[0], renderables=renderables)
