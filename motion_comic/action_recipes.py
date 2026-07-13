"""Expand reusable cinematic action recipes into renderer motion entries."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .action_catalog import ACTION_CATALOG
from .registry import AssetRegistry


class ActionRecipeError(ValueError):
    """Raised when a recipe cannot be expanded safely."""


def _target(value: Any, invocation: dict[str, Any]) -> str:
    if value == "$actor":
        value = invocation.get("actor")
    elif value == "$target":
        value = invocation.get("target")
    if not isinstance(value, str) or not value:
        raise ActionRecipeError("recipe step target could not be resolved")
    return value


def expand_action_recipes(
    scene: dict[str, Any],
    registry: AssetRegistry,
    library_ref: str,
) -> dict[str, Any]:
    """Return a copied scene with ``recipes`` expanded into ordinary motions."""
    resolved = deepcopy(scene)
    invocations = resolved.pop("recipes", [])
    if not invocations:
        return resolved
    if not isinstance(invocations, list):
        raise ActionRecipeError(f"scene {scene.get('id')!r}: recipes must be an array")
    manifest = registry.resolve(library_ref, "action_recipe_library")
    catalog = manifest.data["recipes"]
    motions = list(resolved.get("motions", []))
    for invocation in invocations:
        if not isinstance(invocation, dict):
            raise ActionRecipeError("recipe invocation must be an object")
        recipe_key = invocation.get("recipe")
        definition = catalog.get(recipe_key)
        if not isinstance(definition, dict):
            raise ActionRecipeError(f"unknown action recipe {recipe_key!r}")
        start = float(invocation.get("start", 0.0))
        end = float(invocation.get("end", start + float(definition.get("duration", 1.0))))
        if end <= start:
            raise ActionRecipeError(f"recipe {recipe_key!r} end must be after start")
        duration = end - start
        invocation_params = invocation.get("params", {})
        if not isinstance(invocation_params, dict):
            raise ActionRecipeError(f"recipe {recipe_key!r} params must be an object")
        for step in definition["steps"]:
            if not isinstance(step, dict):
                raise ActionRecipeError(f"recipe {recipe_key!r} contains a non-object step")
            action = step.get("action")
            if action not in ACTION_CATALOG:
                raise ActionRecipeError(
                    f"recipe {recipe_key!r} uses unsupported action {action!r}"
                )
            relative_start = float(step.get("start", 0.0))
            relative_end = float(step.get("end", 1.0))
            if not 0 <= relative_start < relative_end <= 1:
                raise ActionRecipeError(
                    f"recipe {recipe_key!r} step ranges must be normalized from 0 to 1"
                )
            params = dict(step.get("params", {}))
            params.update(invocation_params)
            motions.append(
                {
                    "target": _target(step.get("target", "$actor"), invocation),
                    "action": action,
                    "start": round(start + relative_start * duration, 4),
                    "end": round(start + relative_end * duration, 4),
                    "params": params,
                }
            )
    resolved["motions"] = motions
    return resolved
