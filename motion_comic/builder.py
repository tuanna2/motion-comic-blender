"""Build and render a complete storyboard inside Blender."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import bpy

from .assets import AssetBundle, create_element, create_flat_object, create_text, hex_color
from .easing import choose_render_engine
from .motions import apply_motion
from .schema import Storyboard, load_storyboard


def reset_blender() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data_group in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras):
        for block in list(data_group):
            if block.users == 0:
                data_group.remove(block)


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
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.audio_codec = "AAC"
    scene.render.filepath = str(output_path)
    scene.frame_start = 1
    scene.frame_end = storyboard.total_frames
    scene.render.film_transparent = False
    scene.world.color = hex_color(settings.background_color)[:3]
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = settings.samples

    camera_data = bpy.data.cameras.new("MotionComicCamera")
    camera = bpy.data.objects.new("MotionComicCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = (0, 0, 20)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = settings.world_height
    scene.camera = camera
    return scene, camera


def _keyframe_visibility(obj, frame: int, visible: bool) -> None:
    obj.hide_render = not visible
    obj.keyframe_insert(data_path="hide_render", frame=max(1, frame))


def _show_during(bundle: AssetBundle, start: int, end: int) -> None:
    for obj in bundle.renderables:
        if start > 1:
            _keyframe_visibility(obj, start - 1, False)
        _keyframe_visibility(obj, start, True)
        _keyframe_visibility(obj, end, True)
        _keyframe_visibility(obj, end + 1, False)


def _register_bundle(registry: dict[str, Any], local_id: str, bundle: AssetBundle) -> None:
    registry[local_id] = bundle.root
    for part_name, obj in bundle.parts.items():
        registry[f"{local_id}.{part_name}"] = obj


def _scene_background(scene_id: str, scene_data: dict[str, Any], world_width: float, world_height: float):
    color = str(scene_data.get("background_color", "#7dd3fc"))
    obj = create_flat_object(
        f"{scene_id}.background",
        color=color,
        location=(0, 0, -2),
        scale=(world_width, world_height, 1),
    )
    return AssetBundle(root=obj, renderables=[obj])


def _create_subtitle(scene_id: str, index: int, subtitle: dict[str, Any], world_height: float):
    text = create_text(
        f"{scene_id}.subtitle.{index}",
        str(subtitle["text"]),
        color=str(subtitle.get("color", "#ffffff")),
        location=(0, float(subtitle.get("y", -world_height * 0.39)), 10),
        size=float(subtitle.get("size", 0.48)),
    )
    return AssetBundle(root=text, renderables=[text])


def build_storyboard(storyboard: Storyboard, output_path: Path):
    reset_blender()
    scene, camera = setup_render(storyboard, output_path)
    aspect = storyboard.settings.width / storyboard.settings.height
    world_height = storyboard.settings.world_height
    world_width = world_height * aspect
    current_frame = 1
    fps = storyboard.settings.fps
    asset_root = storyboard.source_path.parent

    for scene_data in storyboard.scenes:
        scene_id = str(scene_data["id"])
        duration_frames = round(float(scene_data["duration"]) * fps)
        scene_start = current_frame
        scene_end = current_frame + duration_frames - 1
        registry: dict[str, Any] = {"camera": camera}

        background = _scene_background(scene_id, scene_data, world_width, world_height)
        _show_during(background, scene_start, scene_end)

        for element in scene_data.get("elements", []):
            bundle = create_element(scene_id, element, asset_root)
            _register_bundle(registry, str(element["id"]), bundle)
            _show_during(bundle, scene_start, scene_end)

        for motion in scene_data.get("motions", []):
            target = str(motion["target"])
            obj = registry[target]
            start = scene_start + round(float(motion.get("start", 0)) * fps)
            end = scene_start + round(float(motion.get("end", scene_data["duration"])) * fps)
            end = min(scene_end, end)
            apply_motion(
                str(motion["preset"]),
                obj,
                start,
                end,
                dict(motion.get("params", {})),
                registry=registry,
                target=target,
            )

        for index, subtitle in enumerate(scene_data.get("subtitles", [])):
            bundle = _create_subtitle(scene_id, index, subtitle, world_height)
            subtitle_start = scene_start + round(float(subtitle.get("start", 0)) * fps)
            subtitle_end = scene_start + round(float(subtitle.get("end", scene_data["duration"])) * fps)
            _show_during(bundle, subtitle_start, min(scene_end, subtitle_end))

        current_frame = scene_end + 1

    scene.frame_end = current_frame - 1
    scene.frame_set(1)
    return scene


def render_storyboard(
    storyboard_path: str | Path,
    output_path: str | Path,
    *,
    save_blend: str | Path | None = None,
    render: bool = True,
) -> Storyboard:
    storyboard = load_storyboard(storyboard_path)
    resolved_output = Path(output_path).expanduser().resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    build_storyboard(storyboard, resolved_output)
    if save_blend:
        blend_path = Path(save_blend).expanduser().resolve()
        blend_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    if render:
        bpy.ops.render.render(animation=True)
    return storyboard
