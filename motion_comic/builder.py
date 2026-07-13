"""Build and render a complete storyboard inside Blender."""

from __future__ import annotations

import math
import shutil
import tempfile
from pathlib import Path
from typing import Any

import bpy

from .action_catalog import motion_action_key, resolve_action
from .assets import AssetBundle, create_element, create_flat_object, create_text, hex_color
from .backends import MMDActionBackend, SpriteActionBackend
from .camera import camera_baseline
from .easing import choose_render_engine
from .encoding import encode_png_sequence, encode_png_stream
from .effects import create_action_effect
from .layout import resolve_scene_elements
from .lipsync import LipCue, cue_frame_range, load_lip_sync
from .motions import apply_motion
from .registry import AssetRegistry
from .schema import Storyboard, load_storyboard


def reset_blender() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data_group in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras):
        for block in list(data_group):
            if block.users == 0:
                data_group.remove(block)


def _set_camera_baseline(camera, scene_mode: str, world_height: float, frame: int) -> None:
    baseline = camera_baseline(scene_mode, world_height)
    camera.location = baseline.location
    camera.rotation_euler = baseline.rotation
    camera.data.ortho_scale = baseline.ortho_scale
    camera["motion_comic_scene_mode"] = scene_mode
    camera.keyframe_insert(data_path="location", frame=frame)
    camera.keyframe_insert(data_path="rotation_euler", frame=frame)
    camera.data.keyframe_insert(data_path="ortho_scale", frame=frame)


def setup_render(storyboard: Storyboard, output_path: Path):
    scene = bpy.context.scene
    settings = storyboard.settings
    engine_items = scene.render.bl_rna.properties["engine"].enum_items
    available_engines = {item.identifier for item in engine_items}
    scene.render.engine = choose_render_engine(available_engines)
    scene.render.resolution_x = settings.width
    scene.render.resolution_y = settings.height
    scene.render.resolution_percentage = 100
    scene.render.fps = settings.fps
    # Render a lossless image sequence on every Blender version. Some Blender
    # 5.x distributions no longer expose FFMPEG as an image_settings format.
    # Encoding externally is also resumable and avoids losing the whole video
    # when animation rendering is interrupted.
    frames_dir = output_path.parent / f".{output_path.stem}_frames"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(frames_dir / "frame_")
    scene.frame_start = 1
    scene.frame_end = storyboard.total_frames
    scene.render.film_transparent = False
    scene.world.color = hex_color(settings.background_color)[:3]
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = settings.samples

    camera_data = bpy.data.cameras.new("MotionComicCamera")
    camera = bpy.data.objects.new("MotionComicCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    # Keep ortho_scale tied to storyboard world height. Blender's AUTO sensor
    # fit treats it as horizontal scale for landscape output, which crops low
    # MMD characters out of the vertical frame.
    camera.data.sensor_fit = "VERTICAL"
    _set_camera_baseline(camera, settings.scene_mode, settings.world_height, 1)
    scene.camera = camera
    return scene, camera, frames_dir


def _keyframe_visibility(obj, frame: int, visible: bool) -> None:
    obj.hide_render = not visible
    obj.keyframe_insert(data_path="hide_render", frame=max(1, frame))


def _show_during(bundle: AssetBundle, start: int, end: int) -> None:
    for obj in bundle.renderables:
        visible = bundle.initial_visibility.get(obj.name, True)
        if start > 1:
            _keyframe_visibility(obj, start - 1, False)
        _keyframe_visibility(obj, start, visible)
        _keyframe_visibility(obj, end, visible)
        _keyframe_visibility(obj, end + 1, False)


def _register_bundle(registry: dict[str, Any], local_id: str, bundle: AssetBundle) -> None:
    registry[local_id] = bundle.root
    for part_name, obj in bundle.parts.items():
        registry[f"{local_id}.{part_name}"] = obj


def _keyframe_mouth_sprites(closed, opened, frame: int, *, is_open: bool) -> None:
    closed.hide_render = is_open
    closed.keyframe_insert(data_path="hide_render", frame=frame)
    opened.hide_render = not is_open
    opened.keyframe_insert(data_path="hide_render", frame=frame)


def _apply_lip_sync(
    cues: list[LipCue],
    registry: dict[str, Any],
    scene_start: int,
    scene_end: int,
    fps: int,
    bundles: dict[str, AssetBundle],
) -> None:
    """Apply audio-derived word intervals to mouth sprites or a fallback mouth scale."""
    targets = sorted({cue.target for cue in cues})
    for target in targets:
        if target not in registry:
            raise ValueError(f"lip-sync target {target!r} does not exist in scene")
        closed = registry.get(f"{target}.mouth_closed")
        opened = registry.get(f"{target}.mouth_open")
        target_cues = [cue for cue in cues if cue.target == target]
        bundle = bundles.get(target)
        if bundle is not None and bundle.backend == "mmd":
            mouth_blocks = bundle.morphs.get("mouth_open", [])
            if not mouth_blocks:
                raise ValueError(f"MMD lip-sync target {target!r} has no mouth_open morph")
            for block in mouth_blocks:
                block.value = 0.0
                block.keyframe_insert(data_path="value", frame=scene_start)
            for cue in target_cues:
                open_frame, close_frame = cue_frame_range(cue, scene_start, scene_end, fps)
                if close_frame <= open_frame:
                    continue
                for block in mouth_blocks:
                    block.value = 0.0
                    block.keyframe_insert(data_path="value", frame=max(scene_start, open_frame - 1))
                    block.value = 1.0
                    block.keyframe_insert(data_path="value", frame=open_frame)
                    block.value = 0.0
                    block.keyframe_insert(data_path="value", frame=close_frame)
            continue
        if closed is not None and opened is not None:
            _keyframe_mouth_sprites(closed, opened, scene_start, is_open=False)
            for cue in target_cues:
                open_frame, close_frame = cue_frame_range(cue, scene_start, scene_end, fps)
                if close_frame <= open_frame:
                    continue
                _keyframe_mouth_sprites(
                    closed,
                    opened,
                    max(scene_start, open_frame - 1),
                    is_open=False,
                )
                _keyframe_mouth_sprites(closed, opened, open_frame, is_open=True)
                _keyframe_mouth_sprites(closed, opened, close_frame, is_open=False)
            continue

        mouth = registry.get(f"{target}.mouth")
        if mouth is None:
            raise ValueError(
                f"lip-sync target {target!r} needs mouth_closed/mouth_open sprites or a mouth part"
            )
        base_scale = mouth.scale.copy()
        mouth.scale = base_scale
        mouth.keyframe_insert(data_path="scale", frame=scene_start)
        for cue in target_cues:
            open_frame, close_frame = cue_frame_range(cue, scene_start, scene_end, fps)
            if close_frame <= open_frame:
                continue
            mouth.scale = base_scale
            mouth.keyframe_insert(data_path="scale", frame=max(scene_start, open_frame - 1))
            mouth.scale.y = base_scale.y * 2.8
            mouth.keyframe_insert(data_path="scale", frame=open_frame)
            mouth.scale = base_scale
            mouth.keyframe_insert(data_path="scale", frame=close_frame)


def _apply_attachments(
    elements: list[dict[str, Any]],
    bundles: dict[str, AssetBundle],
) -> None:
    for element in elements:
        attachment = element.get("attach")
        if attachment is None:
            continue
        element_id = str(element["id"])
        target_id = str(attachment["target"])
        anchor_id = str(attachment["anchor"])
        if target_id not in bundles:
            raise ValueError(f"attachment target {target_id!r} does not exist for {element_id!r}")
        target_bundle = bundles[target_id]
        if anchor_id not in target_bundle.anchors:
            known = ", ".join(sorted(target_bundle.anchors)) or "none"
            raise ValueError(
                f"anchor {anchor_id!r} does not exist on {target_id!r}; available anchors: {known}"
            )
        offset = attachment.get("offset", [0, 0])
        if not isinstance(offset, list) or len(offset) < 2:
            raise ValueError(f"attachment offset for {element_id!r} must contain x and y")
        anchor_x, anchor_y = target_bundle.anchors[anchor_id]
        bundle = bundles[element_id]
        bundle.root.parent = target_bundle.anchor_parents.get(anchor_id, target_bundle.root)
        bundle.root.location = (
            anchor_x + float(offset[0]),
            anchor_y + float(offset[1]),
            float(attachment.get("z", 0.25)),
        )
        bundle.root.rotation_euler.z += math.radians(float(attachment.get("rotation", 0)))


def _scene_background(
    scene_id: str,
    scene_data: dict[str, Any],
    world_width: float,
    world_height: float,
    scene_mode: str,
):
    color = str(scene_data.get("background_color", "#7dd3fc"))
    obj = create_flat_object(
        f"{scene_id}.background",
        color=color,
        location=(0, 0, -2) if scene_mode == "sprite_2d" else (0, 5, world_height / 2),
        scale=(world_width * 1.5, world_height * 1.5, 1),
    )
    if scene_mode == "mmd_3d":
        obj.rotation_euler.x = math.radians(90)
    return AssetBundle(root=obj, renderables=[obj])


def _create_subtitle(
    scene_id: str,
    index: int,
    subtitle: dict[str, Any],
    world_height: float,
    scene_mode: str,
):
    if scene_mode == "sprite_2d":
        location = (0, float(subtitle.get("y", -world_height * 0.39)), 10)
    else:
        location = (0, -6, float(subtitle.get("y", world_height * 0.14)))
    text = create_text(
        f"{scene_id}.subtitle.{index}",
        str(subtitle["text"]),
        color=str(subtitle.get("color", "#ffffff")),
        location=location,
        size=float(subtitle.get("size", 0.48)),
    )
    if scene_mode == "mmd_3d":
        text.rotation_euler.x = math.radians(90)
    return AssetBundle(root=text, renderables=[text])


def build_storyboard(
    storyboard: Storyboard,
    output_path: Path,
    *,
    lip_sync: dict[str, list[LipCue]] | None = None,
):
    reset_blender()
    scene, camera, frames_dir = setup_render(storyboard, output_path)
    aspect = storyboard.settings.width / storyboard.settings.height
    world_height = storyboard.settings.world_height
    world_width = world_height * aspect
    current_frame = 1
    fps = storyboard.settings.fps
    scene_mode = storyboard.settings.scene_mode
    action_backends = {"sprite2d": SpriteActionBackend(), "mmd": MMDActionBackend()}
    storyboard_dir = storyboard.source_path.parent
    uses_asset_library = any(
        element.get("kind") in {"character", "prop"}
        for scene_data in storyboard.scenes
        for element in scene_data.get("elements", [])
    ) or any(scene_data.get("template_ref") for scene_data in storyboard.scenes)
    asset_registry = None
    if uses_asset_library:
        library_path = (storyboard_dir / storyboard.settings.asset_library).resolve()
        asset_registry = AssetRegistry(library_path).scan()

    for scene_data in storyboard.scenes:
        scene_id = str(scene_data["id"])
        duration_frames = round(float(scene_data["duration"]) * fps)
        scene_start = current_frame
        scene_end = current_frame + duration_frames - 1
        _set_camera_baseline(camera, scene_mode, world_height, scene_start)
        registry: dict[str, Any] = {"camera": camera}
        bundles: dict[str, AssetBundle] = {}

        template = None
        template_ref = scene_data.get("template_ref")
        if template_ref is not None:
            if asset_registry is None:
                raise ValueError("scene template_ref requires a configured asset library")
            template = asset_registry.resolve(str(template_ref), "scene_template")
        resolved_elements = resolve_scene_elements(scene_data.get("elements", []), template)

        background = _scene_background(
            scene_id, scene_data, world_width, world_height, scene_mode
        )
        _show_during(background, scene_start, scene_end)

        for element in resolved_elements:
            bundle = create_element(scene_id, element, storyboard_dir, asset_registry)
            element_id = str(element["id"])
            bundles[element_id] = bundle
            _register_bundle(registry, element_id, bundle)
            element_start = scene_start + round(float(element.get("visible_start", 0)) * fps)
            element_end = min(
                scene_end,
                scene_start
                + round(float(element.get("visible_end", scene_data["duration"])) * fps),
            )
            _show_during(bundle, element_start, element_end)

        _apply_attachments(resolved_elements, bundles)

        for motion_index, motion in enumerate(scene_data.get("motions", [])):
            action_key = motion_action_key(motion)
            if action_key is None or resolve_action(action_key).category != "effect":
                continue
            effect_start = scene_start + round(float(motion.get("start", 0)) * fps)
            effect_end = min(
                scene_end,
                scene_start + round(float(motion.get("end", scene_data["duration"])) * fps),
            )
            if action_key in {"impact_flash", "screen_flash"}:
                flash_frames = int(motion.get("params", {}).get("frames", 3))
                effect_end = min(effect_end, effect_start + max(1, flash_frames))
            effect = create_action_effect(
                scene_id,
                motion_index,
                action_key,
                bundles.get(str(motion["target"])),
                world_width=world_width,
                world_height=world_height,
                params=dict(motion.get("params", {})),
            )
            if effect is not None:
                _show_during(effect, effect_start, effect_end)

        for motion in scene_data.get("motions", []):
            target = str(motion["target"])
            obj = registry[target]
            action_key = motion_action_key(motion)
            if action_key is None:
                raise ValueError(f"motion for {target!r} is missing action")
            start = scene_start + round(float(motion.get("start", 0)) * fps)
            end = scene_start + round(float(motion.get("end", scene_data["duration"])) * fps)
            end = min(scene_end, end)
            base_target = target.split(".", 1)[0]
            bundle = bundles.get(base_target)
            if bundle is not None and target == base_target:
                action_backends[bundle.backend].apply(
                    bundle,
                    action_key,
                    start,
                    end,
                    dict(motion.get("params", {})),
                    registry=registry,
                    target=target,
                    asset_registry=asset_registry,
                )
            else:
                apply_motion(
                    action_key,
                    obj,
                    start,
                    end,
                    dict(motion.get("params", {})),
                    registry=registry,
                    target=target,
                )

        if lip_sync is not None:
            _apply_lip_sync(
                lip_sync.get(scene_id, []),
                registry,
                scene_start,
                scene_end,
                fps,
                bundles,
            )

        for index, subtitle in enumerate(scene_data.get("subtitles", [])):
            bundle = _create_subtitle(
                scene_id, index, subtitle, world_height, scene_mode
            )
            subtitle_start = scene_start + round(float(subtitle.get("start", 0)) * fps)
            subtitle_end = scene_start + round(float(subtitle.get("end", scene_data["duration"])) * fps)
            _show_during(bundle, subtitle_start, min(scene_end, subtitle_end))

        current_frame = scene_end + 1

    scene.frame_end = current_frame - 1
    scene.frame_set(1)
    return scene, frames_dir


def render_storyboard(
    storyboard_path: str | Path,
    output_path: str | Path,
    *,
    save_blend: str | Path | None = None,
    render: bool = True,
    keep_frames: bool = False,
    render_mode: str = "direct",
    audio_path: str | Path | None = None,
    lip_sync_path: str | Path | None = None,
) -> Storyboard:
    storyboard = load_storyboard(storyboard_path)
    resolved_output = Path(output_path).expanduser().resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_audio = Path(audio_path).expanduser().resolve() if audio_path is not None else None
    lip_sync = load_lip_sync(lip_sync_path) if lip_sync_path is not None else None
    scene, frames_dir = build_storyboard(storyboard, resolved_output, lip_sync=lip_sync)
    if save_blend:
        blend_path = Path(save_blend).expanduser().resolve()
        blend_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    if render:
        if render_mode not in {"direct", "frames"}:
            raise ValueError("render_mode must be 'direct' or 'frames'")
        if render_mode == "frames" or keep_frames:
            if frames_dir.exists():
                shutil.rmtree(frames_dir)
            frames_dir.mkdir(parents=True, exist_ok=True)
            bpy.ops.render.render(animation=True)
            encode_png_sequence(
                frames_dir,
                storyboard.settings.fps,
                resolved_output,
                audio_path=resolved_audio,
            )
            if not keep_frames:
                shutil.rmtree(frames_dir)
        else:
            def rendered_pngs():
                with tempfile.TemporaryDirectory(prefix="motion-comic-frame-") as directory:
                    frame_path = Path(directory) / "current.png"
                    original_path = scene.render.filepath
                    scene.render.filepath = str(frame_path)
                    try:
                        total = scene.frame_end - scene.frame_start + 1
                        for index, frame in enumerate(
                            range(scene.frame_start, scene.frame_end + 1), start=1
                        ):
                            scene.frame_set(frame)
                            bpy.ops.render.render(write_still=True)
                            yield frame_path.read_bytes()
                            if index == 1 or index == total or index % max(1, storyboard.settings.fps * 5) == 0:
                                print(
                                    f"Rendered/encoded frame {index}/{total} ({index / storyboard.settings.fps:.1f}s)",
                                    flush=True,
                                )
                    finally:
                        scene.render.filepath = original_path

            encode_png_stream(
                rendered_pngs(),
                storyboard.settings.fps,
                resolved_output,
                audio_path=resolved_audio,
            )
    return storyboard
