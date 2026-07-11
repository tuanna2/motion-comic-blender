"""Semantic action catalog for high-volume motion-comic production."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActionSpec:
    key: str
    category: str
    handler: str


CATEGORY_KEYS: dict[str, tuple[str, ...]] = {
    "locomotion": (
        "idle", "walk", "walk_slow", "walk_fast", "run", "sprint", "sneak",
        "tiptoe", "crawl", "climb", "jump", "jump_back", "step_forward", "step_back",
        "turn_left", "turn_right", "turn_around", "enter_scene", "exit_scene", "approach",
        "move_away", "stop_suddenly", "stumble", "fall_down", "get_up",
    ),
    "pose": (
        "stand", "sit", "sit_down", "stand_up", "lie_down", "sleep", "wake_up",
        "lean_forward", "lean_back", "bend_down", "kneel", "crouch", "cross_arms",
        "hands_on_hips", "hands_in_pockets", "stretch", "shiver", "freeze", "hide",
        "peek", "look_around", "look_up", "look_down", "look_back",
    ),
    "gesture": (
        "point", "wave", "beckon", "raise_hand", "lower_hand", "reach_out", "grab",
        "hold", "release", "give_item", "receive_item", "take_item", "offer_item",
        "throw_item", "catch_item", "pick_up", "put_down", "open", "close", "push",
        "pull", "drag", "carry", "lift", "drop", "touch", "tap", "knock", "clap",
        "rub_hands", "cover_face", "cover_mouth", "scratch_head", "facepalm", "wipe_sweat",
        "wipe_tears",
    ),
    "interaction": (
        "handshake", "hug", "pat_shoulder", "hold_hand", "pull_person", "push_person",
        "help_up", "support_person", "block_path", "stand_in_front", "comfort", "beg",
        "bow", "apologize", "threaten", "confront", "ignore", "follow", "chase", "escape",
    ),
    "dialogue": (
        "talk", "talk_calm", "talk_happy", "talk_angry", "talk_sad", "talk_nervous",
        "shout", "yell", "whisper", "mumble", "argue", "explain", "ask", "answer",
        "command", "refuse", "agree", "nod", "shake_head", "listen", "interrupt", "gasp",
        "sigh",
    ),
    "positive_emotion": (
        "neutral", "smile", "big_smile", "laugh", "laugh_hard", "excited", "proud",
        "relieved", "curious", "confident", "surprised_happy", "love", "shy", "blush",
    ),
    "negative_emotion": (
        "angry", "furious", "annoyed", "frustrated", "disgusted", "jealous", "suspicious",
        "cold_stare", "glare", "clench_fist", "grit_teeth", "stomp", "slam_table",
        "point_angrily", "turn_away_angry", "throw_in_anger",
    ),
    "sad_emotion": (
        "sad", "cry", "sob", "tearful", "disappointed", "hopeless", "lonely", "hurt",
        "guilty", "regret", "lower_head", "hug_knees", "collapse", "walk_away_sad",
    ),
    "fear_emotion": (
        "surprised", "shocked", "scared", "terrified", "panic", "nervous", "confused",
        "hesitate", "tremble", "step_back_scared", "cover_ears", "shield_face", "hide_behind",
        "look_over_shoulder", "run_away_scared",
    ),
    "thinking": (
        "think", "deep_thought", "remember", "realize", "inspect", "search", "read", "write",
        "study", "check_phone", "listen_at_door", "observe_secretly", "scan_room",
    ),
    "fight": (
        "punch", "kick", "slap", "block_attack", "dodge", "duck", "grab_person", "restrain",
        "struggle", "wrestle", "charge", "knock_down", "get_hit", "recoil", "draw_weapon",
        "aim_weapon", "swing_weapon", "defend", "surrender", "protect_person",
    ),
    "daily": (
        "eat", "drink", "cook", "pour_drink", "open_door", "close_door", "lock_door",
        "unlock_door", "sit_at_table", "use_phone", "make_call", "answer_call", "hang_up",
        "type_keyboard", "drive", "get_in_vehicle", "get_out_vehicle", "change_clothes",
        "wash_face", "brush_teeth",
    ),
    "comic": (
        "idle_bob", "breathing", "head_bob", "talk_bounce", "blink", "eye_shift", "head_turn",
        "body_turn", "lean_in", "lean_out", "reaction_pop", "impact_shake", "fear_shake",
        "anger_shake", "surprise_jump", "sad_sink", "walk_cycle_fake", "run_cycle_fake",
        "enter_slide", "exit_slide", "foreground_pass", "depth_move",
    ),
    "camera": (
        "camera_static", "camera_pan_left", "camera_pan_right", "camera_pan_up", "camera_pan_down",
        "camera_zoom_in", "camera_zoom_out", "camera_push_in", "camera_pull_out", "camera_follow",
        "camera_shake", "camera_whip_pan", "camera_focus_shift", "camera_parallax", "camera_tilt",
        "camera_handheld",
    ),
    "effect": (
        "sweat_drop", "anger_mark", "question_mark", "exclamation_mark", "shock_lines",
        "speed_lines", "impact_flash", "dust_cloud", "tear_stream", "blush_overlay", "dark_aura",
        "glow_aura", "heartbeat", "screen_flash", "screen_blur", "vignette", "freeze_frame",
        "slow_motion",
    ),
}


HANDLER_BY_CATEGORY = {
    "locomotion": "locomotion_action",
    "pose": "pose_action",
    "gesture": "gesture_action",
    "interaction": "interaction_action",
    "dialogue": "dialogue_action",
    "positive_emotion": "emotion_action",
    "negative_emotion": "emotion_action",
    "sad_emotion": "emotion_action",
    "fear_emotion": "emotion_action",
    "thinking": "thinking_action",
    "fight": "fight_action",
    "daily": "daily_action",
    "comic": "comic_action",
    "camera": "camera_action",
    "effect": "effect_action",
}


ACTION_CATALOG: dict[str, ActionSpec] = {}
for category, keys in CATEGORY_KEYS.items():
    for key in keys:
        ACTION_CATALOG.setdefault(key, ActionSpec(key, category, HANDLER_BY_CATEGORY[category]))

# Backward-compatible specialized presets remain valid alongside semantic actions.
for legacy_key in (
    "enter", "look", "pull_rod", "fish_jump", "shake", "impact", "fall", "camera_zoom",
    "camera_pan",
):
    ACTION_CATALOG[legacy_key] = ActionSpec(legacy_key, "legacy", legacy_key)


def resolve_action(key: str) -> ActionSpec:
    try:
        return ACTION_CATALOG[key]
    except KeyError as exc:
        raise ValueError(f"unknown action {key!r}") from exc


def motion_action_key(motion: dict[str, Any]) -> str | None:
    action = motion.get("action")
    preset = motion.get("preset")
    if action is not None and preset is not None and action != preset:
        raise ValueError("motion cannot declare different action and preset values")
    value = action if action is not None else preset
    return value if isinstance(value, str) else None
