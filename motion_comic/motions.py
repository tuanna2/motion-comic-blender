"""Reusable keyframe-based motion presets."""

from __future__ import annotations

import math
from typing import Any

from .easing import deterministic_shake, ease_in_out, parabolic_arc


def _keyframe(obj, data_path: str, frame: int) -> None:
    obj.keyframe_insert(data_path=data_path, frame=frame)


def _sample_frames(start: int, end: int, count: int = 12) -> list[int]:
    if end <= start:
        return [start]
    return sorted({round(start + (end - start) * i / count) for i in range(count + 1)})


def _set_linear(obj) -> None:
    if not obj.animation_data or not obj.animation_data.action:
        return
    # Blender 5 introduced layered Actions. Legacy actions expose ``fcurves``
    # directly; layered actions do not. Keyframes still render correctly when
    # this optional interpolation pass is skipped.
    fcurves = getattr(obj.animation_data.action, "fcurves", None)
    if fcurves is None:
        return
    for fcurve in fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = "LINEAR"


def enter(obj, start: int, end: int, params: dict[str, Any], **_) -> None:
    original = obj.location.copy()
    obj.location.x = original.x + float(params.get("from_x", -5.0))
    obj.location.y = original.y + float(params.get("from_y", 0.0))
    _keyframe(obj, "location", start)
    obj.location = original
    _keyframe(obj, "location", end)


def idle(obj, start: int, end: int, params: dict[str, Any], **_) -> None:
    base = obj.location.copy()
    amplitude = float(params.get("amplitude", 0.08))
    cycles = max(1, int(params.get("cycles", 2)))
    for index, frame in enumerate(_sample_frames(start, end, cycles * 4)):
        progress = index / max(1, cycles * 4)
        obj.location.y = base.y + math.sin(progress * math.tau * cycles) * amplitude
        _keyframe(obj, "location", frame)
    obj.location = base
    _set_linear(obj)


def talk(obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, **_) -> None:
    mouth_closed = registry.get(f"{target}.mouth_closed")
    mouth_open = registry.get(f"{target}.mouth_open")
    pulses = max(2, int(params.get("pulses", max(2, (end - start) // 4))))
    if mouth_closed is not None and mouth_open is not None:
        frames = _sample_frames(start, end, pulses)
        for index, frame in enumerate(frames):
            is_open = index % 2 == 1
            mouth_closed.hide_render = is_open
            mouth_closed.keyframe_insert(data_path="hide_render", frame=frame)
            mouth_open.hide_render = not is_open
            mouth_open.keyframe_insert(data_path="hide_render", frame=frame)
        mouth_closed.hide_render = False
        mouth_closed.keyframe_insert(data_path="hide_render", frame=end)
        mouth_open.hide_render = True
        mouth_open.keyframe_insert(data_path="hide_render", frame=end)
        return

    mouth = registry.get(f"{target}.mouth", obj)
    base_scale = mouth.scale.copy()
    for index, frame in enumerate(_sample_frames(start, end, pulses)):
        mouth.scale.y = base_scale.y * (1.0 if index % 2 == 0 else float(params.get("open", 2.8)))
        _keyframe(mouth, "scale", frame)
    mouth.scale = base_scale
    _keyframe(mouth, "scale", end)


def pull_rod(obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, **_) -> None:
    base_rotation = obj.rotation_euler.z
    base_location = obj.location.copy()
    rod = registry.get(f"{target}.rod")
    rod_rotation = rod.rotation_euler.z if rod else 0.0
    middle = round(start + (end - start) * 0.55)
    obj.rotation_euler.z = base_rotation + math.radians(float(params.get("prepare_degrees", -8)))
    _keyframe(obj, "rotation_euler", start)
    obj.rotation_euler.z = base_rotation + math.radians(float(params.get("pull_degrees", 22)))
    obj.location.x = base_location.x - float(params.get("pull_back", 0.45))
    _keyframe(obj, "rotation_euler", middle)
    _keyframe(obj, "location", middle)
    if rod:
        rod.rotation_euler.z = rod_rotation + math.radians(float(params.get("rod_degrees", 32)))
        _keyframe(rod, "rotation_euler", middle)
    obj.rotation_euler.z = base_rotation
    obj.location = base_location
    _keyframe(obj, "rotation_euler", end)
    _keyframe(obj, "location", end)
    if rod:
        rod.rotation_euler.z = rod_rotation
        _keyframe(rod, "rotation_euler", end)


def fish_jump(obj, start: int, end: int, params: dict[str, Any], **_) -> None:
    base = obj.location.copy()
    dx = float(params.get("distance", -4.0))
    height = float(params.get("height", 3.2))
    turns = float(params.get("turns", 0.7))
    for frame in _sample_frames(start, end, 18):
        progress = (frame - start) / max(1, end - start)
        smooth = ease_in_out(progress)
        obj.location.x = base.x + dx * smooth
        obj.location.y = base.y + parabolic_arc(progress, height)
        obj.rotation_euler.z = math.tau * turns * progress
        _keyframe(obj, "location", frame)
        _keyframe(obj, "rotation_euler", frame)
    _set_linear(obj)


def shake(obj, start: int, end: int, params: dict[str, Any], **_) -> None:
    base = obj.location.copy()
    amplitude = float(params.get("amplitude", 0.12))
    step = max(1, int(params.get("step_frames", 2)))
    for index, frame in enumerate(range(start, end + 1, step)):
        dx, dy = deterministic_shake(index, amplitude)
        obj.location.x = base.x + dx
        obj.location.y = base.y + dy
        _keyframe(obj, "location", frame)
    obj.location = base
    _keyframe(obj, "location", end)
    _set_linear(obj)


def impact(obj, start: int, end: int, params: dict[str, Any], **_) -> None:
    base = obj.scale.copy()
    frames = _sample_frames(start, end, 3)
    multipliers = (1.0, float(params.get("punch", 1.3)), 0.92, 1.0)
    for frame, multiplier in zip(frames, multipliers):
        obj.scale = tuple(axis * multiplier for axis in base)
        _keyframe(obj, "scale", frame)
    obj.scale = base


def fall(obj, start: int, end: int, params: dict[str, Any], **_) -> None:
    base_location = obj.location.copy()
    base_rotation = obj.rotation_euler.z
    _keyframe(obj, "location", start)
    _keyframe(obj, "rotation_euler", start)
    obj.location.x += float(params.get("x", -1.0))
    obj.location.y += float(params.get("y", -1.2))
    obj.rotation_euler.z = base_rotation + math.radians(float(params.get("degrees", 78)))
    _keyframe(obj, "location", end)
    _keyframe(obj, "rotation_euler", end)


def camera_zoom(obj, start: int, end: int, params: dict[str, Any], **_) -> None:
    base = obj.data.ortho_scale
    obj.data.ortho_scale = float(params.get("from", base))
    obj.data.keyframe_insert(data_path="ortho_scale", frame=start)
    obj.data.ortho_scale = float(params.get("to", base * 0.8))
    obj.data.keyframe_insert(data_path="ortho_scale", frame=end)


def camera_pan(obj, start: int, end: int, params: dict[str, Any], **_) -> None:
    base = obj.location.copy()
    _keyframe(obj, "location", start)
    obj.location.x = base.x + float(params.get("x", 0.0))
    obj.location.y = base.y + float(params.get("y", 0.0))
    _keyframe(obj, "location", end)


PRESETS = {
    "enter": enter,
    "idle": idle,
    "talk": talk,
    "pull_rod": pull_rod,
    "fish_jump": fish_jump,
    "shake": shake,
    "impact": impact,
    "fall": fall,
    "camera_zoom": camera_zoom,
    "camera_pan": camera_pan,
}


def apply_motion(preset: str, obj, start: int, end: int, params: dict[str, Any], **context) -> None:
    PRESETS[preset](obj, start, end, params, **context)
