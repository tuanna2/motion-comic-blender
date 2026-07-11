"""Encode Blender image sequences with an external FFmpeg executable."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class EncodingError(RuntimeError):
    """Raised when PNG frames cannot be encoded into a video."""


def ffmpeg_command(
    ffmpeg_bin: str,
    frames_pattern: Path,
    fps: int,
    output_path: Path,
    *,
    start_number: int = 1,
    audio_path: Path | None = None,
) -> list[str]:
    command = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-framerate",
        str(fps),
        "-start_number",
        str(start_number),
        "-i",
        str(frames_pattern),
    ]
    if audio_path is not None:
        command.extend(["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0"])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
        ]
    )
    if audio_path is not None:
        command.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
    command.append(str(output_path))
    return command


def encode_png_sequence(
    frames_dir: Path,
    fps: int,
    output_path: Path,
    *,
    audio_path: Path | None = None,
) -> None:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise EncodingError(
            "FFmpeg CLI was not found. Frames were kept at "
            f"{frames_dir}. On macOS install it with: brew install ffmpeg"
        )
    pattern = frames_dir / "frame_%04d.png"
    if audio_path is not None and not audio_path.is_file():
        raise EncodingError(f"audio file not found: {audio_path}")
    command = ffmpeg_command(ffmpeg_bin, pattern, fps, output_path, audio_path=audio_path)
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise EncodingError(
            f"FFmpeg failed with exit code {exc.returncode}; PNG frames were kept at {frames_dir}"
        ) from exc
