"""Encode Blender frames with external FFmpeg, from disk or a live PNG pipe."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable


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


def ffmpeg_pipe_command(
    ffmpeg_bin: str,
    fps: int,
    output_path: Path,
    *,
    audio_path: Path | None = None,
) -> list[str]:
    """Build an FFmpeg command that reads concatenated PNG images from stdin."""
    command = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "image2pipe",
        "-framerate",
        str(fps),
        "-vcodec",
        "png",
        "-i",
        "pipe:0",
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


def encode_png_stream(
    frames: Iterable[bytes],
    fps: int,
    output_path: Path,
    *,
    audio_path: Path | None = None,
) -> None:
    """Write rendered PNG bytes directly to FFmpeg without retaining a frame directory."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise EncodingError("FFmpeg CLI was not found. On macOS: brew install ffmpeg")
    if audio_path is not None and not audio_path.is_file():
        raise EncodingError(f"audio file not found: {audio_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = ffmpeg_pipe_command(ffmpeg_bin, fps, output_path, audio_path=audio_path)
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        if process.stdin is None:
            raise EncodingError("FFmpeg stdin pipe could not be opened")
        for frame in frames:
            process.stdin.write(frame)
        process.stdin.close()
        return_code = process.wait()
    except (BrokenPipeError, OSError) as exc:
        process.kill()
        process.wait()
        raise EncodingError("FFmpeg stopped while Blender was streaming frames") from exc
    if return_code != 0:
        raise EncodingError(f"FFmpeg live encoding failed with exit code {return_code}")


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
