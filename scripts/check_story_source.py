#!/usr/bin/env python3
"""Validate a story_source JSON pasted back from an AI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.series import SeriesError, load_series, validate_story_source  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-created story source JSON")
    parser.add_argument("story_source")
    parser.add_argument("--series", default="series/urban_mystery/series.json")
    args = parser.parse_args()
    try:
        series = load_series(args.series)
        payload = json.loads(Path(args.story_source).read_text(encoding="utf-8"))
        result = validate_story_source(payload, series)
    except (SeriesError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    if not result.valid:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        f"OK: {payload['title']} | {result.word_count} words | "
        f"estimated {result.estimated_minutes:.1f} minutes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
