#!/usr/bin/env python3
"""Validate storyboard JSON without starting Blender."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.schema import StoryboardError, load_storyboard  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a motion-comic storyboard")
    parser.add_argument("storyboard")
    args = parser.parse_args()
    try:
        storyboard = load_storyboard(args.storyboard)
    except StoryboardError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    print(
        f"OK: {storyboard.title} | {len(storyboard.scenes)} scenes | "
        f"{storyboard.duration_seconds:.2f}s | {storyboard.total_frames} frames"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

