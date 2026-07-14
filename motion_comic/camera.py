"""Blender-independent camera conventions shared by sprite and MMD scenes."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CameraBaseline:
    location: tuple[float, float, float]
    rotation: tuple[float, float, float]
    ortho_scale: float


def camera_baseline(scene_mode: str, world_height: float) -> CameraBaseline:
    if scene_mode == "sprite_2d":
        return CameraBaseline((0.0, 0.0, 20.0), (0.0, 0.0, 0.0), world_height)
    if scene_mode == "mmd_3d":
        return CameraBaseline(
            (0.0, -18.0, world_height / 2),
            (math.radians(90), 0.0, 0.0),
            world_height,
        )
    raise ValueError(f"unsupported scene mode: {scene_mode!r}")


def subtitle_screen_y(
    scene_mode: str,
    world_height: float,
    authored_y: float | None = None,
) -> float:
    """Convert legacy subtitle coordinates to camera-local vertical position."""
    if scene_mode == "sprite_2d":
        return float(authored_y) if authored_y is not None else -world_height * 0.39
    if scene_mode == "mmd_3d":
        world_z = float(authored_y) if authored_y is not None else world_height * 0.14
        return world_z - world_height / 2
    raise ValueError(f"unsupported scene mode: {scene_mode!r}")
