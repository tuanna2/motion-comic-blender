#!/usr/bin/env python3
"""Report whether the authoring add-ons required by the MMD build step are available."""

from __future__ import annotations

import bpy


def main() -> int:
    mmd_tools = hasattr(bpy.ops, "mmd_tools") and hasattr(bpy.ops.mmd_tools, "import_model")
    # MikuMikuRig operator names vary by release, so inspect enabled module names as well.
    enabled = set(bpy.context.preferences.addons.keys())
    mikumikurig = any("mikumiku" in module.lower() for module in enabled)
    print(f"MMD Tools: {'ready' if mmd_tools else 'missing'}")
    print(f"MikuMikuRig: {'enabled (optional)' if mikumikurig else 'not enabled (optional)'}")
    print("Runtime JSON/NLA rendering does not require either add-on after assets are compiled.")
    return 0 if mmd_tools else 2


if __name__ == "__main__":
    raise SystemExit(main())
