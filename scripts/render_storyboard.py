#!/usr/bin/env python3
"""Blender entry point: blender -b -P this_file -- storyboard.json [options]."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.builder import render_storyboard  # noqa: E402
from motion_comic.schema import StoryboardError  # noqa: E402


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a JSON motion comic with Blender")
    parser.add_argument("storyboard", help="Path to storyboard JSON")
    parser.add_argument("--output", default="output/motion-comic.mp4", help="Output MP4 path")
    parser.add_argument("--save-blend", help="Optionally save the generated .blend project")
    parser.add_argument("--no-render", action="store_true", help="Build without rendering (use with --save-blend)")
    return parser.parse_args(blender_args())


def main() -> int:
    args = parse_args()
    try:
        storyboard = render_storyboard(
            args.storyboard,
            args.output,
            save_blend=args.save_blend,
            render=not args.no_render,
        )
    except (StoryboardError, FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"Rendered {storyboard.title!r}: "
        f"{storyboard.duration_seconds:.2f}s / {storyboard.total_frames} frames -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

