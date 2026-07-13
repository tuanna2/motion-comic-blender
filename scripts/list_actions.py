#!/usr/bin/env python3
"""Print the semantic action catalog for humans or LLM storyboard generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.action_catalog import ACTION_CATALOG, CATEGORY_KEYS  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="List supported storyboard actions")
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--category", choices=tuple(CATEGORY_KEYS))
    args = parser.parse_args()
    categories = (
        {args.category: CATEGORY_KEYS[args.category]}
        if args.category
        else CATEGORY_KEYS
    )
    if args.format == "json":
        print(
            json.dumps(
                {
                    "count": len(ACTION_CATALOG),
                    "categories": {category: list(keys) for category, keys in categories.items()},
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.format == "markdown":
        print(f"# Action catalog ({len(ACTION_CATALOG)})\n")
        for category, keys in categories.items():
            print(f"## {category}\n")
            print(", ".join(f"`{key}`" for key in keys))
            print()
    else:
        for category, keys in categories.items():
            print(f"{category} ({len(keys)}): {' '.join(keys)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
