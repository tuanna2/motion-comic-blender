"""Root-facing helpers shared by the MMD runtime and Blender-free tests."""

from __future__ import annotations

import math
from typing import Any


FACING_ACTIONS = frozenset(
    {"turn_left", "turn_right", "turn_around", "face_target", "body_turn"}
)


class FacingError(ValueError):
    """Raised when a facing action cannot resolve its intended direction."""


def shortest_yaw(current: float, desired: float) -> float:
    """Return an equivalent desired yaw reached by the shortest rotation."""
    delta = (desired - current + math.pi) % math.tau - math.pi
    return current + delta


def yaw_toward(source: Any, destination: Any, *, offset_degrees: float = 0.0) -> float:
    """Calculate yaw for an MMD model whose zero-degree forward axis is -Y."""
    dx = float(destination.location.x) - float(source.location.x)
    dy = float(destination.location.y) - float(source.location.y)
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        raise FacingError("cannot face a target at the same position")
    return math.atan2(dx, -dy) + math.radians(offset_degrees)


def _turn_delta(action_key: str, params: dict[str, Any]) -> float:
    default_degrees = 180 if action_key in {"turn_around", "body_turn"} else 90
    degrees = abs(float(params.get("degrees", default_degrees)))
    if action_key == "turn_left":
        return math.radians(degrees)
    if action_key == "turn_right":
        return -math.radians(degrees)
    direction = str(params.get("direction", "counterclockwise")).lower()
    sign = -1.0 if direction in {"clockwise", "right", "cw"} else 1.0
    return math.radians(degrees) * sign


def animate_root_facing(
    root: Any,
    action_key: str,
    start: int,
    end: int,
    params: dict[str, Any],
    *,
    registry: dict[str, Any],
) -> float:
    """Keyframe an MMD character root and return its final yaw in radians."""
    if action_key not in FACING_ACTIONS:
        raise FacingError(f"unsupported facing action {action_key!r}")
    if end <= start:
        raise FacingError("facing action end must be after start")

    initial = float(root.rotation_euler.z)
    root.keyframe_insert(data_path="rotation_euler", frame=start)

    if action_key == "face_target":
        target_id = params.get("target") or params.get("with") or params.get("listener")
        destination = registry.get(str(target_id)) if target_id is not None else None
        if destination is None:
            raise FacingError(f"face_target cannot resolve target {target_id!r}")
        absolute = yaw_toward(
            root,
            destination,
            offset_degrees=float(params.get("offset_degrees", 0.0)),
        )
        final = shortest_yaw(initial, absolute)
    else:
        final = initial + _turn_delta(action_key, params)

    hold = bool(params.get("hold", True))
    turn_frame = end if hold else max(start + 1, round(start + (end - start) * 0.55))
    root.rotation_euler.z = final
    root.keyframe_insert(data_path="rotation_euler", frame=turn_frame)
    if not hold:
        root.rotation_euler.z = initial
        root.keyframe_insert(data_path="rotation_euler", frame=end)
        return initial
    return final
