"""Series registry and AI-created story source validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .action_catalog import ACTION_CATALOG


SUPPORTED_VI_VOICES = {
    "vi-VN-HoaiMyNeural",
    "vi-VN-NamMinhNeural",
}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class SeriesError(ValueError):
    """Raised when a series registry is malformed."""


@dataclass(frozen=True)
class SeriesRegistry:
    source_path: Path
    data: dict[str, Any]

    @property
    def series_id(self) -> str:
        return str(self.data["series_id"])

    @property
    def characters(self) -> dict[str, dict[str, Any]]:
        return {str(item["id"]): item for item in self.data["characters"]}


@dataclass(frozen=True)
class StoryValidation:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    word_count: int
    estimated_minutes: float

    @property
    def valid(self) -> bool:
        return not self.errors


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SeriesError(message)


def _validate_voice(profile: Any, field_name: str) -> None:
    _require(isinstance(profile, dict), f"{field_name} must be an object")
    _require(profile.get("engine") == "edge_tts", f"{field_name}.engine must be 'edge_tts'")
    voice = profile.get("voice")
    _require(
        voice in SUPPORTED_VI_VOICES,
        f"{field_name}.voice must be a supported Vietnamese voice, got {voice!r}",
    )
    for key in ("rate", "volume", "pitch"):
        _require(
            isinstance(profile.get(key), str) and profile[key],
            f"{field_name}.{key} must be a non-empty string",
        )


def load_series(path: str | Path) -> SeriesRegistry:
    source = Path(path).expanduser().resolve()
    _require(source.is_file(), f"series registry not found: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SeriesError(f"invalid series JSON at line {exc.lineno}: {exc.msg}") from exc
    _require(isinstance(data, dict), "series registry root must be an object")
    _require(data.get("version") == "1.0", "series version must be '1.0'")
    series_id = data.get("series_id")
    _require(isinstance(series_id, str) and ID_PATTERN.match(series_id) is not None, "invalid series_id")
    _require(isinstance(data.get("language"), str), "series language is required")
    raw_characters = data.get("characters")
    _require(isinstance(raw_characters, list) and raw_characters, "series characters are required")

    ids: set[str] = set()
    names: set[str] = set()
    primary_colors: set[str] = set()
    for index, character in enumerate(raw_characters):
        _require(isinstance(character, dict), f"character {index} must be an object")
        character_id = character.get("id")
        name = character.get("name")
        _require(
            isinstance(character_id, str) and ID_PATTERN.match(character_id) is not None,
            f"character {index} has invalid id",
        )
        _require(character_id not in ids, f"duplicate character id {character_id!r}")
        _require(isinstance(name, str) and name, f"character {character_id!r} name is required")
        _require(name not in names, f"duplicate character name {name!r}")
        _require(isinstance(character.get("role"), str), f"character {character_id!r} role is required")
        _require(
            isinstance(character.get("personality"), list) and character["personality"],
            f"character {character_id!r} personality is required",
        )
        visual = character.get("visual")
        _require(isinstance(visual, dict), f"character {character_id!r} visual is required")
        palette = visual.get("palette")
        _require(
            isinstance(palette, list)
            and palette
            and all(isinstance(color, str) and COLOR_PATTERN.match(color) for color in palette),
            f"character {character_id!r} palette must contain hex colors",
        )
        _require(
            palette[0] not in primary_colors,
            f"character {character_id!r} primary color {palette[0]!r} is not unique",
        )
        primary_colors.add(palette[0])
        profiles = character.get("voice_profiles")
        _require(isinstance(profiles, dict), f"character {character_id!r} voice_profiles are required")
        _validate_voice(profiles.get("dialogue"), f"character {character_id}.voice_profiles.dialogue")
        _validate_voice(profiles.get("narration"), f"character {character_id}.voice_profiles.narration")
        actions = character.get("preferred_actions", [])
        _require(isinstance(actions, list), f"character {character_id!r} preferred_actions must be an array")
        unknown_actions = sorted(set(actions) - set(ACTION_CATALOG))
        _require(
            not unknown_actions,
            f"character {character_id!r} has unknown preferred actions: {', '.join(unknown_actions)}",
        )
        ids.add(character_id)
        names.add(name)

    rules = data.get("story_rules")
    _require(isinstance(rules, dict), "series story_rules are required")
    _require(
        rules.get("default_protagonist_id") in ids,
        "story_rules.default_protagonist_id must reference a character",
    )
    narrator = data.get("narrator")
    _require(isinstance(narrator, dict), "series narrator is required")
    _validate_voice(narrator.get("voice"), "narrator.voice")
    crowd = data.get("crowd")
    _require(isinstance(crowd, dict) and crowd.get("id"), "series crowd is required")
    voice_pool = crowd.get("speaking_voice_pool")
    _require(isinstance(voice_pool, list) and voice_pool, "crowd speaking_voice_pool is required")
    for index, profile in enumerate(voice_pool):
        _validate_voice(profile, f"crowd.speaking_voice_pool[{index}]")

    locations = data.get("locations")
    _require(isinstance(locations, list) and locations, "series locations are required")
    location_ids: set[str] = set()
    for index, location in enumerate(locations):
        _require(isinstance(location, dict), f"location {index} must be an object")
        location_id = location.get("id")
        _require(
            isinstance(location_id, str) and ID_PATTERN.match(location_id) is not None,
            f"location {index} has invalid id",
        )
        _require(location_id not in location_ids, f"duplicate location id {location_id!r}")
        _require(
            isinstance(location.get("asset_ref"), str) and location["asset_ref"],
            f"location {location_id!r} asset_ref is required",
        )
        location_ids.add(location_id)
    production = data.get("production")
    _require(isinstance(production, dict), "series production settings are required")
    _require(
        production.get("default_location_id") in location_ids,
        "production.default_location_id must reference a location",
    )

    for index, relationship in enumerate(data.get("relationships", [])):
        _require(isinstance(relationship, dict), f"relationship {index} must be an object")
        _require(relationship.get("from") in ids, f"relationship {index} has unknown from character")
        _require(relationship.get("to") in ids, f"relationship {index} has unknown to character")
    return SeriesRegistry(source, data)


def validate_story_source(payload: Any, series: SeriesRegistry) -> StoryValidation:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return StoryValidation(("story source root must be an object",), (), 0, 0.0)
    if payload.get("version") != "1.0":
        errors.append("version must be '1.0'")
    if payload.get("series_id") != series.series_id:
        errors.append(f"series_id must be {series.series_id!r}")
    if not isinstance(payload.get("title"), str) or not payload["title"].strip():
        errors.append("title is required")
    narration_mode = payload.get("narration_mode")
    if narration_mode not in {"first_person", "third_person"}:
        errors.append("narration_mode must be first_person or third_person")
    narrator_id = payload.get("narrator_character_id")
    if narration_mode == "first_person" and narrator_id not in series.characters:
        errors.append("first-person narrator_character_id must reference a main character")
    if narration_mode == "third_person" and narrator_id != series.data["narrator"]["id"]:
        errors.append(f"third-person narrator_character_id must be {series.data['narrator']['id']!r}")
    minutes = payload.get("estimated_minutes")
    if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or not 10 <= float(minutes) <= 30:
        errors.append("estimated_minutes must be between 10 and 30")
    character_ids = payload.get("characters_used")
    allowed = set(series.characters) | {str(series.data["crowd"]["id"])}
    if not isinstance(character_ids, list) or not character_ids:
        errors.append("characters_used must be a non-empty array")
    else:
        unknown = sorted({item for item in character_ids if item not in allowed})
        if unknown:
            errors.append(f"characters_used contains unknown IDs: {', '.join(unknown)}")
    text = payload.get("full_story_text")
    word_count = len(text.split()) if isinstance(text, str) else 0
    estimated = word_count / 145.0
    if not isinstance(text, str) or len(text.strip()) < 500:
        errors.append("full_story_text must contain the complete story (at least 500 characters)")
    if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and word_count:
        target = float(minutes)
        if estimated < target * 0.75 or estimated > target * 1.25:
            warnings.append(
                f"word count estimates {estimated:.1f} minutes at 145 words/minute, "
                f"different from declared {target:.1f} minutes"
            )
    return StoryValidation(tuple(errors), tuple(warnings), word_count, estimated)
