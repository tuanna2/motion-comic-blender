"""Resolve semantic scene slots and anchors into deterministic transforms."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .registry import AssetManifest


class LayoutError(ValueError):
    """Raised when scene placement is missing, conflicting, or invalid."""


TRANSFORM_KEYS = ("x", "y", "z", "scale", "rotation")


def _apply_defaults(element: dict[str, Any], placement: dict[str, Any]) -> None:
    for key in TRANSFORM_KEYS:
        if key not in element and key in placement:
            element[key] = placement[key]


def _anchor_placement(raw: Any, anchor_id: str) -> dict[str, Any]:
    if isinstance(raw, list) and len(raw) >= 2:
        return {"x": raw[0], "y": raw[1]}
    if isinstance(raw, dict):
        return raw
    raise LayoutError(f"scene anchor {anchor_id!r} must be [x, y] or a transform object")


def resolve_scene_elements(
    elements: list[dict[str, Any]],
    template: AssetManifest | None,
) -> list[dict[str, Any]]:
    """Return copied elements with slots and scene anchors resolved to transforms."""
    resolved = deepcopy(elements)
    needs_template = any(
        element.get("slot") is not None
        or element.get("scene_anchor") is not None
        or element.get("auto_layout") is True
        for element in resolved
    )
    if template is None:
        if needs_template:
            raise LayoutError("slot, scene_anchor, and auto_layout require scene template_ref")
        return resolved
    if template.asset_type != "scene_template":
        raise LayoutError(f"layout manifest must be scene_template, got {template.asset_type!r}")

    data = template.data
    slots = data.get("slots", {})
    scene_anchors = data.get("anchors", {})
    auto_order = data.get("auto_order", list(slots))
    if not isinstance(auto_order, list):
        raise LayoutError(f"auto_order must be an array in {template.path}")
    occupied: dict[str, str] = {}

    for element in resolved:
        element_id = str(element.get("id", "unknown"))
        slot_id = element.get("slot")
        if slot_id == "auto" or element.get("auto_layout") is True:
            slot_id = next((candidate for candidate in auto_order if candidate not in occupied), None)
            if slot_id is None:
                raise LayoutError(f"no free auto-layout slot for element {element_id!r}")
            element["slot"] = slot_id

        if slot_id is not None:
            if not isinstance(slot_id, str) or slot_id not in slots:
                raise LayoutError(f"unknown slot {slot_id!r} for element {element_id!r}")
            if slot_id in occupied and not element.get("allow_overlap", False):
                raise LayoutError(
                    f"slot {slot_id!r} is already occupied by {occupied[slot_id]!r}; "
                    f"cannot place {element_id!r}"
                )
            placement = slots[slot_id]
            if not isinstance(placement, dict):
                raise LayoutError(f"slot {slot_id!r} must be a transform object")
            _apply_defaults(element, placement)
            occupied[slot_id] = element_id
            element["_resolved_slot"] = slot_id

        anchor_id = element.get("scene_anchor")
        if anchor_id is not None:
            if not isinstance(anchor_id, str) or anchor_id not in scene_anchors:
                raise LayoutError(f"unknown scene_anchor {anchor_id!r} for element {element_id!r}")
            _apply_defaults(element, _anchor_placement(scene_anchors[anchor_id], anchor_id))

    return resolved

