"""Batch manifest loading and deterministic episode command planning."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BatchError(ValueError):
    """Raised when a production batch manifest is invalid."""


@dataclass(frozen=True)
class BatchJob:
    job_id: str
    storyboard: Path
    output: Path
    voice: bool = True
    save_blend: bool = False
    enabled: bool = True


@dataclass(frozen=True)
class BatchPlan:
    source_path: Path
    output_dir: Path
    cache_dir: Path
    status_path: Path
    retries: int
    jobs: tuple[BatchJob, ...]


def load_batch(path: str | Path) -> BatchPlan:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise BatchError(f"batch manifest not found: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BatchError(f"invalid batch JSON at line {exc.lineno}: {exc.msg}") from exc
    if not isinstance(data, dict) or data.get("version") != "1.0":
        raise BatchError("batch version must be '1.0'")
    root = source.parent
    output_dir = (root / str(data.get("output_dir", "../output/batch"))).resolve()
    cache_dir = (root / str(data.get("cache_dir", "../output/.voice-cache"))).resolve()
    status_path = output_dir / str(data.get("status_file", "batch_status.json"))
    retries = data.get("retries", 1)
    if not isinstance(retries, int) or retries < 0 or retries > 10:
        raise BatchError("batch retries must be an integer between 0 and 10")
    raw_jobs = data.get("episodes")
    if not isinstance(raw_jobs, list) or not raw_jobs:
        raise BatchError("batch episodes must be a non-empty array")

    jobs: list[BatchJob] = []
    ids: set[str] = set()
    for index, raw in enumerate(raw_jobs):
        if not isinstance(raw, dict):
            raise BatchError(f"batch episode {index} must be an object")
        job_id = raw.get("id")
        storyboard_value = raw.get("storyboard")
        if not isinstance(job_id, str) or not job_id:
            raise BatchError(f"batch episode {index} id is required")
        if job_id in ids:
            raise BatchError(f"duplicate batch episode id {job_id!r}")
        if not isinstance(storyboard_value, str) or not storyboard_value:
            raise BatchError(f"batch episode {job_id!r} storyboard is required")
        storyboard = (root / storyboard_value).resolve()
        if not storyboard.is_file():
            raise BatchError(f"batch episode {job_id!r} storyboard not found: {storyboard}")
        output_value = raw.get("output", f"{job_id}.mp4")
        if not isinstance(output_value, str) or not output_value.endswith(".mp4"):
            raise BatchError(f"batch episode {job_id!r} output must be an .mp4 path")
        jobs.append(
            BatchJob(
                job_id=job_id,
                storyboard=storyboard,
                output=(output_dir / output_value).resolve(),
                voice=bool(raw.get("voice", True)),
                save_blend=bool(raw.get("save_blend", False)),
                enabled=bool(raw.get("enabled", True)),
            )
        )
        ids.add(job_id)
    return BatchPlan(source, output_dir, cache_dir, status_path, retries, tuple(jobs))


def job_voice_dir(plan: BatchPlan, job: BatchJob) -> Path:
    return plan.output_dir / ".voice" / job.job_id


def build_job_commands(
    plan: BatchPlan,
    job: BatchJob,
    *,
    python_bin: str,
    blender_bin: str,
    project_root: Path,
    force_voice: bool = False,
) -> list[list[str]]:
    commands: list[list[str]] = []
    voice_dir = job_voice_dir(plan, job)
    if job.voice:
        voice_command = [
            python_bin,
            str(project_root / "scripts/generate_voice.py"),
            str(job.storyboard),
            "--output-dir",
            str(voice_dir),
            "--cache-dir",
            str(plan.cache_dir),
        ]
        if force_voice:
            voice_command.append("--force")
        commands.append(voice_command)

    render_command = [
        blender_bin,
        "-b",
        "-P",
        str(project_root / "scripts/render_storyboard.py"),
        "--",
        str(job.storyboard),
        "--output",
        str(job.output),
    ]
    if job.save_blend:
        render_command.extend(["--save-blend", str(job.output.with_suffix(".blend"))])
    if job.voice:
        render_command.extend(
            [
                "--audio",
                str(voice_dir / "voice.wav"),
                "--lip-sync",
                str(voice_dir / "lip_sync.json"),
            ]
        )
    commands.append(render_command)
    return commands


def empty_status(plan: BatchPlan) -> dict[str, Any]:
    return {
        "version": "1.0",
        "batch": str(plan.source_path),
        "episodes": {
            job.job_id: {"state": "pending", "attempts": 0, "output": str(job.output)}
            for job in plan.jobs
        },
    }
