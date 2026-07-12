"""Discover and activate Blender's externally installed MMD Tools add-on."""

from __future__ import annotations

from dataclasses import dataclass

import addon_utils
import bpy


@dataclass(frozen=True)
class MMDEnvironment:
    ready: bool
    enabled_module: str | None
    candidates: tuple[str, ...]
    errors: tuple[str, ...]


def operator_registered(name: str) -> bool:
    """Unlike hasattr(bpy.ops), get_rna_type fails when an operator is not registered."""
    namespace, operator = name.split(".", 1)
    try:
        getattr(getattr(bpy.ops, namespace), operator).get_rna_type()
        return True
    except (AttributeError, RuntimeError):
        return False


def _candidate_modules() -> list[str]:
    modules = addon_utils.modules(refresh=True)
    candidates = [module.__name__ for module in modules if "mmd_tools" in module.__name__.lower()]
    # Preserve preference keys too; Blender Extensions commonly use a bl_ext.* module id.
    candidates.extend(
        name
        for name in bpy.context.preferences.addons.keys()
        if "mmd_tools" in name.lower()
    )
    return list(dict.fromkeys(candidates))


def ensure_mmd_tools() -> MMDEnvironment:
    required = ("mmd_tools.import_model", "mmd_tools.import_vmd")
    if all(operator_registered(name) for name in required):
        return MMDEnvironment(True, None, tuple(_candidate_modules()), ())

    candidates = _candidate_modules()
    errors: list[str] = []
    for module_name in candidates:
        try:
            addon_utils.enable(module_name, default_set=False, persistent=False)
        except Exception as exc:  # Blender/add-on versions expose different exception types.
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
            continue
        if all(operator_registered(name) for name in required):
            return MMDEnvironment(True, module_name, tuple(candidates), tuple(errors))

    return MMDEnvironment(False, None, tuple(candidates), tuple(errors))


def mmd_tools_error(environment: MMDEnvironment) -> str:
    candidates = ", ".join(environment.candidates) or "none discovered"
    errors = "; ".join(environment.errors) or "no registration exception was reported"
    return (
        "MMD Tools operators are not registered in this background Blender process. "
        f"Discovered modules: {candidates}. Enable attempts: {errors}. "
        "Open this exact Blender installation, enable MMD Tools in Preferences > Add-ons/Extensions, "
        "save preferences, then retry."
    )
