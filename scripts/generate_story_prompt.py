#!/usr/bin/env python3
"""Generate a copy/paste AI prompt for a complete 10-30 minute story."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.series import SeriesError, load_series  # noqa: E402
from motion_comic.story_prompt import build_story_creation_prompt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an AI story-creation prompt")
    parser.add_argument(
        "--series",
        default="series/urban_mystery/series.json",
        help="Series registry JSON",
    )
    parser.add_argument("--minutes", type=int, default=15, help="Target TTS duration, 10-30")
    parser.add_argument("--genre", default="đô thị, bí ẩn, trùng sinh")
    parser.add_argument(
        "--narration-mode",
        choices=("first_person", "third_person"),
        default="first_person",
    )
    parser.add_argument("--protagonist", default="char_minh_khang")
    parser.add_argument("--premise", default="")
    parser.add_argument("--output", help="Write prompt to a UTF-8 file instead of stdout")
    args = parser.parse_args()
    try:
        series = load_series(args.series)
        prompt = build_story_creation_prompt(
            series,
            minutes=args.minutes,
            genre=args.genre,
            narration_mode=args.narration_mode,
            protagonist_id=args.protagonist,
            premise=args.premise,
        )
    except (SeriesError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(prompt, encoding="utf-8")
        print(output)
    else:
        print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
