"""NLA backend for precompiled MMD character assets."""

from __future__ import annotations

from ..action_catalog import resolve_action
from ..facing import FACING_ACTIONS, animate_root_facing
from ..mmd_actions import apply_mmd_action
from ..motions import apply_motion


def _apply_expression(bundle, expression: str, start: int, end: int) -> None:
    blocks = bundle.morphs.get(expression, [])
    for block in blocks:
        block.value = 0.0
        block.keyframe_insert(data_path="value", frame=max(1, start - 1))
        block.value = 1.0
        block.keyframe_insert(data_path="value", frame=start)
        block.keyframe_insert(data_path="value", frame=end)
        block.value = 0.0
        block.keyframe_insert(data_path="value", frame=end + 1)


class MMDActionBackend:
    def apply(self, bundle, action, start, end, params, **context) -> None:
        apply_mmd_action(bundle, action, start, end, params, context["asset_registry"])
        category = resolve_action(action).category
        if action in FACING_ACTIONS:
            animate_root_facing(
                bundle.root,
                action,
                start,
                end,
                params,
                registry=context.get("registry", {}),
            )
        elif category == "comic":
            apply_motion(
                action,
                bundle.root,
                start,
                end,
                params,
                registry=context.get("registry", {}),
                target=context.get("target", ""),
            )
        expression = {
            "positive_emotion": "happy",
            "negative_emotion": "angry",
            "sad_emotion": "sad",
            "fear_emotion": "surprised",
        }.get(category)
        if expression:
            _apply_expression(bundle, expression, start, end)
