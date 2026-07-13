"""AI storyboard prompt generation, validation, and render preparation."""

from __future__ import annotations

import copy
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .action_catalog import ACTION_CATALOG
from .compiler import compile_episode_plan
from .registry import AssetRegistry, AssetRegistryError
from .schema import StoryboardError, load_storyboard
from .series import SeriesRegistry, validate_story_source

_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class StoryboardValidation:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    scene_count: int
    duration_seconds: float
    subtitle_count: int
    text_coverage: float

    @property
    def valid(self) -> bool:
        return not self.errors


def _profile_json(profile: dict[str, Any]) -> str:
    return json.dumps(
        {
            "voice": profile["voice"],
            "rate": profile["rate"],
            "volume": profile["volume"],
            "pitch": profile["pitch"],
        },
        ensure_ascii=False,
    )


def build_storyboard_creation_prompt(
    story_source: dict[str, Any],
    series: SeriesRegistry,
) -> str:
    """Build a copy/paste prompt that asks an AI for renderer-compatible JSON."""
    source_validation = validate_story_source(story_source, series)
    if not source_validation.valid:
        raise ValueError("invalid story source: " + "; ".join(source_validation.errors))

    production_characters = [
        {
            "id": character_id,
            "name": character["name"],
            "asset_ref": character["visual"].get(
                "asset_ref", f"{character['visual']['asset_id']}@1"
            ),
            "preferred_actions": character.get("preferred_actions", []),
        }
        for character_id, character in series.characters.items()
    ]
    locations = [
        {
            "location_id": item["id"],
            "name": item["name"],
            "keywords": item.get("keywords", []),
        }
        for item in series.data.get("locations", [])
    ]
    compact_shape = {
        "version": "1.0",
        "title": story_source["title"],
        "scenes": [
            {
                "id": "beat_0001",
                "location_id": "urban_alley",
                "characters": [story_source["characters_used"][0]],
                "speech": [
                    {
                        "speaker": story_source["narrator_character_id"],
                        "text": "Nguyên văn phần dẫn chuyện hoặc thoại.",
                        "narration": True,
                        "pause_after": 0.2,
                    }
                ],
                "visual_beats": [
                    {
                        "actor": story_source["characters_used"][0],
                        "action": "look_around",
                        "start": 0,
                        "duration": 2.0,
                        "params": {},
                    },
                    {
                        "actor": story_source["characters_used"][0],
                        "recipe": "dramatic_reveal",
                        "start": 2.0,
                        "duration": 2.5,
                        "params": {},
                    },
                ],
            }
        ],
    }
    return f"""# ROLE
You are a visual-beat planner for a deterministic Blender MMD motion-comic compiler.

# TASK
Convert the complete Vietnamese story into one compact episode-plan JSON object. The local compiler—not you—will assign MMD assets, voices, slots, camera defaults, scene geometry, and exact fallback motions.

# NON-NEGOTIABLE RULES
1. Return exactly one JSON object, no Markdown.
2. Preserve every spoken/narrated sentence in chronological order inside scenes[].speech[].text. Do not summarize.
3. Split on location, active cast, or visible beat changes. Prefer 4-15 seconds of spoken content per scene.
4. Use only character IDs, location IDs, action keys, and recipe keys listed below.
5. speech speaker must be a listed character ID, crowd_default, or narrator.
6. narration=true for narration/thoughts and false for visible dialogue.
7. visual_beats actor may be a character ID or camera. A beat uses either action or recipe.
8. For a two-person recipe, set actor and target. Times are relative to that scene.
9. Keep visual beats sparse and meaningful; the compiler adds idle and static camera automatically.

# CHARACTERS
{json.dumps(production_characters, ensure_ascii=False, indent=2)}

# LOCATIONS
{json.dumps(locations, ensure_ascii=False, indent=2)}

# ACTION RECIPES
dramatic_reveal, heated_argument, punch_impact, chase_escape, comfort_moment

# ALLOWED_ACTIONS
{', '.join(sorted(ACTION_CATALOG))}

# OUTPUT SHAPE
{json.dumps(compact_shape, ensure_ascii=False, indent=2)}

# COMPLETE STORY SOURCE
{json.dumps(story_source, ensure_ascii=False, indent=2)}
"""

    characters = []
    for character_id, character in series.characters.items():
        characters.append(
            {
                "id": character_id,
                "name": character["name"],
                "asset_ref": f"{character['visual']['asset_id']}@1",
                "dialogue_voice": character["voice_profiles"]["dialogue"],
                "narration_voice": character["voice_profiles"]["narration"],
                "preferred_actions": character.get("preferred_actions", []),
            }
        )
    narrator = series.data["narrator"]
    allowed_actions = ", ".join(sorted(ACTION_CATALOG))
    expected_seconds = round(float(story_source["estimated_minutes"]) * 60)

    return f"""# ROLE
You are a storyboard compiler for a deterministic Blender 2D motion-comic engine.

# TASK
Convert the complete Vietnamese story source below into ONE renderable storyboard JSON object. Return JSON only, without Markdown fences or explanation.

# HARD OUTPUT CONTRACT
- Root version must be \"1.0\".
- Root fields: version, title, settings, scenes.
- settings must use width=1280, height=720, fps=30, world_height=9, samples=16, asset_library=\"assets\".
- Total duration should be close to {expected_seconds} seconds.
- Split by visible beat. Prefer 3-10 seconds per scene; use longer scenes only when the picture can remain useful.
- Every scene requires: id, duration, background_color, elements, motions, subtitles.
- Element kinds allowed: character, prop, image, rectangle, disc, text.
- Main characters use kind=\"character\", their exact asset_ref below, explicit x/y/z/scale, and no template_ref.
- Only use action keys from ALLOWED_ACTIONS. A motion requires target, action, start, end, params.
- Every motion range must fit inside its scene duration.
- Every spoken/narrated portion must appear in subtitles so the complete story can be sent to TTS.
- Preserve Vietnamese wording and chronological order. Do not summarize or omit plot content.
- Dialogue speaker must be the exact character ID and that character must exist in the scene elements.
- First-person narration uses narrator_character_id as speaker, with that character's narration voice and \"lip_sync\": false.
- Third-person narration uses speaker=\"narrator\". Add an off-screen text element with id=\"narrator\", kind=\"text\", text=\"\", x=100, y=100, z=-100, size=0.01; set \"lip_sync\": false.
- Dialogue uses the character dialogue voice and \"lip_sync\": true.
- Subtitle fields: start, end, text, speaker, voice, rate, volume, pitch, lip_sync.
- Keep each subtitle inside scene duration. Avoid overlapping speech unless the story explicitly needs interruption.
- Use 1-3 meaningful motions per visible character, not constant random motion.
- Use camera motions by targeting \"camera\".
- Backgrounds may initially use background_color plus rectangle/text/image elements. Do not invent scene template asset refs.

# CHARACTER ASSETS AND VOICES
{json.dumps(characters, ensure_ascii=False, indent=2)}

Third-person narrator voice: {_profile_json(narrator['voice'])}

# MINIMAL EXAMPLE SHAPE
{{
  \"version\": \"1.0\",
  \"title\": \"Example\",
  \"settings\": {{
    \"width\": 1280,
    \"height\": 720,
    \"fps\": 30,
    \"world_height\": 9,
    \"background_color\": \"#111827\",
    \"samples\": 16,
    \"asset_library\": \"assets\",
    \"tts\": {{\"voice\": \"vi-VN-HoaiMyNeural\", \"rate\": \"+0%\", \"volume\": \"+0%\", \"pitch\": \"+0Hz\"}}
  }},
  \"scenes\": [
    {{
      \"id\": \"beat_0001\",
      \"duration\": 5.0,
      \"background_color\": \"#111827\",
      \"elements\": [
        {{\"id\": \"char_minh_khang\", \"kind\": \"character\", \"asset_ref\": \"char_minh_khang@1\", \"x\": 0, \"y\": -3.0, \"z\": 2, \"scale\": 0.9}}
      ],
      \"motions\": [
        {{\"target\": \"char_minh_khang\", \"action\": \"wake_up\", \"start\": 0, \"end\": 1.5, \"params\": {{}}}},
        {{\"target\": \"camera\", \"action\": \"camera_push_in\", \"start\": 0, \"end\": 5.0, \"params\": {{}}}}
      ],
      \"subtitles\": [
        {{\"start\": 0, \"end\": 4.8, \"text\": \"Tôi tỉnh dậy giữa tiếng chuông báo cháy.\", \"speaker\": \"char_minh_khang\", \"voice\": \"vi-VN-NamMinhNeural\", \"rate\": \"-4%\", \"volume\": \"+0%\", \"pitch\": \"-4Hz\", \"lip_sync\": false}}
      ]
    }}
  ]
}}

# ALLOWED_ACTIONS
{allowed_actions}

# STORY SOURCE
{json.dumps(story_source, ensure_ascii=False, indent=2)}
"""


def _tokens(text: str) -> list[str]:
    return [item.lower() for item in _WORD_RE.findall(text)]


def _coverage(source: str, rendered: str) -> float:
    source_tokens = _tokens(source)
    if not source_tokens:
        return 1.0
    rendered_counts: dict[str, int] = {}
    for token in _tokens(rendered):
        rendered_counts[token] = rendered_counts.get(token, 0) + 1
    matched = 0
    for token in source_tokens:
        count = rendered_counts.get(token, 0)
        if count:
            matched += 1
            rendered_counts[token] = count - 1
    return matched / len(source_tokens)


def validate_storyboard_payload(
    payload: Any,
    series: SeriesRegistry,
    *,
    story_source: dict[str, Any] | None = None,
    asset_root: str | Path | None = None,
) -> StoryboardValidation:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return StoryboardValidation(("storyboard root must be an object",), (), 0, 0.0, 0, 0.0)

    with tempfile.TemporaryDirectory(prefix="motion-comic-storyboard-") as directory:
        path = Path(directory) / "storyboard.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        try:
            storyboard = load_storyboard(path)
        except (StoryboardError, OSError, ValueError) as exc:
            return StoryboardValidation((str(exc),), (), 0, 0.0, 0, 0.0)

    allowed_speakers = set(series.characters) | {
        str(series.data["narrator"]["id"]),
        str(series.data["crowd"]["id"]),
    }
    subtitle_texts: list[str] = []
    subtitle_count = 0
    asset_refs: set[tuple[str, str]] = set()
    for scene in storyboard.scenes:
        element_ids = {str(item["id"]) for item in scene.get("elements", [])}
        for element in scene.get("elements", []):
            if element.get("kind") in {"character", "prop"}:
                asset_refs.add((str(element["asset_ref"]), str(element["kind"])))
        for subtitle in scene.get("subtitles", []):
            subtitle_count += 1
            subtitle_texts.append(str(subtitle.get("text", "")))
            speaker = subtitle.get("speaker")
            if speaker not in allowed_speakers:
                errors.append(f"scene {scene['id']}: unknown subtitle speaker {speaker!r}")
            if subtitle.get("lip_sync", True) and speaker not in element_ids:
                errors.append(
                    f"scene {scene['id']}: lip-sync speaker {speaker!r} must exist in elements"
                )

    coverage = 1.0
    if story_source is not None:
        source_result = validate_story_source(story_source, series)
        if not source_result.valid:
            errors.append("story_source is invalid: " + "; ".join(source_result.errors))
        else:
            coverage = _coverage(
                str(story_source.get("full_story_text", "")),
                " ".join(subtitle_texts),
            )
            if coverage < 0.72:
                warnings.append(
                    f"subtitle text covers only about {coverage * 100:.1f}% of source words; AI may have omitted story content"
                )
            target = float(story_source["estimated_minutes"]) * 60
            if storyboard.duration_seconds < target * 0.65 or storyboard.duration_seconds > target * 1.35:
                warnings.append(
                    f"storyboard duration {storyboard.duration_seconds / 60:.1f} minutes differs from declared {target / 60:.1f} minutes"
                )

    if asset_root is not None:
        try:
            registry = AssetRegistry(asset_root).scan()
            for reference, kind in sorted(asset_refs):
                expected = "sprite_prop" if kind == "prop" else None
                try:
                    manifest = registry.resolve(reference, expected)
                    if kind == "character" and manifest.asset_type not in {
                        "layered_character",
                        "mmd_character",
                    }:
                        raise AssetRegistryError(
                            f"asset_ref {reference!r} is not a character asset"
                        )
                except AssetRegistryError as exc:
                    warnings.append(str(exc))
        except AssetRegistryError as exc:
            warnings.append(str(exc))

    return StoryboardValidation(
        tuple(dict.fromkeys(errors)),
        tuple(dict.fromkeys(warnings)),
        len(storyboard.scenes),
        storyboard.duration_seconds,
        subtitle_count,
        coverage,
    )


def prepare_storyboard_for_render(
    payload: dict[str, Any],
    *,
    asset_root: str | Path,
    placeholder_missing_assets: bool = False,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Normalize paths and optionally replace missing character assets for previews."""
    prepared = copy.deepcopy(payload)
    prepared.setdefault("settings", {})["asset_library"] = str(Path(asset_root).resolve())
    warnings: list[str] = []
    registry = AssetRegistry(asset_root).scan()
    for scene in prepared.get("scenes", []):
        for element in scene.get("elements", []):
            kind = element.get("kind")
            if kind not in {"character", "prop"}:
                continue
            reference = str(element.get("asset_ref", ""))
            expected = "sprite_prop" if kind == "prop" else None
            try:
                manifest = registry.resolve(reference, expected)
                if kind == "character" and manifest.asset_type not in {
                    "layered_character",
                    "mmd_character",
                }:
                    raise AssetRegistryError(
                        f"asset_ref {reference!r} is not a character asset"
                    )
            except AssetRegistryError:
                if placeholder_missing_assets and kind == "character":
                    registry.resolve("char_angler@1", "layered_character")
                    element["asset_ref"] = "char_angler@1"
                    warnings.append(
                        f"replaced missing character asset {reference!r} with preview placeholder char_angler@1"
                    )
                else:
                    raise
    return prepared, tuple(dict.fromkeys(warnings))
