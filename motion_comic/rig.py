"""Pure-Python validation and topological ordering for 2D rig parts."""

from __future__ import annotations

from typing import Any


class RigError(ValueError):
    """Raised when a layered character contains an invalid joint hierarchy."""


def order_rig_parts(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate part IDs/parents and return parents before their children."""
    by_id: dict[str, dict[str, Any]] = {}
    for part in parts:
        part_id = part.get("id")
        if not isinstance(part_id, str) or not part_id:
            raise RigError("every rig part requires a non-empty id")
        if part_id in by_id:
            raise RigError(f"duplicate rig part id {part_id!r}")
        by_id[part_id] = part

    ordered: list[dict[str, Any]] = []
    state: dict[str, int] = {}

    def visit(part_id: str) -> None:
        status = state.get(part_id, 0)
        if status == 1:
            raise RigError(f"cyclic rig parent relationship at {part_id!r}")
        if status == 2:
            return
        state[part_id] = 1
        part = by_id[part_id]
        parent = part.get("parent")
        if parent is not None:
            if not isinstance(parent, str) or parent not in by_id:
                raise RigError(f"part {part_id!r} references unknown parent {parent!r}")
            if "joint" not in by_id[parent]:
                raise RigError(f"parent part {parent!r} must define a joint controller")
            visit(parent)
        state[part_id] = 2
        ordered.append(part)

    for part_id in by_id:
        visit(part_id)
    return ordered


def point2(value: Any, field_name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) < 2:
        raise RigError(f"{field_name} must contain x and y")
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise RigError(f"{field_name} coordinates must be numbers") from exc

