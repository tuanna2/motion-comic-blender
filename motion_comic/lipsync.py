"""Load and validate Blender-independent mouth cue sidecars."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LipSyncError(ValueError):
    """Raised when a lip-sync sidecar is malformed."""


@dataclass(frozen=True)
class LipCue:
    target: str
    start: float
    end: float
    text: str = ""


def load_lip_sync(path: str | Path) -> dict[str, list[LipCue]]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise LipSyncError(f"lip-sync file not found: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LipSyncError(f"invalid lip-sync JSON at line {exc.lineno}: {exc.msg}") from exc
    if not isinstance(data, dict) or data.get("version") != "1.0":
        raise LipSyncError("lip-sync version must be '1.0'")
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, dict):
        raise LipSyncError("lip-sync scenes must be an object")

    scenes: dict[str, list[LipCue]] = {}
    for scene_id, raw_cues in raw_scenes.items():
        if not isinstance(scene_id, str) or not isinstance(raw_cues, list):
            raise LipSyncError("each lip-sync scene must contain an array of cues")
        cues: list[LipCue] = []
        for raw in raw_cues:
            if not isinstance(raw, dict):
                raise LipSyncError(f"scene {scene_id}: cue must be an object")
            target = raw.get("target")
            start = raw.get("start")
            end = raw.get("end")
            if not isinstance(target, str) or not target:
                raise LipSyncError(f"scene {scene_id}: cue target is required")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                raise LipSyncError(f"scene {scene_id}: cue start/end must be numbers")
            if float(start) < 0 or float(end) <= float(start):
                raise LipSyncError(f"scene {scene_id}: invalid cue range")
            cues.append(
                LipCue(
                    target=target,
                    start=float(start),
                    end=float(end),
                    text=str(raw.get("text", "")),
                )
            )
        scenes[scene_id] = sorted(cues, key=lambda cue: (cue.start, cue.end, cue.target))
    return scenes


def cue_frame_range(
    cue: LipCue,
    scene_start: int,
    scene_end: int,
    fps: int,
) -> tuple[int, int]:
    start = max(scene_start, scene_start + round(cue.start * fps))
    if start >= scene_end:
        return scene_end, scene_end
    end = min(scene_end, max(start + 1, scene_start + round(cue.end * fps)))
    return start, end
