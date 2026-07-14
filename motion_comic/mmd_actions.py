"""Resolve semantic actions and compose precompiled Blender Actions through NLA."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .registry import AssetManifest, AssetRegistry
from .cache import cached_artifact

if TYPE_CHECKING:
    from .assets import AssetBundle


class MMDActionError(ValueError):
    """Raised when an MMD action mapping or compiled Action is invalid."""


@dataclass(frozen=True)
class MMDActionSpec:
    semantic_key: str
    resolved_key: str
    blender_action: str
    track: str
    loop: bool
    root_motion: bool
    blend_in: int
    blend_out: int
    blend_type: str


def resolve_mmd_action(manifest: AssetManifest, semantic_key: str) -> MMDActionSpec:
    if manifest.asset_type != "action_library":
        raise MMDActionError(f"expected action_library, got {manifest.asset_type!r}")
    actions = manifest.data["actions"]
    fallbacks = manifest.data.get("fallbacks", {})
    current = semantic_key
    visited: set[str] = set()
    while True:
        if current in visited:
            chain = " -> ".join([*visited, current])
            raise MMDActionError(f"cyclic MMD action fallback: {chain}")
        visited.add(current)
        definition = actions.get(current)
        if definition is None:
            current = fallbacks.get(current) or manifest.data.get("default_fallback")
            if not isinstance(current, str) or not current:
                raise MMDActionError(
                    f"action {semantic_key!r} is not mapped by {manifest.reference}"
                )
            continue
        fallback = definition.get("fallback")
        if isinstance(fallback, str) and fallback:
            current = fallback
            continue
        action_name = definition.get("action")
        if not isinstance(action_name, str) or not action_name:
            raise MMDActionError(f"action mapping {current!r} has no Blender Action")
        return MMDActionSpec(
            semantic_key=semantic_key,
            resolved_key=current,
            blender_action=action_name,
            track=str(definition.get("track", "base")),
            loop=bool(definition.get("loop", False)),
            root_motion=bool(definition.get("root_motion", False)),
            blend_in=max(0, int(definition.get("blend_in", 4))),
            blend_out=max(0, int(definition.get("blend_out", 4))),
            blend_type=str(definition.get("blend_type", "REPLACE")).upper(),
        )


def _load_blender_action(manifest: AssetManifest, action_name: str):
    import bpy

    existing = bpy.data.actions.get(action_name)
    if existing is not None:
        return existing
    blend_path = (manifest.directory / str(manifest.data["blend"])).resolve()
    if not blend_path.is_file():
        raise MMDActionError(f"compiled action blend not found: {blend_path}")
    runtime_blend = cached_artifact(blend_path)
    with bpy.data.libraries.load(str(runtime_blend), link=False) as (source, target):
        if action_name not in source.actions:
            available = ", ".join(source.actions) or "none"
            raise MMDActionError(
                f"Blender Action {action_name!r} is missing from {blend_path}; available: {available}"
            )
        target.actions = [action_name]
    action = target.actions[0]
    if action is None:
        raise MMDActionError(f"failed to append Blender Action {action_name!r}")
    return action


def _available_track(animation_data, name: str, start: int, end: int):
    prefix = f"MC.{name}"
    for track in animation_data.nla_tracks:
        if not track.name.startswith(prefix):
            continue
        if all(end <= strip.frame_start or start >= strip.frame_end for strip in track.strips):
            return track
    track = animation_data.nla_tracks.new()
    track.name = f"{prefix}.{len(animation_data.nla_tracks):02d}"
    return track


def _keyframe_external_root_motion(
    bundle: AssetBundle,
    start: int,
    end: int,
    params: dict[str, Any],
    spec: MMDActionSpec,
) -> None:
    if spec.root_motion:
        return
    has_motion = any(key in params for key in ("distance", "from_x", "to_x"))
    if not has_motion:
        return
    root = bundle.root
    base_x = float(root.location.x)
    start_x = base_x + float(params.get("from_x", 0.0))
    if "to_x" in params:
        end_x = base_x + float(params["to_x"])
    else:
        end_x = base_x + float(params.get("distance", 0.0))
    root.location.x = start_x
    root.keyframe_insert(data_path="location", frame=start)
    root.location.x = end_x
    root.keyframe_insert(data_path="location", frame=end)


def apply_mmd_action(
    bundle: AssetBundle,
    semantic_key: str,
    start: int,
    end: int,
    params: dict[str, Any],
    asset_registry: AssetRegistry,
) -> MMDActionSpec:
    if bundle.armature is None or not bundle.action_set:
        raise MMDActionError("MMD bundle has no armature or action_set")
    manifest = asset_registry.resolve(bundle.action_set, "action_library")
    spec = resolve_mmd_action(manifest, semantic_key)
    action = _load_blender_action(manifest, spec.blender_action)
    armature = bundle.armature
    animation_data = armature.animation_data_create()
    track = _available_track(animation_data, spec.track, start, end)
    strip = track.strips.new(f"{semantic_key}@{start}", start, action)
    source_start, source_end = (float(value) for value in action.frame_range)
    source_duration = max(1.0, source_end - source_start)
    target_duration = max(1, end - start)
    strip.action_frame_start = source_start
    strip.action_frame_end = source_end
    if spec.loop:
        strip.repeat = max(1.0, target_duration / source_duration)
    else:
        strip.scale = target_duration / source_duration
    strip.frame_end = end
    strip.blend_in = min(spec.blend_in, target_duration / 2)
    strip.blend_out = min(spec.blend_out, target_duration / 2)
    strip.blend_type = spec.blend_type
    _keyframe_external_root_motion(bundle, start, end, params, spec)
    return spec
