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


def _rig_part(registry, target: str, part_id: str):
    return registry.get(f"{target}.{part_id}")


def _keyframe_rotation(obj, frame: int) -> None:
    if obj is not None:
        _keyframe(obj, "rotation_euler", frame)


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
    base_location = obj.location.copy()
    body = _rig_part(registry, target, "body")
    if body is None:
        body = obj
    head = _rig_part(registry, target, "head")
    arm = _rig_part(registry, target, "arm_upper")
    if arm is None:
        arm = _rig_part(registry, target, "arm_front")
    forearm = _rig_part(registry, target, "forearm")
    rod = _rig_part(registry, target, "rod")
    controllers = [part for part in (body, head, arm, forearm, rod) if part is not None]
    base_rotations = {part.name: part.rotation_euler.z for part in controllers}
    middle = round(start + (end - start) * 0.55)

    obj.location = base_location
    _keyframe(obj, "location", start)
    body.rotation_euler.z = base_rotations[body.name] + math.radians(
        float(params.get("prepare_degrees", -8))
    )
    for part in controllers:
        _keyframe_rotation(part, start)

    pull_degrees = float(params.get("pull_degrees", 22))
    body.rotation_euler.z = base_rotations[body.name] + math.radians(pull_degrees)
    obj.location.x = base_location.x - float(params.get("pull_back", 0.45))
    _keyframe(obj, "location", middle)
    if head is not None:
        head.rotation_euler.z = base_rotations[head.name] - math.radians(pull_degrees * 0.45)
    if arm is not None:
        arm.rotation_euler.z = base_rotations[arm.name] + math.radians(
            float(params.get("shoulder_degrees", 34))
        )
    if forearm is not None:
        forearm.rotation_euler.z = base_rotations[forearm.name] + math.radians(
            float(params.get("elbow_degrees", 58))
        )
    if rod is not None:
        rod.rotation_euler.z = base_rotations[rod.name] + math.radians(
            float(params.get("rod_degrees", 32))
        )
    for part in controllers:
        _keyframe_rotation(part, middle)

    obj.location = base_location
    _keyframe(obj, "location", end)
    for part in controllers:
        part.rotation_euler.z = base_rotations[part.name]
        _keyframe_rotation(part, end)


def walk(obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, **_) -> None:
    """Move the root while swinging hierarchical arm and leg controllers."""
    base_location = obj.location.copy()
    from_x = params.get("from_x")
    if from_x is not None:
        start_x = base_location.x + float(from_x)
        end_x = base_location.x
    else:
        start_x = base_location.x
        end_x = base_location.x + float(params.get("distance", 2.0))
    cycles = max(1, int(params.get("cycles", 3)))
    stride = math.radians(float(params.get("stride_degrees", 24)))
    knee_bend = math.radians(float(params.get("knee_degrees", 18)))
    bob = float(params.get("bob", 0.06))

    left_upper = _rig_part(registry, target, "leg_left_upper")
    left_lower = _rig_part(registry, target, "leg_left_lower")
    right_upper = _rig_part(registry, target, "leg_right_upper")
    right_lower = _rig_part(registry, target, "leg_right_lower")
    arm = _rig_part(registry, target, "arm_upper")
    controllers = [
        part for part in (left_upper, left_lower, right_upper, right_lower, arm) if part is not None
    ]
    base_rotations = {part.name: part.rotation_euler.z for part in controllers}

    sample_count = cycles * 8
    for frame in _sample_frames(start, end, sample_count):
        progress = (frame - start) / max(1, end - start)
        phase = math.sin(progress * math.tau * cycles)
        obj.location.x = start_x + (end_x - start_x) * ease_in_out(progress)
        obj.location.y = base_location.y + abs(phase) * bob
        _keyframe(obj, "location", frame)
        if left_upper is not None:
            left_upper.rotation_euler.z = base_rotations[left_upper.name] + stride * phase
        if right_upper is not None:
            right_upper.rotation_euler.z = base_rotations[right_upper.name] - stride * phase
        if left_lower is not None:
            left_lower.rotation_euler.z = base_rotations[left_lower.name] + knee_bend * max(0.0, -phase)
        if right_lower is not None:
            right_lower.rotation_euler.z = base_rotations[right_lower.name] + knee_bend * max(0.0, phase)
        if arm is not None:
            arm.rotation_euler.z = base_rotations[arm.name] - stride * phase * 0.55
        for part in controllers:
            _keyframe_rotation(part, frame)

    obj.location.x = end_x
    obj.location.y = base_location.y
    for part in controllers:
        part.rotation_euler.z = base_rotations[part.name]
    _set_linear(obj)
    for part in controllers:
        _set_linear(part)


def wave(obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, **_) -> None:
    """Raise the arm at the shoulder and wave from the elbow."""
    arm = _rig_part(registry, target, "arm_upper")
    forearm = _rig_part(registry, target, "forearm")
    if arm is None and forearm is None:
        return
    cycles = max(1, int(params.get("cycles", 3)))
    lift = math.radians(float(params.get("lift_degrees", 58)))
    bend = math.radians(float(params.get("bend_degrees", 45)))
    amplitude = math.radians(float(params.get("amplitude_degrees", 22)))
    base_arm = arm.rotation_euler.z if arm is not None else 0.0
    base_forearm = forearm.rotation_euler.z if forearm is not None else 0.0
    sample_count = cycles * 8
    for frame in _sample_frames(start, end, sample_count):
        progress = (frame - start) / max(1, end - start)
        envelope = math.sin(math.pi * progress)
        oscillation = math.sin(progress * math.tau * cycles)
        if arm is not None:
            arm.rotation_euler.z = base_arm + lift * envelope
            _keyframe_rotation(arm, frame)
        if forearm is not None:
            forearm.rotation_euler.z = base_forearm + (bend + amplitude * oscillation) * envelope
            _keyframe_rotation(forearm, frame)


def look(obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, **_) -> None:
    """Turn the head controller, optionally returning to the neutral pose."""
    head = _rig_part(registry, target, "head")
    if head is None:
        return
    base = head.rotation_euler.z
    angle = math.radians(float(params.get("degrees", 18)))
    returns = bool(params.get("return", True))
    for frame in _sample_frames(start, end, 12):
        progress = (frame - start) / max(1, end - start)
        blend = math.sin(math.pi * progress) if returns else ease_in_out(progress)
        head.rotation_euler.z = base + angle * blend
        _keyframe_rotation(head, frame)


def nod(obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, **_) -> None:
    """Animate a damped head nod around the neck joint."""
    head = _rig_part(registry, target, "head")
    if head is None:
        return
    base = head.rotation_euler.z
    cycles = max(1, int(params.get("cycles", 2)))
    amplitude = math.radians(float(params.get("degrees", 10)))
    sample_count = cycles * 8
    for frame in _sample_frames(start, end, sample_count):
        progress = (frame - start) / max(1, end - start)
        envelope = math.sin(math.pi * progress)
        head.rotation_euler.z = base + math.sin(progress * math.tau * cycles) * amplitude * envelope
        _keyframe_rotation(head, frame)


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
    "walk": walk,
    "wave": wave,
    "look": look,
    "nod": nod,
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
