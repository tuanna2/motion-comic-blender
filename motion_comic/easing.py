"""Pure-Python easing and sampling functions used by Blender motions."""

from __future__ import annotations

import math


def choose_render_engine(available: set[str]) -> str:
    """Choose the best flat-render engine across Blender 4.x and 5.x.

    Blender 4.x exposed Eevee as ``BLENDER_EEVEE_NEXT`` while Blender 5.x
    exposes it as ``BLENDER_EEVEE`` again. Reading the runtime enum prevents
    version-string checks and also gives Workbench a safe final fallback.
    """
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        if candidate in available:
            return candidate
    raise ValueError(f"no supported Blender render engine found; available: {sorted(available)}")


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def lerp(start: float, end: float, progress: float) -> float:
    return start + (end - start) * clamp(progress)


def ease_in_out(progress: float) -> float:
    """Smoothstep easing with stable end points."""
    t = clamp(progress)
    return t * t * (3.0 - 2.0 * t)


def ease_out_back(progress: float, overshoot: float = 1.70158) -> float:
    t = clamp(progress) - 1.0
    return 1.0 + (overshoot + 1.0) * t**3 + overshoot * t**2


def parabolic_arc(progress: float, height: float = 1.0) -> float:
    """Return a zero-at-ends arc peaking at ``height`` halfway through."""
    t = clamp(progress)
    return 4.0 * height * t * (1.0 - t)


def deterministic_shake(index: int, amplitude: float) -> tuple[float, float]:
    """Repeatable pseudo-shake without random module state."""
    return (
        math.sin(index * 12.9898) * amplitude,
        math.cos(index * 78.233) * amplitude * 0.65,
    )
