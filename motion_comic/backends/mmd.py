"""NLA backend for precompiled MMD character assets."""

from __future__ import annotations

from ..mmd_actions import apply_mmd_action


class MMDActionBackend:
    def apply(self, bundle, action, start, end, params, **context) -> None:
        apply_mmd_action(bundle, action, start, end, params, context["asset_registry"])
