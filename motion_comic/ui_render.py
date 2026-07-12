"""Background render jobs used by the local story creator UI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .series import SeriesRegistry
from .storyboard_ai import prepare_storyboard_for_render, validate_storyboard_payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def discover_blender(explicit: str | None = None) -> str:
    candidates = [
        explicit,
        os.environ.get("BLENDER_BIN"),
        shutil.which("blender"),
        "/Applications/Blender.app/Contents/MacOS/Blender",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().is_file():
            return str(Path(candidate).expanduser().resolve())
    raise FileNotFoundError(
        "Blender executable not found. Install Blender or set BLENDER_BIN; "
        "on macOS the default path is /Applications/Blender.app/Contents/MacOS/Blender"
    )


@dataclass
class RenderJob:
    job_id: str
    directory: Path
    status: str = "queued"
    stage: str = "queued"
    progress_message: str = "Đang chờ"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    return_code: int | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    video_path: Path | None = None
    blend_path: Path | None = None
    log_path: Path | None = None

    def public(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "stage": self.stage,
            "progress_message": self.progress_message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "return_code": self.return_code,
            "error": self.error,
            "warnings": list(self.warnings),
            "video_ready": bool(self.video_path and self.video_path.is_file()),
            "blend_ready": bool(self.blend_path and self.blend_path.is_file()),
            "log_ready": bool(self.log_path and self.log_path.is_file()),
        }


class RenderJobManager:
    def __init__(self, root: Path, series: SeriesRegistry):
        self.root = root.resolve()
        self.series = series
        self.jobs_root = self.root / "output" / "ui_jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, RenderJob] = {}
        self._lock = threading.Lock()

    def get(self, job_id: str) -> RenderJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def start(
        self,
        storyboard_payload: dict[str, Any],
        *,
        story_source: dict[str, Any] | None,
        with_tts: bool,
        placeholder_missing_assets: bool,
        keep_frames: bool,
        blender_bin: str | None,
    ) -> RenderJob:
        validation = validate_storyboard_payload(
            storyboard_payload,
            self.series,
            story_source=story_source,
            asset_root=self.root / "assets",
        )
        if not validation.valid:
            raise ValueError("; ".join(validation.errors))

        job_id = uuid.uuid4().hex[:12]
        directory = self.jobs_root / job_id
        directory.mkdir(parents=True, exist_ok=False)
        job = RenderJob(job_id=job_id, directory=directory)
        job.warnings.extend(validation.warnings)
        job.log_path = directory / "render.log"
        job.video_path = directory / "episode.mp4"
        job.blend_path = directory / "episode.blend"
        with self._lock:
            self._jobs[job_id] = job

        thread = threading.Thread(
            target=self._run,
            args=(
                job,
                storyboard_payload,
                with_tts,
                placeholder_missing_assets,
                keep_frames,
                blender_bin,
            ),
            daemon=True,
            name=f"motion-comic-render-{job_id}",
        )
        thread.start()
        return job

    def _update(self, job: RenderJob, **values: Any) -> None:
        with self._lock:
            for key, value in values.items():
                setattr(job, key, value)
            job.updated_at = _utc_now()

    def _run_command(self, job: RenderJob, command: list[str], log) -> None:
        log.write("\n$ " + " ".join(command) + "\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            stripped = line.strip()
            if stripped:
                self._update(job, progress_message=stripped[-400:])
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)

    def _run(
        self,
        job: RenderJob,
        storyboard_payload: dict[str, Any],
        with_tts: bool,
        placeholder_missing_assets: bool,
        keep_frames: bool,
        blender_bin: str | None,
    ) -> None:
        try:
            self._update(job, status="running", stage="prepare", progress_message="Chuẩn bị storyboard")
            prepared, warnings = prepare_storyboard_for_render(
                storyboard_payload,
                asset_root=self.root / "assets",
                placeholder_missing_assets=placeholder_missing_assets,
            )
            job.warnings.extend(item for item in warnings if item not in job.warnings)
            storyboard_path = job.directory / "storyboard.json"
            storyboard_path.write_text(
                json.dumps(prepared, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            voice_dir = job.directory / "voice"
            audio_path = voice_dir / "voice.wav"
            lip_sync_path = voice_dir / "lip_sync.json"
            blender = discover_blender(blender_bin)

            with job.log_path.open("w", encoding="utf-8") as log:
                if with_tts:
                    self._update(job, stage="tts", progress_message="Đang tạo Edge-TTS")
                    self._run_command(
                        job,
                        [
                            sys.executable,
                            str(self.root / "scripts" / "generate_voice.py"),
                            str(storyboard_path),
                            "--output-dir",
                            str(voice_dir),
                            "--cache-dir",
                            str(self.root / "output" / ".voice-cache"),
                        ],
                        log,
                    )

                self._update(job, stage="blender", progress_message="Đang render Blender")
                command = [
                    blender,
                    "-b",
                    "-P",
                    str(self.root / "scripts" / "render_storyboard.py"),
                    "--",
                    str(storyboard_path),
                    "--output",
                    str(job.video_path),
                    "--save-blend",
                    str(job.blend_path),
                ]
                if keep_frames:
                    command.append("--keep-frames")
                if with_tts:
                    command.extend(["--audio", str(audio_path), "--lip-sync", str(lip_sync_path)])
                self._run_command(job, command, log)

            if not job.video_path.is_file():
                raise RuntimeError("Blender finished but episode.mp4 was not created")
            self._update(
                job,
                status="completed",
                stage="completed",
                progress_message="Render hoàn tất",
                return_code=0,
            )
        except Exception as exc:
            self._update(
                job,
                status="failed",
                stage="failed",
                progress_message="Render thất bại",
                error=str(exc),
                return_code=getattr(exc, "returncode", 1),
            )

    def resolve_file(self, job_id: str, kind: str) -> Path | None:
        job = self.get(job_id)
        if job is None:
            return None
        mapping = {
            "video": job.video_path,
            "blend": job.blend_path,
            "log": job.log_path,
            "storyboard": job.directory / "storyboard.json",
        }
        path = mapping.get(kind)
        return path if path and path.is_file() else None
