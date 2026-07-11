"""Reusable keyframe-based motion presets."""

from __future__ import annotations

import math
from typing import Any

from .action_catalog import resolve_action
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
    arm_left = _rig_part(registry, target, "arm_left_upper")
    controllers = [
        part
        for part in (left_upper, left_lower, right_upper, right_lower, arm, arm_left)
        if part is not None
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
        if arm_left is not None:
            arm_left.rotation_euler.z = base_rotations[arm_left.name] + stride * phase * 0.55
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


def _merged(params: dict[str, Any], **defaults: Any) -> dict[str, Any]:
    result = dict(defaults)
    result.update(params)
    return result


def _pose_parts(registry, target: str) -> dict[str, Any]:
    ids = (
        "body", "head", "arm_upper", "forearm", "arm_left_upper", "forearm_left",
        "leg_left_upper", "leg_left_lower", "leg_right_upper", "leg_right_lower",
    )
    return {part_id: _rig_part(registry, target, part_id) for part_id in ids}


def _animate_pose(
    obj,
    start: int,
    end: int,
    *,
    registry,
    target: str,
    rotations: dict[str, float] | None = None,
    dx: float = 0.0,
    dy: float = 0.0,
    scale: float = 1.0,
    cycles: int = 0,
    returns: bool = True,
) -> None:
    rotations = rotations or {}
    parts = _pose_parts(registry, target)
    active = {part_id: parts.get(part_id) for part_id in rotations if parts.get(part_id) is not None}
    base_rotations = {part_id: part.rotation_euler.z for part_id, part in active.items()}
    base_location = obj.location.copy()
    base_scale = obj.scale.copy()
    samples = max(8, cycles * 8)
    for frame in _sample_frames(start, end, samples):
        progress = (frame - start) / max(1, end - start)
        if cycles:
            blend = math.sin(progress * math.tau * cycles) * math.sin(math.pi * progress)
        else:
            blend = math.sin(math.pi * progress) if returns else ease_in_out(progress)
        obj.location.x = base_location.x + dx * blend
        obj.location.y = base_location.y + dy * blend
        multiplier = 1.0 + (scale - 1.0) * blend
        obj.scale = tuple(axis * multiplier for axis in base_scale)
        _keyframe(obj, "location", frame)
        _keyframe(obj, "scale", frame)
        for part_id, part in active.items():
            part.rotation_euler.z = base_rotations[part_id] + math.radians(rotations[part_id]) * blend
            _keyframe_rotation(part, frame)


EXPRESSION_PARTS = (
    "eyes_normal", "eyes_angry", "eyes_closed", "eyes_sad", "eyes_surprised",
    "mouth_closed", "mouth_open", "blush", "tears",
)
EXPRESSION_VISIBLE = {
    "normal": {"eyes_normal", "mouth_closed"},
    "happy": {"eyes_closed", "mouth_open"},
    "angry": {"eyes_angry", "mouth_closed"},
    "sad": {"eyes_sad", "mouth_closed"},
    "scared": {"eyes_surprised", "mouth_open"},
    "surprised": {"eyes_surprised", "mouth_open"},
    "blush": {"eyes_normal", "mouth_closed", "blush"},
    "crying": {"eyes_sad", "mouth_open", "tears"},
}


def _keyframe_expression(registry, target: str, expression: str, frame: int) -> None:
    visible = EXPRESSION_VISIBLE.get(expression, EXPRESSION_VISIBLE["normal"])
    for part_id in EXPRESSION_PARTS:
        part = registry.get(f"{target}.{part_id}")
        if part is None:
            continue
        part.hide_render = part_id not in visible
        part.keyframe_insert(data_path="hide_render", frame=frame)


def locomotion_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    if action_key == "idle":
        idle(obj, start, end, _merged(params, amplitude=0.055, cycles=2))
        return
    walk_profiles = {
        "walk": (3, 24, 0.06, 2.0), "walk_slow": (2, 16, 0.035, 1.2),
        "walk_fast": (4, 30, 0.09, 3.0), "run": (5, 38, 0.13, 4.0),
        "sprint": (7, 48, 0.18, 5.5), "sneak": (3, 12, 0.025, 1.1),
        "tiptoe": (4, 10, 0.06, 1.0), "follow": (4, 24, 0.06, 2.5),
        "chase": (6, 42, 0.14, 4.5), "escape": (6, 44, 0.16, 4.8),
    }
    if action_key in walk_profiles:
        cycles, stride, bob, distance = walk_profiles[action_key]
        walk(
            obj, start, end,
            _merged(params, cycles=cycles, stride_degrees=stride, bob=bob, distance=distance),
            registry=registry, target=target,
        )
        return
    if action_key in {"enter_scene", "exit_scene"}:
        base = obj.location.copy()
        distance = float(params.get("distance", 5.0))
        if action_key == "enter_scene":
            obj.location.x = base.x + float(params.get("from_x", -distance))
            _keyframe(obj, "location", start)
            obj.location = base
            _keyframe(obj, "location", end)
        else:
            _keyframe(obj, "location", start)
            obj.location.x = base.x + float(params.get("to_x", distance))
            _keyframe(obj, "location", end)
        return
    if action_key in {"jump", "jump_back"}:
        base = obj.location.copy()
        dx = float(params.get("distance", -0.8 if action_key == "jump_back" else 0.6))
        height = float(params.get("height", 1.2 if action_key == "jump" else 0.8))
        for frame in _sample_frames(start, end, 16):
            progress = (frame - start) / max(1, end - start)
            obj.location.x = base.x + dx * ease_in_out(progress)
            obj.location.y = base.y + parabolic_arc(progress, height)
            _keyframe(obj, "location", frame)
        return
    if action_key in {"turn_left", "turn_right", "turn_around"}:
        base = obj.scale.copy()
        middle = round((start + end) / 2)
        _keyframe(obj, "scale", start)
        obj.scale.x = base.x * 0.08
        _keyframe(obj, "scale", middle)
        obj.scale.x = -base.x
        _keyframe(obj, "scale", end)
        return
    if action_key in {"approach", "move_away"}:
        base = obj.scale.copy()
        factor = float(params.get("factor", 1.3 if action_key == "approach" else 0.72))
        _keyframe(obj, "scale", start)
        obj.scale = tuple(axis * factor for axis in base)
        _keyframe(obj, "scale", end)
        return
    if action_key == "climb":
        walk(obj, start, end, _merged(params, distance=0, cycles=4, stride_degrees=32), registry=registry, target=target)
        base = obj.location.copy()
        _keyframe(obj, "location", start)
        obj.location.y = base.y + float(params.get("height", 2.5))
        _keyframe(obj, "location", end)
        return
    if action_key == "crawl":
        _animate_pose(
            obj, start, end, registry=registry, target=target, dy=-0.65,
            rotations={"body": -72, "head": 55, "arm_upper": -35, "arm_left_upper": 35},
            cycles=2,
        )
        return
    if action_key in {"step_forward", "step_back"}:
        direction = 1 if action_key == "step_forward" else -1
        walk(obj, start, end, _merged(params, distance=direction * 0.75, cycles=1, stride_degrees=18), registry=registry, target=target)
        return
    if action_key == "stop_suddenly":
        _animate_pose(obj, start, end, registry=registry, target=target, dx=0.35, rotations={"body": -18, "head": 15}, returns=True)
        return
    if action_key == "stumble":
        _animate_pose(obj, start, end, registry=registry, target=target, dx=0.7, dy=-0.15, rotations={"body": 28, "head": -20}, cycles=2)
        return
    if action_key == "fall_down":
        fall(obj, start, end, _merged(params, x=-0.6, y=-0.9, degrees=82))
        return
    if action_key == "get_up":
        base_location = obj.location.copy()
        base_rotation = obj.rotation_euler.z
        obj.location.y = base_location.y - float(params.get("y", 0.9))
        obj.rotation_euler.z = base_rotation + math.radians(float(params.get("degrees", 82)))
        _keyframe(obj, "location", start)
        _keyframe(obj, "rotation_euler", start)
        obj.location = base_location
        obj.rotation_euler.z = base_rotation
        _keyframe(obj, "location", end)
        _keyframe(obj, "rotation_euler", end)


POSE_PROFILES: dict[str, dict[str, Any]] = {
    "stand": {}, "freeze": {},
    "sit": {"dy": -0.55, "rotations": {"leg_left_upper": 70, "leg_right_upper": -70}},
    "sit_down": {"dy": -0.55, "rotations": {"leg_left_upper": 70, "leg_right_upper": -70}},
    "stand_up": {"dy": 0.45, "rotations": {"body": -8}},
    "lie_down": {"dy": -0.8, "rotations": {"body": -88, "head": 78}},
    "sleep": {"dy": -0.82, "rotations": {"body": -88, "head": 82, "arm_upper": 25}},
    "wake_up": {"dy": 0.65, "rotations": {"body": 38, "head": -25}},
    "lean_forward": {"rotations": {"body": -18, "head": 12}},
    "lean_back": {"rotations": {"body": 20, "head": -14}},
    "bend_down": {"dy": -0.25, "rotations": {"body": -52, "head": 35}},
    "kneel": {"dy": -0.48, "rotations": {"leg_left_upper": 45, "leg_left_lower": -75}},
    "crouch": {"dy": -0.45, "rotations": {"body": -15, "leg_left_upper": 32, "leg_right_upper": -32}},
    "cross_arms": {"rotations": {"arm_upper": 128, "forearm": 72, "arm_left_upper": -128, "forearm_left": -72}},
    "hands_on_hips": {"rotations": {"arm_upper": -55, "forearm": 105, "arm_left_upper": 55, "forearm_left": -105}},
    "hands_in_pockets": {"rotations": {"arm_upper": -72, "forearm": 82, "arm_left_upper": 72, "forearm_left": -82}},
    "stretch": {"dy": 0.12, "rotations": {"arm_upper": 72, "forearm": 25, "arm_left_upper": -72, "forearm_left": -25}},
    "hide": {"dy": -0.35, "rotations": {"body": 18, "head": -22}},
    "peek": {"dx": 0.25, "rotations": {"body": -12, "head": 22}},
    "look_up": {"rotations": {"head": 18}}, "look_down": {"rotations": {"head": -20}},
    "look_back": {"rotations": {"head": 34, "body": 12}},
}


def pose_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    if action_key == "shiver":
        shake(obj, start, end, _merged(params, amplitude=0.055, step_frames=2))
        return
    if action_key == "look_around":
        _animate_pose(obj, start, end, registry=registry, target=target, rotations={"head": 32}, cycles=2)
        return
    profile = POSE_PROFILES.get(action_key, {})
    _animate_pose(
        obj, start, end, registry=registry, target=target,
        rotations=profile.get("rotations", {}), dx=float(profile.get("dx", 0)),
        dy=float(profile.get("dy", 0)), scale=float(profile.get("scale", 1)),
        returns=bool(params.get("return", action_key not in {"sit", "sleep", "lie_down", "kneel"})),
    )


GESTURE_PROFILES: dict[str, dict[str, float]] = {
    "point": {"arm_upper": 18, "forearm": -12}, "beckon": {"arm_upper": 48, "forearm": 65},
    "raise_hand": {"arm_upper": 78, "forearm": 25}, "lower_hand": {"arm_upper": -35, "forearm": 5},
    "reach_out": {"arm_upper": 18, "forearm": -15}, "grab": {"arm_upper": 22, "forearm": 35},
    "hold": {"arm_upper": 72, "forearm": 88}, "release": {"arm_upper": 20, "forearm": -30},
    "give_item": {"arm_upper": 12, "forearm": -8}, "receive_item": {"arm_upper": 28, "forearm": 20},
    "take_item": {"arm_upper": 25, "forearm": 42}, "offer_item": {"arm_upper": 10, "forearm": -4},
    "throw_item": {"arm_upper": 118, "forearm": 92}, "catch_item": {"arm_upper": 45, "forearm": 75, "arm_left_upper": -45, "forearm_left": -75},
    "pick_up": {"body": -48, "head": 30, "arm_upper": -45, "forearm": 35},
    "put_down": {"body": -35, "arm_upper": -38, "forearm": 25},
    "open": {"arm_upper": 28, "forearm": 25}, "close": {"arm_upper": 22, "forearm": 52},
    "push": {"arm_upper": 8, "forearm": -18, "arm_left_upper": -8, "forearm_left": 18},
    "pull": {"body": 18, "arm_upper": 45, "forearm": 85, "arm_left_upper": -45, "forearm_left": -85},
    "drag": {"body": 22, "arm_upper": 55, "forearm": 90}, "carry": {"arm_upper": 72, "forearm": 92, "arm_left_upper": -72, "forearm_left": -92},
    "lift": {"arm_upper": 75, "forearm": 25, "arm_left_upper": -75, "forearm_left": -25},
    "drop": {"arm_upper": -28, "forearm": -18}, "touch": {"arm_upper": 25, "forearm": 5},
    "tap": {"arm_upper": 32, "forearm": 18}, "knock": {"arm_upper": 48, "forearm": 75},
    "clap": {"arm_upper": 72, "forearm": 95, "arm_left_upper": -72, "forearm_left": -95},
    "rub_hands": {"arm_upper": 68, "forearm": 88, "arm_left_upper": -68, "forearm_left": -88},
    "cover_face": {"arm_upper": 92, "forearm": 68, "arm_left_upper": -92, "forearm_left": -68},
    "cover_mouth": {"arm_upper": 72, "forearm": 82}, "scratch_head": {"arm_upper": 105, "forearm": 100},
    "facepalm": {"arm_upper": 88, "forearm": 78, "head": -12},
    "wipe_sweat": {"arm_upper": 92, "forearm": 86}, "wipe_tears": {"arm_upper": 82, "forearm": 75},
}


def gesture_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    if action_key == "wave":
        wave(obj, start, end, params, registry=registry, target=target)
        return
    rotations = GESTURE_PROFILES.get(action_key, {"arm_upper": 35, "forearm": 35})
    repeated = action_key in {"beckon", "knock", "clap", "rub_hands", "tap"}
    _animate_pose(
        obj, start, end, registry=registry, target=target, rotations=rotations,
        cycles=int(params.get("cycles", 3)) if repeated else 0,
        returns=bool(params.get("return", True)),
    )


def _other_target(registry, params: dict[str, Any]):
    other_id = params.get("with") or params.get("other")
    return (str(other_id), registry.get(str(other_id))) if other_id is not None else (None, None)


def interaction_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    other_id, other = _other_target(registry, params)
    if action_key in {"follow", "chase", "escape"}:
        locomotion_action(obj, start, end, params, registry=registry, target=target, action_key=action_key)
        return
    profile_key = {
        "handshake": "reach_out", "pat_shoulder": "tap", "hold_hand": "reach_out",
        "pull_person": "pull", "push_person": "push", "help_up": "lift", "support_person": "carry",
        "beg": "clap", "threaten": "point", "comfort": "pat_shoulder",
    }.get(action_key)
    rotations = GESTURE_PROFILES.get(profile_key or "reach_out", {})
    if action_key == "hug":
        rotations = {"arm_upper": 55, "forearm": 95, "arm_left_upper": -55, "forearm_left": -95}
    elif action_key in {"bow", "apologize"}:
        rotations = {"body": -35, "head": 22}
    elif action_key in {"confront", "block_path", "stand_in_front"}:
        rotations = {"body": -8, "arm_upper": 22, "arm_left_upper": -22}
    elif action_key == "ignore":
        rotations = {"body": 18, "head": 30}
    _animate_pose(obj, start, end, registry=registry, target=target, rotations=rotations, dx=float(params.get("distance", 0.18 if other else 0)), returns=True)
    if other is not None and action_key in {"push_person", "pull_person", "help_up"}:
        base = other.location.copy()
        _keyframe(other, "location", start)
        direction = -1 if action_key == "pull_person" else 1
        other.location.x = base.x + direction * float(params.get("other_distance", 0.65))
        other.location.y = base.y + (0.45 if action_key == "help_up" else 0)
        _keyframe(other, "location", end)


def dialogue_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    if action_key == "talk":
        talk(obj, start, end, params, registry=registry, target=target)
        return
    if action_key == "nod":
        nod(obj, start, end, params, registry=registry, target=target)
        return
    if action_key == "shake_head":
        _animate_pose(obj, start, end, registry=registry, target=target, rotations={"head": 16}, cycles=3)
        return
    expression = "normal"
    rotations: dict[str, float] = {"head": 5}
    cycles = 0
    if action_key in {"talk_happy", "agree", "answer"}:
        expression, rotations = "happy", {"head": 8, "arm_upper": 18}
    elif action_key in {"talk_angry", "shout", "yell", "argue", "command", "interrupt"}:
        expression, rotations, cycles = "angry", {"body": -10, "head": 8, "arm_upper": 45}, 2
    elif action_key in {"talk_sad", "sigh"}:
        expression, rotations = "sad", {"body": 12, "head": -14}
    elif action_key in {"talk_nervous", "mumble", "whisper"}:
        expression, rotations, cycles = "scared", {"body": 8, "head": -8}, 2
    elif action_key == "gasp":
        expression, rotations = "surprised", {"body": 12, "head": 12}
    elif action_key == "refuse":
        expression, rotations, cycles = "angry", {"head": 15}, 3
    elif action_key in {"explain", "ask"}:
        rotations = {"head": 7, "arm_upper": 28, "forearm": 20}
    _keyframe_expression(registry, target, expression, start)
    _animate_pose(obj, start, end, registry=registry, target=target, rotations=rotations, cycles=cycles)
    _keyframe_expression(registry, target, "normal", end)


EMOTION_EXPRESSION = {
    "neutral": "normal", "smile": "happy", "big_smile": "happy", "laugh": "happy",
    "laugh_hard": "happy", "excited": "happy", "proud": "happy", "relieved": "happy",
    "curious": "normal", "confident": "happy", "surprised_happy": "surprised", "love": "happy",
    "shy": "blush", "blush": "blush", "angry": "angry", "furious": "angry",
    "annoyed": "angry", "frustrated": "angry", "disgusted": "angry", "jealous": "angry",
    "suspicious": "angry", "cold_stare": "angry", "glare": "angry", "clench_fist": "angry",
    "grit_teeth": "angry", "stomp": "angry", "slam_table": "angry", "point_angrily": "angry",
    "turn_away_angry": "angry", "throw_in_anger": "angry", "sad": "sad", "cry": "crying",
    "sob": "crying", "tearful": "crying", "disappointed": "sad", "hopeless": "sad",
    "lonely": "sad", "hurt": "sad", "guilty": "sad", "regret": "sad", "lower_head": "sad",
    "hug_knees": "sad", "collapse": "sad", "walk_away_sad": "sad", "surprised": "surprised",
    "shocked": "surprised", "scared": "scared", "terrified": "scared", "panic": "scared",
    "nervous": "scared", "confused": "surprised", "hesitate": "scared", "tremble": "scared",
    "step_back_scared": "scared", "cover_ears": "scared", "shield_face": "scared",
    "hide_behind": "scared", "look_over_shoulder": "scared", "run_away_scared": "scared",
}


def emotion_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    expression = EMOTION_EXPRESSION.get(action_key, "normal")
    _keyframe_expression(registry, target, expression, start)
    if action_key in {"laugh", "laugh_hard", "excited", "surprised_happy"}:
        _animate_pose(obj, start, end, registry=registry, target=target, dy=0.16, scale=1.06, rotations={"head": 8}, cycles=3)
    elif expression == "angry":
        rotations = {"body": -10, "head": 9, "arm_upper": 32, "arm_left_upper": -32}
        if action_key in {"point_angrily", "threaten"}:
            rotations.update(GESTURE_PROFILES["point"])
        _animate_pose(obj, start, end, registry=registry, target=target, rotations=rotations, cycles=2 if action_key in {"furious", "stomp", "slam_table"} else 0)
    elif expression in {"sad", "crying"}:
        rotations = {"body": 14, "head": -18, "arm_upper": -12, "arm_left_upper": 12}
        _animate_pose(obj, start, end, registry=registry, target=target, rotations=rotations, dy=-0.18, cycles=2 if action_key == "sob" else 0)
    elif expression in {"scared", "surprised"}:
        rotations = {"body": 12, "head": 10, "arm_upper": 35, "arm_left_upper": -35}
        _animate_pose(obj, start, end, registry=registry, target=target, rotations=rotations, dx=-0.18, dy=0.1, cycles=3 if action_key in {"panic", "terrified", "tremble"} else 0)
    else:
        _animate_pose(obj, start, end, registry=registry, target=target, rotations={"head": 7}, scale=1.035, cycles=2 if action_key in {"love", "shy"} else 0)
    if bool(params.get("return_expression", True)):
        _keyframe_expression(registry, target, "normal", end)


def thinking_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    expression = "surprised" if action_key == "realize" else "normal"
    _keyframe_expression(registry, target, expression, start)
    rotations = {"head": -12, "arm_upper": 82, "forearm": 88}
    if action_key in {"search", "scan_room", "observe_secretly"}:
        rotations = {"head": 30, "body": -8}
        cycles = 2
    elif action_key in {"read", "write", "study", "check_phone"}:
        rotations = {"head": -24, "arm_upper": 52, "forearm": 80}
        cycles = 0
    elif action_key == "listen_at_door":
        rotations = {"body": -22, "head": 28, "arm_upper": 75, "forearm": 78}
        cycles = 0
    else:
        cycles = 0
    _animate_pose(obj, start, end, registry=registry, target=target, rotations=rotations, cycles=cycles)
    _keyframe_expression(registry, target, "normal", end)


def fight_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    _keyframe_expression(registry, target, "angry" if action_key not in {"get_hit", "recoil", "surrender"} else "scared", start)
    other_id, other = _other_target(registry, params)
    windup = round(start + (end - start) * 0.28)
    contact = round(start + (end - start) * 0.52)
    base = obj.location.copy()
    body = _rig_part(registry, target, "body")
    arm = _rig_part(registry, target, "arm_upper")
    forearm = _rig_part(registry, target, "forearm")
    kick_leg = _rig_part(registry, target, "leg_right_upper")
    active = [part for part in (body, arm, forearm, kick_leg) if part is not None]
    base_rotations = {part.name: part.rotation_euler.z for part in active}
    _keyframe(obj, "location", start)
    for part in active:
        _keyframe_rotation(part, start)
    if action_key in {"get_hit", "recoil", "dodge", "duck"}:
        obj.location.x = base.x - float(params.get("distance", 0.65))
        obj.location.y = base.y - (0.35 if action_key == "duck" else 0)
        if body is not None:
            body.rotation_euler.z = base_rotations[body.name] + math.radians(25)
    elif action_key in {"kick", "charge", "knock_down"}:
        obj.location.x = base.x + float(params.get("distance", 0.8))
        if kick_leg is not None:
            kick_leg.rotation_euler.z = base_rotations[kick_leg.name] + math.radians(78)
        if body is not None:
            body.rotation_euler.z = base_rotations[body.name] - math.radians(18)
    elif action_key in {"block_attack", "defend", "protect_person", "surrender"}:
        _animate_pose(obj, start, end, registry=registry, target=target, rotations={"arm_upper": 75, "forearm": 95, "arm_left_upper": -75, "forearm_left": -95}, returns=True)
        _keyframe_expression(registry, target, "normal", end)
        return
    else:
        if arm is not None:
            arm.rotation_euler.z = base_rotations[arm.name] + math.radians(105)
        if forearm is not None:
            forearm.rotation_euler.z = base_rotations[forearm.name] + math.radians(85)
        if body is not None:
            body.rotation_euler.z = base_rotations[body.name] - math.radians(12)
        for part in active:
            _keyframe_rotation(part, windup)
        obj.location.x = base.x + float(params.get("distance", 0.55))
        if arm is not None:
            arm.rotation_euler.z = base_rotations[arm.name] + math.radians(8)
        if forearm is not None:
            forearm.rotation_euler.z = base_rotations[forearm.name] - math.radians(20)
    _keyframe(obj, "location", contact)
    for part in active:
        _keyframe_rotation(part, contact)
    if other is not None and action_key not in {"dodge", "duck", "get_hit", "recoil"}:
        other_base = other.location.copy()
        other_rotation = other.rotation_euler.z
        _keyframe(other, "location", contact)
        _keyframe(other, "rotation_euler", contact)
        other.location.x = other_base.x + float(params.get("recoil", 0.75))
        other.rotation_euler.z = other_rotation + math.radians(float(params.get("recoil_degrees", 18)))
        _keyframe(other, "location", min(end, contact + max(1, (end - start) // 5)))
        _keyframe(other, "rotation_euler", min(end, contact + max(1, (end - start) // 5)))
    obj.location = base
    _keyframe(obj, "location", end)
    for part in active:
        part.rotation_euler.z = base_rotations[part.name]
        _keyframe_rotation(part, end)
    _keyframe_expression(registry, target, "normal", end)


def daily_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    mapping = {
        "eat": "cover_mouth", "drink": "cover_mouth", "cook": "rub_hands",
        "pour_drink": "offer_item", "open_door": "pull", "close_door": "push",
        "lock_door": "tap", "unlock_door": "tap", "use_phone": "hold", "make_call": "scratch_head",
        "answer_call": "scratch_head", "hang_up": "lower_hand", "type_keyboard": "rub_hands",
        "drive": "hold", "change_clothes": "cross_arms", "wash_face": "cover_face",
        "brush_teeth": "cover_mouth",
    }
    if action_key in {"sit_at_table", "get_in_vehicle", "get_out_vehicle"}:
        pose_action(obj, start, end, params, registry=registry, target=target, action_key="sit_down" if action_key != "get_out_vehicle" else "stand_up")
        return
    gesture_action(obj, start, end, params, registry=registry, target=target, action_key=mapping.get(action_key, "reach_out"))


def comic_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, target: str, action_key: str, **_
) -> None:
    if action_key in {"idle_bob", "breathing", "head_bob", "talk_bounce"}:
        if action_key == "breathing":
            _animate_pose(obj, start, end, registry=registry, target=target, scale=1.025, cycles=3)
        elif action_key == "head_bob":
            _animate_pose(obj, start, end, registry=registry, target=target, rotations={"head": 6}, cycles=3)
        else:
            idle(obj, start, end, _merged(params, amplitude=0.07, cycles=3))
        return
    if action_key == "blink":
        frames = _sample_frames(start, end, max(2, int(params.get("blinks", 2)) * 2))
        for index, frame in enumerate(frames):
            _keyframe_expression(registry, target, "happy" if index % 2 else "normal", frame)
        _keyframe_expression(registry, target, "normal", end)
        return
    if action_key in {"eye_shift", "head_turn"}:
        _animate_pose(obj, start, end, registry=registry, target=target, rotations={"head": 18}, cycles=2)
        return
    if action_key == "body_turn":
        locomotion_action(obj, start, end, params, registry=registry, target=target, action_key="turn_around")
        return
    if action_key in {"lean_in", "reaction_pop", "heartbeat"}:
        _animate_pose(obj, start, end, registry=registry, target=target, scale=1.15 if action_key == "reaction_pop" else 1.08, rotations={"body": -12}, cycles=2 if action_key == "heartbeat" else 0)
        return
    if action_key in {"lean_out", "sad_sink"}:
        _animate_pose(obj, start, end, registry=registry, target=target, scale=0.9, dy=-0.25, rotations={"body": 10})
        return
    if action_key in {"impact_shake", "fear_shake", "anger_shake"}:
        shake(obj, start, end, _merged(params, amplitude=0.1 if action_key == "impact_shake" else 0.06, step_frames=2))
        return
    if action_key == "surprise_jump":
        locomotion_action(obj, start, end, _merged(params, height=0.7, distance=-0.2), registry=registry, target=target, action_key="jump_back")
        return
    if action_key in {"walk_cycle_fake", "run_cycle_fake"}:
        locomotion_action(obj, start, end, params, registry=registry, target=target, action_key="walk" if action_key == "walk_cycle_fake" else "run")
        return
    if action_key in {"enter_slide", "exit_slide"}:
        locomotion_action(obj, start, end, params, registry=registry, target=target, action_key="enter_scene" if action_key == "enter_slide" else "exit_scene")
        return
    if action_key == "foreground_pass":
        locomotion_action(obj, start, end, _merged(params, distance=8, cycles=5), registry=registry, target=target, action_key="walk_fast")
        return
    if action_key == "depth_move":
        locomotion_action(obj, start, end, params, registry=registry, target=target, action_key="approach")


def camera_action(
    obj, start: int, end: int, params: dict[str, Any], *, registry, action_key: str, **_
) -> None:
    if action_key == "camera_static":
        _keyframe(obj, "location", start)
        _keyframe(obj, "location", end)
    elif action_key in {"camera_pan_left", "camera_pan_right", "camera_pan_up", "camera_pan_down", "camera_whip_pan"}:
        distance = float(params.get("distance", 2.0 if action_key != "camera_whip_pan" else 4.0))
        x = -distance if action_key == "camera_pan_left" else distance if action_key in {"camera_pan_right", "camera_whip_pan"} else 0
        y = distance if action_key == "camera_pan_up" else -distance if action_key == "camera_pan_down" else 0
        camera_pan(obj, start, end, {"x": x, "y": y})
    elif action_key in {"camera_zoom_in", "camera_push_in", "camera_zoom_out", "camera_pull_out"}:
        base = obj.data.ortho_scale
        factor = 0.72 if action_key in {"camera_zoom_in", "camera_push_in"} else 1.3
        camera_zoom(obj, start, end, {"from": base, "to": float(params.get("to", base * factor))})
    elif action_key in {"camera_shake", "camera_handheld"}:
        shake(obj, start, end, _merged(params, amplitude=0.15 if action_key == "camera_shake" else 0.035, step_frames=2 if action_key == "camera_shake" else 4))
    elif action_key == "camera_tilt":
        base = obj.rotation_euler.z
        _keyframe(obj, "rotation_euler", start)
        obj.rotation_euler.z = base + math.radians(float(params.get("degrees", 8)))
        _keyframe(obj, "rotation_euler", end)
    elif action_key in {"camera_follow", "camera_focus_shift"}:
        follow_id = params.get("follow") or params.get("focus")
        followed = registry.get(str(follow_id)) if follow_id is not None else None
        if followed is not None:
            _keyframe(obj, "location", start)
            obj.location.x = followed.location.x
            obj.location.y = followed.location.y
            _keyframe(obj, "location", end)
    elif action_key == "camera_parallax":
        camera_pan(obj, start, end, {"x": float(params.get("x", 1.2)), "y": float(params.get("y", 0.2))})


def effect_action(
    obj, start: int, end: int, params: dict[str, Any], *, action_key: str, registry, target: str, **_
) -> None:
    if action_key == "blush_overlay":
        _keyframe_expression(registry, target, "blush", start)
        _keyframe_expression(registry, target, "normal", end)
        return
    if action_key == "tear_stream":
        _keyframe_expression(registry, target, "crying", start)
        _keyframe_expression(registry, target, "sad", end)
        return
    if action_key in {"heartbeat", "impact_flash", "screen_flash"}:
        impact(obj, start, end, _merged(params, punch=1.12))
    elif action_key in {"shock_lines", "speed_lines", "dust_cloud"}:
        shake(obj, start, end, _merged(params, amplitude=0.08, step_frames=2))
    elif action_key in {"screen_blur", "vignette", "dark_aura", "glow_aura"}:
        impact(obj, start, end, _merged(params, punch=1.04))
    # Symbol/overlay effects are created and timed by builder.py. freeze_frame
    # and slow_motion are deterministic holds in this MVP; they do not retime audio.
    elif action_key in {"freeze_frame", "slow_motion"}:
        _keyframe(obj, "location", start)
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
    "locomotion_action": locomotion_action,
    "pose_action": pose_action,
    "gesture_action": gesture_action,
    "interaction_action": interaction_action,
    "dialogue_action": dialogue_action,
    "emotion_action": emotion_action,
    "thinking_action": thinking_action,
    "fight_action": fight_action,
    "daily_action": daily_action,
    "comic_action": comic_action,
    "camera_action": camera_action,
    "effect_action": effect_action,
}


def apply_motion(action_key: str, obj, start: int, end: int, params: dict[str, Any], **context) -> None:
    spec = resolve_action(action_key)
    PRESETS[spec.handler](
        obj,
        start,
        end,
        params,
        action_key=action_key,
        action_category=spec.category,
        **context,
    )
