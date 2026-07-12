"""Existing keyframe preset backend for layered PNG characters and flat elements."""

from __future__ import annotations

from ..motions import apply_motion


class SpriteActionBackend:
    def apply(self, bundle, action, start, end, params, **context) -> None:
        apply_motion(action, bundle.root, start, end, params, **context)
