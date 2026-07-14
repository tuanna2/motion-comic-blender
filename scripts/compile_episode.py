#!/usr/bin/env python3
"""Compile an AI episode plan into deterministic renderer storyboard JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.compiler import EpisodeCompileError, compile_episode_plan  # noqa: E402
from motion_comic.series import SeriesError, load_series  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile episode_plan.json")
    parser.add_argument("plan")
    parser.add_argument("--series", default="series/urban_mystery/series.json")
    parser.add_argument("--assets", default="assets")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        asset_root = Path(args.assets).expanduser().resolve()
        compiled = compile_episode_plan(
            payload,
            load_series(args.series),
            asset_root=asset_root,
        )
        # Storyboard-relative paths break as soon as --output is outside the
        # repository root (the documented output/production location does so).
        compiled.setdefault("settings", {})["asset_library"] = str(asset_root)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(compiled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, EpisodeCompileError, SeriesError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Compiled storyboard: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
