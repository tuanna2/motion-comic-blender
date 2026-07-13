#!/usr/bin/env python3
"""Report whether the authoring add-ons required by the MMD build step are available."""

from __future__ import annotations

import bpy

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.mmd_environment import ensure_mmd_tools, mmd_tools_error  # noqa: E402


def main() -> int:
    environment = ensure_mmd_tools()
    # MikuMikuRig operator names vary by release, so inspect enabled module names as well.
    enabled = set(bpy.context.preferences.addons.keys())
    mikumikurig = any("mikumiku" in module.lower() for module in enabled)
    print(f"MMD Tools: {'ready' if environment.ready else 'missing/not registered'}")
    print(f"MMD module candidates: {', '.join(environment.candidates) or 'none'}")
    if environment.enabled_module:
        print(f"Enabled for this process: {environment.enabled_module}")
    print(f"MikuMikuRig: {'enabled (optional)' if mikumikurig else 'not enabled (optional)'}")
    print("Runtime JSON/NLA rendering does not require either add-on after assets are compiled.")
    if not environment.ready:
        print(mmd_tools_error(environment))
    return 0 if environment.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
