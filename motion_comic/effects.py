"""Procedural overlays for semantic motion-comic effect actions."""

from __future__ import annotations

from typing import Any

from .assets import AssetBundle, create_flat_object, create_text


SYMBOL_EFFECTS = {
    "sweat_drop": ("●", "#38bdf8", 0.65),
    "anger_mark": ("!!", "#ef4444", 0.8),
    "question_mark": ("?", "#fde047", 0.9),
    "exclamation_mark": ("!", "#f97316", 1.0),
    "shock_lines": ("!!!", "#fef08a", 0.75),
    "speed_lines": (">>>", "#ffffff", 0.65),
    "dust_cloud": ("...", "#d6d3d1", 0.95),
}


def create_action_effect(
    scene_id: str,
    index: int,
    action_key: str,
    target_bundle: AssetBundle | None,
    *,
    world_width: float,
    world_height: float,
    params: dict[str, Any],
) -> AssetBundle | None:
    """Create a deterministic symbol, aura, or screen overlay for an effect action."""
    name = f"{scene_id}.effect.{index}.{action_key}"
    if action_key in SYMBOL_EFFECTS:
        symbol, default_color, default_size = SYMBOL_EFFECTS[action_key]
        obj = create_text(
            name,
            str(params.get("text", symbol)),
            color=str(params.get("color", default_color)),
            location=(
                float(params.get("x", 0.75)),
                float(params.get("y", 3.1)),
                float(params.get("z", 0.6)),
            ),
            size=float(params.get("size", default_size)),
        )
        if target_bundle is not None:
            obj.parent = target_bundle.root
        return AssetBundle(root=obj, renderables=[obj])

    if action_key in {"impact_flash", "screen_flash"}:
        obj = create_flat_object(
            name,
            color=str(params.get("color", "#ffffff")),
            location=(0, 0, 14.0),
            scale=(world_width, world_height, 1),
        )
        return AssetBundle(root=obj, renderables=[obj])

    if action_key in {"dark_aura", "glow_aura"} and target_bundle is not None:
        obj = create_flat_object(
            name,
            color=str(
                params.get("color", "#312e81" if action_key == "dark_aura" else "#fde047")
            ),
            location=(0, 1.35, -0.25),
            scale=(float(params.get("width", 1.3)), float(params.get("height", 1.9)), 1),
            shape="disc",
        )
        obj.parent = target_bundle.root
        return AssetBundle(root=obj, renderables=[obj])
    return None
