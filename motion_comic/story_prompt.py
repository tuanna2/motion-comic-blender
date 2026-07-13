"""Build copy/paste prompts for AI story creation from a series registry."""

from __future__ import annotations

import json
from typing import Any

from .action_catalog import CATEGORY_KEYS
from .series import SeriesRegistry


def _prompt_series_database(series: SeriesRegistry) -> dict[str, Any]:
    data = series.data
    return {
        "series_id": data["series_id"],
        "title": data.get("title"),
        "language": data["language"],
        "story_rules": data["story_rules"],
        "characters": [
            {
                "id": character["id"],
                "name": character["name"],
                "gender": character.get("gender"),
                "age": character.get("age"),
                "role": character["role"],
                "story_function": character.get("story_function"),
                "personality": character["personality"],
                "speech_style": character.get("speech_style"),
                "visual": character["visual"],
                "preferred_actions": character.get("preferred_actions", []),
            }
            for character in data["characters"]
        ],
        "relationships": data.get("relationships", []),
        "crowd": {
            "id": data["crowd"]["id"],
            "name": data["crowd"].get("name"),
            "reuse_same_appearance": data["crowd"].get("reuse_same_appearance", True),
        },
    }


def build_story_creation_prompt(
    series: SeriesRegistry,
    *,
    minutes: int,
    genre: str,
    narration_mode: str,
    protagonist_id: str,
    premise: str = "",
) -> str:
    if not 10 <= minutes <= 30:
        raise ValueError("minutes must be between 10 and 30")
    if narration_mode not in {"first_person", "third_person"}:
        raise ValueError("narration_mode must be first_person or third_person")
    if protagonist_id not in series.characters:
        raise ValueError(f"unknown protagonist_id {protagonist_id!r}")
    narrator_id = protagonist_id if narration_mode == "first_person" else str(series.data["narrator"]["id"])
    min_words = minutes * 135
    max_words = minutes * 155
    action_catalog = {category: list(keys) for category, keys in CATEGORY_KEYS.items()}
    output_shape = {
        "version": "1.0",
        "series_id": series.series_id,
        "title": "Tên truyện",
        "narration_mode": narration_mode,
        "narrator_character_id": narrator_id,
        "estimated_minutes": minutes,
        "characters_used": [protagonist_id],
        "logline": "Tóm tắt một câu, không thay thế nội dung truyện.",
        "full_story_text": "Toàn bộ nội dung truyện hoàn chỉnh để TTS, gồm dẫn chuyện và lời thoại.",
    }
    return f"""# ROLE
You are a professional Vietnamese serialized-fiction writer creating source content for a deterministic 2D motion-comic engine.

# TASK
Write one complete Vietnamese story episode using the fixed series database below.

# TARGET
- Genre: {genre.strip() or ', '.join(series.data.get('default_genres', []))}
- Target duration: {minutes} minutes of Vietnamese TTS
- Target length: {min_words}-{max_words} Vietnamese words
- Narration mode: {narration_mode}
- Protagonist: {protagonist_id}
- Narrator ID: {narrator_id}
- Premise supplied by user: {premise.strip() or 'Tự tạo một bí ẩn mới phù hợp series.'}

# SPOKEN-CONTENT RULES
1. full_story_text is the complete source that will be sent to TTS. Do not provide an outline in place of the story.
2. Include narration, thoughts, and complete dialogue inside full_story_text.
3. Attribute every dialogue line clearly by character name in the surrounding prose so another AI can identify the speaker safely.
4. First-person narration uses the protagonist's “tôi” voice. Third-person narration uses an invisible narrator.
5. Do not switch narration person midway.
6. Keep character names, personalities, appearance, relationships, and speech styles consistent with SERIES_DATABASE.
7. Do not invent another named main character. Unnamed passers-by, guards, customers, or crowds use crowd_default.
8. Do not mention character IDs, action keys, cameras, TTS, JSON, or production instructions inside full_story_text.

# STORY RULES
1. Begin with a strong visual hook within the first 150 words.
2. Use scenes and events that can be shown visually with reusable locations, props, expressions, and actions.
3. Build a clear escalation, at least one meaningful reversal, a climax, and a satisfying ending or deliberate cliffhanger.
4. Balance narration with character dialogue. Avoid several pages of pure exposition.
5. Give each used main character a distinct purpose; do not force all five into the episode.
6. Preserve long-term relationship states unless the episode earns a change through visible events.

# ACTIONABILITY REFERENCE
These are visual actions the later planner can animate. You do not output action keys, but prefer events that can be represented by this catalog:
{json.dumps(action_catalog, ensure_ascii=False, indent=2)}

# SERIES_DATABASE
{json.dumps(_prompt_series_database(series), ensure_ascii=False, indent=2)}

# OUTPUT RULES
1. Output exactly one valid JSON object and nothing else.
2. Do not wrap the JSON in Markdown fences.
3. Use this exact structure:
{json.dumps(output_shape, ensure_ascii=False, indent=2)}
4. characters_used contains only IDs from SERIES_DATABASE plus crowd_default.
5. full_story_text must contain {min_words}-{max_words} words and must be ready for TTS without additional writing.
"""
