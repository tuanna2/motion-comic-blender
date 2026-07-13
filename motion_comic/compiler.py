"""Deterministic compiler from an AI-friendly episode plan to storyboard JSON."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .action_catalog import ACTION_CATALOG
from .action_recipes import expand_action_recipes
from .registry import AssetRegistry
from .series import SeriesRegistry


class EpisodeCompileError(ValueError):
    """Raised when an episode plan references unknown production resources."""


def _speech_seconds(text: str) -> float:
    return max(1.2, len(text.split()) / (145.0 / 60.0) + 0.28)


def _voice(series: SeriesRegistry, speaker: str, narration: bool) -> dict[str, str]:
    if speaker == str(series.data["narrator"]["id"]):
        profile = series.data["narrator"]["voice"]
    elif speaker in series.characters:
        key = "narration" if narration else "dialogue"
        profile = series.characters[speaker]["voice_profiles"][key]
    else:
        pool = series.data["crowd"]["speaking_voice_pool"]
        profile = pool[sum(ord(char) for char in speaker) % len(pool)]
    return {
        "voice": str(profile["voice"]),
        "rate": str(profile["rate"]),
        "volume": str(profile["volume"]),
        "pitch": str(profile["pitch"]),
    }


def _locations(series: SeriesRegistry) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in series.data.get("locations", [])}


def _character_element(series: SeriesRegistry, character_id: str) -> dict[str, Any]:
    if character_id in series.characters:
        character = series.characters[character_id]
        reference = character["visual"].get(
            "asset_ref", f"{character['visual']['asset_id']}@1"
        )
    elif character_id == str(series.data["crowd"]["id"]):
        reference = f"{series.data['crowd']['asset_id']}@1"
    else:
        raise EpisodeCompileError(f"unknown character {character_id!r}")
    return {
        "id": character_id,
        "kind": "character",
        "asset_ref": str(reference),
        "slot": "auto",
        "auto_layout": True,
    }


def _normalize_character_ids(scene: dict[str, Any], series: SeriesRegistry) -> list[str]:
    ids: list[str] = []
    for item in scene.get("characters", []):
        character_id = item if isinstance(item, str) else item.get("id") if isinstance(item, dict) else None
        if not isinstance(character_id, str) or not character_id:
            raise EpisodeCompileError(f"scene {scene.get('id')!r}: invalid character entry")
        if character_id not in ids:
            ids.append(character_id)
    for line in scene.get("speech", []):
        if not isinstance(line, dict):
            raise EpisodeCompileError(f"scene {scene.get('id')!r}: speech entries must be objects")
        speaker = line.get("speaker")
        if speaker in series.characters and speaker not in ids:
            ids.append(str(speaker))
    return ids


def _compile_plan_scene(
    raw: dict[str, Any],
    index: int,
    series: SeriesRegistry,
) -> dict[str, Any]:
    scene_id = str(raw.get("id") or f"beat_{index + 1:04d}")
    locations = _locations(series)
    default_location = str(series.data.get("production", {}).get("default_location_id", ""))
    location_id = str(raw.get("location_id") or default_location)
    if location_id not in locations:
        known = ", ".join(sorted(locations)) or "none"
        raise EpisodeCompileError(
            f"scene {scene_id!r}: unknown location_id {location_id!r}; known: {known}"
        )
    location = locations[location_id]
    elements = [_character_element(series, item) for item in _normalize_character_ids(raw, series)]

    subtitles: list[dict[str, Any]] = []
    cursor = 0.0
    for line in raw.get("speech", []):
        speaker = str(line.get("speaker", ""))
        text = str(line.get("text", "")).strip()
        if not speaker or not text:
            raise EpisodeCompileError(f"scene {scene_id!r}: speech needs speaker and text")
        narration = bool(line.get("narration", False))
        start = float(line.get("start", cursor))
        end = float(line.get("end", start + _speech_seconds(text)))
        if end <= start:
            raise EpisodeCompileError(f"scene {scene_id!r}: speech end must be after start")
        subtitle = {
            "start": round(start, 4),
            "end": round(end, 4),
            "text": text,
            "speaker": speaker,
            "lip_sync": not narration and speaker != str(series.data["narrator"]["id"]),
        }
        subtitle.update(_voice(series, speaker, narration))
        subtitles.append(subtitle)
        cursor = end + float(line.get("pause_after", 0.18))

    if any(line["speaker"] == str(series.data["narrator"]["id"]) for line in subtitles):
        elements.append(
            {"id": str(series.data["narrator"]["id"]), "kind": "text", "text": "", "x": 100, "y": 100, "z": -100, "size": 0.01}
        )

    motions: list[dict[str, Any]] = []
    recipes: list[dict[str, Any]] = []
    max_visual_end = 0.0
    for beat in raw.get("visual_beats", []):
        if not isinstance(beat, dict):
            raise EpisodeCompileError(f"scene {scene_id!r}: visual_beats must contain objects")
        start = float(beat.get("start", 0.0))
        end = float(beat.get("end", start + float(beat.get("duration", 2.0))))
        max_visual_end = max(max_visual_end, end)
        if beat.get("recipe"):
            recipes.append(
                {
                    "recipe": str(beat["recipe"]),
                    "actor": str(beat.get("actor", "")),
                    "target": str(beat.get("target", "")),
                    "start": start,
                    "end": end,
                    "params": dict(beat.get("params", {})),
                }
            )
            continue
        action = beat.get("action")
        if action not in ACTION_CATALOG:
            raise EpisodeCompileError(
                f"scene {scene_id!r}: unsupported action {action!r}"
            )
        actor = str(beat.get("actor", ""))
        if not actor:
            raise EpisodeCompileError(f"scene {scene_id!r}: visual beat actor is required")
        motions.append(
            {
                "target": actor,
                "action": str(action),
                "start": start,
                "end": end,
                "params": dict(beat.get("params", {})),
            }
        )

    duration = float(raw.get("duration", max(cursor, max_visual_end, 3.0) + 0.25))
    if duration <= 0:
        raise EpisodeCompileError(f"scene {scene_id!r}: duration must be positive")
    for item in (*subtitles, *motions, *recipes):
        if float(item.get("end", duration)) > duration:
            duration = float(item["end"]) + 0.2
    duration = round(duration, 4)

    if not motions and not recipes:
        visible = [item["id"] for item in elements if item.get("kind") == "character"]
        if visible:
            motions.append(
                {"target": visible[0], "action": "idle", "start": 0, "end": duration, "params": {}}
            )
    if not recipes and not any(item["target"] == "camera" for item in motions):
        motions.append(
            {"target": "camera", "action": "camera_static", "start": 0, "end": duration, "params": {}}
        )

    scene = {
        "id": scene_id,
        "duration": duration,
        "location_id": location_id,
        "template_ref": str(location["asset_ref"]),
        "background_color": str(raw.get("background_color", "#111827")),
        "elements": elements,
        "motions": motions,
        "subtitles": subtitles,
    }
    if recipes:
        scene["recipes"] = recipes
    return scene


def _normalize_render_storyboard(
    payload: dict[str, Any],
    series: SeriesRegistry,
) -> dict[str, Any]:
    result = deepcopy(payload)
    for scene in result.get("scenes", []):
        for element in scene.get("elements", []):
            if element.get("kind") == "character" and not element.get("asset_ref"):
                character_id = str(element.get("id", ""))
                replacement = _character_element(series, character_id)
                element["asset_ref"] = replacement["asset_ref"]
        for subtitle in scene.get("subtitles", []):
            speaker = str(subtitle.get("speaker", ""))
            narration = not bool(subtitle.get("lip_sync", True))
            for key, value in _voice(series, speaker, narration).items():
                subtitle.setdefault(key, value)
    return result


def compile_episode_plan(
    payload: dict[str, Any],
    series: SeriesRegistry,
    *,
    asset_root: str | Path,
) -> dict[str, Any]:
    """Compile either a compact AI episode plan or normalize a full storyboard."""
    if not isinstance(payload, dict):
        raise EpisodeCompileError("episode plan root must be an object")
    raw_scenes = payload.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise EpisodeCompileError("episode plan scenes must be a non-empty array")

    already_renderable = all(
        isinstance(scene, dict) and "elements" in scene and "subtitles" in scene
        for scene in raw_scenes
    )
    if already_renderable:
        result = _normalize_render_storyboard(payload, series)
    else:
        production = series.data.get("production", {})
        result = {
            "version": "1.0",
            "title": str(payload.get("title") or "Untitled episode"),
            "settings": {
                "width": 1280,
                "height": 720,
                "fps": 30,
                "world_height": 9,
                "samples": 16,
                "asset_library": "assets",
                "scene_mode": str(production.get("scene_mode", "mmd_3d")),
                "action_recipes": str(
                    production.get("action_recipe_library", "recipes_cinematic@1")
                ),
            },
            "scenes": [
                _compile_plan_scene(scene, index, series)
                for index, scene in enumerate(raw_scenes)
                if isinstance(scene, dict)
            ],
        }

    registry = AssetRegistry(asset_root).scan()
    recipe_ref = str(
        result.get("settings", {}).get("action_recipes", "recipes_cinematic@1")
    )
    result["scenes"] = [
        expand_action_recipes(scene, registry, recipe_ref) if scene.get("recipes") else scene
        for scene in result["scenes"]
    ]
    return result
