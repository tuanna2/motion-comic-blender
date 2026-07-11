"""Edge-TTS planning, cache keys, word cues, and FFmpeg audio mixing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import Storyboard


EDGE_TTS_TICKS_PER_SECOND = 10_000_000


@dataclass(frozen=True)
class VoiceLine:
    scene_id: str
    subtitle_index: int
    target: str
    text: str
    start: float
    end: float
    global_start: float
    scene_duration: float
    voice: str
    rate: str
    volume: str
    pitch: str

    @property
    def cache_key(self) -> str:
        payload = json.dumps(
            {
                "text": self.text,
                "voice": self.voice,
                "rate": self.rate,
                "volume": self.volume,
                "pitch": self.pitch,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def collect_voice_lines(storyboard: Storyboard) -> list[VoiceLine]:
    """Collect subtitles that declare a speaker into deterministic TTS jobs."""
    lines: list[VoiceLine] = []
    scene_offset = 0.0
    defaults = storyboard.settings.tts
    for scene in storyboard.scenes:
        duration = float(scene["duration"])
        for index, subtitle in enumerate(scene.get("subtitles", [])):
            speaker = subtitle.get("speaker")
            if not isinstance(speaker, str) or not speaker:
                continue
            start = float(subtitle.get("start", 0))
            end = float(subtitle.get("end", duration))
            lines.append(
                VoiceLine(
                    scene_id=str(scene["id"]),
                    subtitle_index=index,
                    target=speaker,
                    text=str(subtitle["text"]),
                    start=start,
                    end=end,
                    global_start=scene_offset + start,
                    scene_duration=duration,
                    voice=str(subtitle.get("voice", defaults.voice)),
                    rate=str(subtitle.get("rate", defaults.rate)),
                    volume=str(subtitle.get("volume", defaults.volume)),
                    pitch=str(subtitle.get("pitch", defaults.pitch)),
                )
            )
        scene_offset += duration
    return lines


def word_boundaries_to_cues(line: VoiceLine, boundaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Edge-TTS 100-nanosecond word boundaries into mouth-open intervals."""
    cues: list[dict[str, Any]] = []
    for boundary in boundaries:
        offset = float(boundary.get("offset", 0)) / EDGE_TTS_TICKS_PER_SECOND
        duration = max(
            0.08,
            float(boundary.get("duration", 0)) / EDGE_TTS_TICKS_PER_SECOND,
        )
        start = line.start + offset
        end = min(line.scene_duration, start + max(0.08, duration * 0.72))
        if end > start:
            cues.append(
                {
                    "target": line.target,
                    "start": round(start, 4),
                    "end": round(end, 4),
                    "text": str(boundary.get("text", "")),
                }
            )
    if cues:
        return cues

    # Some voices/runtimes may omit word metadata. Keep a deterministic visual
    # fallback based on words, while still using the synthesized audio.
    words = line.text.split()
    if not words:
        return []
    available = max(0.1, min(line.end, line.scene_duration) - line.start)
    step = available / len(words)
    for index, word in enumerate(words):
        start = line.start + index * step
        end = min(line.scene_duration, start + max(0.08, step * 0.62))
        cues.append(
            {
                "target": line.target,
                "start": round(start, 4),
                "end": round(end, 4),
                "text": word,
            }
        )
    return cues


def ffmpeg_mix_command(
    ffmpeg_bin: str,
    inputs: list[tuple[Path, int]],
    duration: float,
    output_path: Path,
) -> list[str]:
    """Build a command that aligns individual speech files on the episode timeline."""
    if not inputs:
        raise ValueError("at least one voice input is required")
    command = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "warning"]
    for path, _delay_ms in inputs:
        command.extend(["-i", str(path)])

    filters: list[str] = []
    labels: list[str] = []
    for index, (_path, delay_ms) in enumerate(inputs):
        label = f"voice{index}"
        filters.append(f"[{index}:a]adelay={delay_ms}:all=1[{label}]")
        labels.append(f"[{label}]")
    filters.append(
        f"{''.join(labels)}amix=inputs={len(inputs)}:duration=longest:normalize=0,"
        f"apad,atrim=0:{duration:.3f}[audio]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[audio]",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
    )
    return command
