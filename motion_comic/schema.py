"""Storyboard loading and validation independent from Blender."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_PRESETS = {
    "enter",
    "idle",
    "talk",
    "walk",
    "wave",
    "look",
    "nod",
    "pull_rod",
    "fish_jump",
    "shake",
    "impact",
    "fall",
    "camera_zoom",
    "camera_pan",
}

SUPPORTED_ELEMENT_KINDS = {
    "character",
    "prop",
    "fishing_character",
    "fish",
    "image",
    "rectangle",
    "disc",
    "text",
}


class StoryboardError(ValueError):
    """Raised when storyboard JSON cannot be rendered safely."""


@dataclass(frozen=True)
class TTSSettings:
    voice: str = "vi-VN-HoaiMyNeural"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"


@dataclass(frozen=True)
class RenderSettings:
    width: int = 1280
    height: int = 720
    fps: int = 30
    world_height: float = 9.0
    background_color: str = "#111827"
    samples: int = 16
    asset_library: str = "assets"
    tts: TTSSettings = field(default_factory=TTSSettings)


@dataclass(frozen=True)
class Storyboard:
    source_path: Path
    title: str
    settings: RenderSettings
    scenes: list[dict[str, Any]] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return sum(float(scene["duration"]) for scene in self.scenes)

    @property
    def total_frames(self) -> int:
        return round(self.duration_seconds * self.settings.fps)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StoryboardError(message)


def _number(value: Any, field_name: str) -> float:
    _require(isinstance(value, (int, float)) and not isinstance(value, bool), f"{field_name} must be a number")
    return float(value)


def _validate_motion(motion: dict[str, Any], duration: float, scene_id: str) -> None:
    target = motion.get("target")
    preset = motion.get("preset")
    _require(isinstance(target, str) and target, f"scene {scene_id}: motion target is required")
    _require(preset in SUPPORTED_PRESETS, f"scene {scene_id}: unsupported preset {preset!r}")
    start = _number(motion.get("start", 0), f"scene {scene_id}: motion start")
    end = _number(motion.get("end", duration), f"scene {scene_id}: motion end")
    _require(start >= 0, f"scene {scene_id}: motion start cannot be negative")
    _require(end > start, f"scene {scene_id}: motion end must be greater than start")
    _require(end <= duration + 1e-6, f"scene {scene_id}: motion ends after scene duration")
    params = motion.get("params", {})
    _require(isinstance(params, dict), f"scene {scene_id}: motion params must be an object")


def _validate_scene(scene: dict[str, Any], index: int) -> None:
    scene_id = scene.get("id")
    _require(isinstance(scene_id, str) and scene_id, f"scene {index}: id is required")
    duration = _number(scene.get("duration"), f"scene {scene_id}: duration")
    _require(duration > 0, f"scene {scene_id}: duration must be positive")
    template_ref = scene.get("template_ref")
    if template_ref is not None:
        _require(
            isinstance(template_ref, str) and template_ref,
            f"scene {scene_id}: template_ref must be a non-empty string",
        )

    elements = scene.get("elements", [])
    motions = scene.get("motions", [])
    subtitles = scene.get("subtitles", [])
    _require(isinstance(elements, list), f"scene {scene_id}: elements must be an array")
    _require(isinstance(motions, list), f"scene {scene_id}: motions must be an array")
    _require(isinstance(subtitles, list), f"scene {scene_id}: subtitles must be an array")

    element_ids: set[str] = set()
    attachments: list[tuple[str, dict[str, Any]]] = []
    for element in elements:
        _require(isinstance(element, dict), f"scene {scene_id}: each element must be an object")
        element_id = element.get("id")
        kind = element.get("kind")
        _require(isinstance(element_id, str) and element_id, f"scene {scene_id}: element id is required")
        _require(element_id not in element_ids, f"scene {scene_id}: duplicate element id {element_id!r}")
        _require(kind in SUPPORTED_ELEMENT_KINDS, f"scene {scene_id}: unsupported element kind {kind!r}")
        if kind == "image":
            _require(isinstance(element.get("asset"), str), f"scene {scene_id}: image asset is required")
        if kind in {"character", "prop"}:
            _require(
                isinstance(element.get("asset_ref"), str) and element["asset_ref"],
                f"scene {scene_id}: {kind} asset_ref is required",
            )
        if "slot" in element:
            _require(isinstance(element["slot"], str), f"scene {scene_id}: element slot must be a string")
        if "scene_anchor" in element:
            _require(
                isinstance(element["scene_anchor"], str),
                f"scene {scene_id}: element scene_anchor must be a string",
            )
        attachment = element.get("attach")
        if attachment is not None:
            _require(isinstance(attachment, dict), f"scene {scene_id}: attach must be an object")
            _require(
                isinstance(attachment.get("target"), str) and attachment["target"],
                f"scene {scene_id}: attach target is required",
            )
            _require(
                isinstance(attachment.get("anchor"), str) and attachment["anchor"],
                f"scene {scene_id}: attach anchor is required",
            )
            attachments.append((element_id, attachment))
        element_ids.add(element_id)

    for element_id, attachment in attachments:
        target = attachment["target"]
        _require(target in element_ids, f"scene {scene_id}: attachment target {target!r} does not exist")
        _require(target != element_id, f"scene {scene_id}: element {element_id!r} cannot attach to itself")

    for motion in motions:
        _require(isinstance(motion, dict), f"scene {scene_id}: each motion must be an object")
        _validate_motion(motion, duration, scene_id)
        target = motion["target"].split(".", 1)[0]
        _require(target == "camera" or target in element_ids, f"scene {scene_id}: unknown motion target {motion['target']!r}")

    for subtitle in subtitles:
        _require(isinstance(subtitle, dict), f"scene {scene_id}: each subtitle must be an object")
        _require(isinstance(subtitle.get("text"), str), f"scene {scene_id}: subtitle text is required")
        start = _number(subtitle.get("start", 0), f"scene {scene_id}: subtitle start")
        end = _number(subtitle.get("end", duration), f"scene {scene_id}: subtitle end")
        _require(0 <= start < end <= duration + 1e-6, f"scene {scene_id}: invalid subtitle range")
        speaker = subtitle.get("speaker")
        if speaker is not None:
            _require(
                isinstance(speaker, str) and speaker in element_ids,
                f"scene {scene_id}: subtitle speaker {speaker!r} does not exist",
            )
        for field_name in ("voice", "rate", "volume", "pitch"):
            if field_name in subtitle:
                _require(
                    isinstance(subtitle[field_name], str) and subtitle[field_name],
                    f"scene {scene_id}: subtitle {field_name} must be a non-empty string",
                )


def load_storyboard(path: str | Path) -> Storyboard:
    source_path = Path(path).expanduser().resolve()
    _require(source_path.is_file(), f"storyboard not found: {source_path}")
    try:
        data = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoryboardError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc

    _require(isinstance(data, dict), "storyboard root must be an object")
    _require(data.get("version") == "1.0", "storyboard version must be '1.0'")
    title = data.get("title", source_path.stem)
    _require(isinstance(title, str) and title, "title must be a non-empty string")

    raw_settings = data.get("settings", {})
    _require(isinstance(raw_settings, dict), "settings must be an object")
    raw_tts = raw_settings.get("tts", {})
    _require(isinstance(raw_tts, dict), "settings.tts must be an object")
    tts_defaults = {
        "voice": "vi-VN-HoaiMyNeural",
        "rate": "+0%",
        "volume": "+0%",
        "pitch": "+0Hz",
    }
    for field_name, default in tts_defaults.items():
        value = raw_tts.get(field_name, default)
        _require(
            isinstance(value, str) and value,
            f"settings.tts.{field_name} must be a non-empty string",
        )
    tts = TTSSettings(
        voice=raw_tts.get("voice", tts_defaults["voice"]),
        rate=raw_tts.get("rate", tts_defaults["rate"]),
        volume=raw_tts.get("volume", tts_defaults["volume"]),
        pitch=raw_tts.get("pitch", tts_defaults["pitch"]),
    )
    settings = RenderSettings(
        width=int(raw_settings.get("width", 1280)),
        height=int(raw_settings.get("height", 720)),
        fps=int(raw_settings.get("fps", 30)),
        world_height=float(raw_settings.get("world_height", 9.0)),
        background_color=str(raw_settings.get("background_color", "#111827")),
        samples=int(raw_settings.get("samples", 16)),
        asset_library=str(raw_settings.get("asset_library", "assets")),
        tts=tts,
    )
    _require(settings.width > 0 and settings.height > 0, "render dimensions must be positive")
    _require(1 <= settings.fps <= 120, "fps must be between 1 and 120")
    _require(settings.world_height > 0, "world_height must be positive")

    scenes = data.get("scenes")
    _require(isinstance(scenes, list) and scenes, "scenes must be a non-empty array")
    for index, scene in enumerate(scenes):
        _require(isinstance(scene, dict), f"scene {index}: must be an object")
        _validate_scene(scene, index)

    return Storyboard(source_path=source_path, title=title, settings=settings, scenes=scenes)
