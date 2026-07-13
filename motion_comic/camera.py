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
