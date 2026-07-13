#!/usr/bin/env python3
"""Generate cached Edge-TTS speech, episode audio, and lip-sync cues."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.schema import StoryboardError, load_storyboard  # noqa: E402
from motion_comic.voice import (  # noqa: E402
    EDGE_TTS_TICKS_PER_SECOND,
    VoiceLine,
    collect_voice_lines,
    ffmpeg_mix_command,
    word_boundaries_to_cues,
)


class VoiceGenerationError(RuntimeError):
    """Raised when synthesis or audio assembly fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Edge-TTS audio and mouth cues")
    parser.add_argument("storyboard", help="Path to storyboard JSON")
    parser.add_argument("--output-dir", required=True, help="Directory for voice.wav and lip_sync.json")
    parser.add_argument("--cache-dir", default="output/.voice-cache", help="Reusable TTS cache")
    parser.add_argument("--retries", type=int, default=2, help="Retries per uncached line")
    parser.add_argument("--force", action="store_true", help="Ignore cached speech")
    return parser.parse_args()


async def synthesize_line(
    line: VoiceLine,
    cache_dir: Path,
    *,
    retries: int,
    force: bool,
) -> tuple[Path, list[dict]]:
    try:
        import edge_tts
    except ImportError as exc:
        raise VoiceGenerationError(
            "edge-tts is not installed. Run: python3 -m pip install -e '.[tts]'"
        ) from exc

    audio_path = cache_dir / f"{line.cache_key}.mp3"
    metadata_path = cache_dir / f"{line.cache_key}.json"
    if not force and audio_path.is_file() and metadata_path.is_file():
        boundaries = json.loads(metadata_path.read_text(encoding="utf-8"))
        if isinstance(boundaries, list):
            return audio_path, boundaries

    cache_dir.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(max(0, retries) + 1):
        temp_audio = audio_path.with_suffix(f".attempt-{attempt}.mp3")
        temp_metadata = metadata_path.with_suffix(f".attempt-{attempt}.json")
        boundaries: list[dict] = []
        try:
            communicate = edge_tts.Communicate(
                line.text,
                line.voice,
                rate=line.rate,
                volume=line.volume,
                pitch=line.pitch,
            )
            with temp_audio.open("wb") as output:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        output.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        boundaries.append(
                            {
                                "offset": int(chunk["offset"]),
                                "duration": int(chunk["duration"]),
                                "text": str(chunk.get("text", "")),
                            }
                        )
            if not temp_audio.is_file() or temp_audio.stat().st_size == 0:
                raise VoiceGenerationError("Edge-TTS returned no audio")
            temp_metadata.write_text(
                json.dumps(boundaries, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temp_audio.replace(audio_path)
            temp_metadata.replace(metadata_path)
            return audio_path, boundaries
        except Exception as exc:  # Edge-TTS exposes several transport exceptions.
            last_error = exc
            temp_audio.unlink(missing_ok=True)
            temp_metadata.unlink(missing_ok=True)
            if attempt < retries:
                await asyncio.sleep(0.5 * (attempt + 1))
    raise VoiceGenerationError(
        f"failed to synthesize scene {line.scene_id!r} subtitle {line.subtitle_index}: {last_error}"
    )


async def generate(args: argparse.Namespace) -> tuple[Path, Path, int, int]:
    storyboard = load_storyboard(args.storyboard)
    lines = collect_voice_lines(storyboard)
    if not lines:
        raise VoiceGenerationError("no subtitles declare a speaker; nothing to synthesize")

    output_dir = Path(args.output_dir).expanduser().resolve()
    cache_dir = Path(args.cache_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    scenes: dict[str, list[dict]] = {str(scene["id"]): [] for scene in storyboard.scenes}
    mix_inputs: list[tuple[Path, int]] = []
    cache_hits = 0

    for line in lines:
        cached_audio = cache_dir / f"{line.cache_key}.mp3"
        cached_metadata = cache_dir / f"{line.cache_key}.json"
        was_cached = not args.force and cached_audio.is_file() and cached_metadata.is_file()
        audio_path, boundaries = await synthesize_line(
            line,
            cache_dir,
            retries=args.retries,
            force=args.force,
        )
        cache_hits += int(was_cached)
        scenes[line.scene_id].extend(word_boundaries_to_cues(line, boundaries))
        mix_inputs.append((audio_path, round(line.global_start * 1000)))
        if boundaries:
            spoken_duration = max(
                (float(item["offset"]) + float(item["duration"]))
                / EDGE_TTS_TICKS_PER_SECOND
                for item in boundaries
            )
            if line.start + spoken_duration > line.end + 0.05:
                print(
                    f"WARNING: scene {line.scene_id!r} subtitle {line.subtitle_index} "
                    f"speech exceeds its subtitle end by "
                    f"{line.start + spoken_duration - line.end:.2f}s",
                    file=sys.stderr,
                )

    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise VoiceGenerationError("FFmpeg CLI was not found. On macOS: brew install ffmpeg")
    audio_output = output_dir / "voice.wav"
    command = ffmpeg_mix_command(
        ffmpeg_bin,
        mix_inputs,
        storyboard.duration_seconds,
        audio_output,
    )
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise VoiceGenerationError(f"FFmpeg voice mix failed with exit code {exc.returncode}") from exc

    lip_sync_output = output_dir / "lip_sync.json"
    lip_sync_output.write_text(
        json.dumps(
            {
                "version": "1.0",
                "fps": storyboard.settings.fps,
                "audio": audio_output.name,
                "scenes": scenes,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return audio_output, lip_sync_output, len(lines), cache_hits


def main() -> int:
    args = parse_args()
    try:
        audio, lip_sync, line_count, cache_hits = asyncio.run(generate(args))
    except (StoryboardError, VoiceGenerationError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Generated {line_count} voice lines ({cache_hits} cache hits)")
    print(f"Audio: {audio}")
    print(f"Lip sync: {lip_sync}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
