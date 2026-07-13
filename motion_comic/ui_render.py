"""Persistent background render jobs for the local production UI."""

from __future__ import annotations

import json
import os
import re
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


_FRAME_PROGRESS = re.compile(r"Rendered/encoded frame\s+(\d+)/(\d+)")


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


class RenderCancelled(RuntimeError):
    """Raised internally after a user cancels a render job."""


@dataclass
class RenderJob:
    job_id: str
    directory: Path
    status: str = "queued"
    stage: str = "queued"
    progress_message: str = "Đang chờ"
    progress_percent: float = 0.0
    current_frame: int = 0
    total_frames: int = 0
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    return_code: int | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    video_path: Path | None = None
    blend_path: Path | None = None
    log_path: Path | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    process: subprocess.Popen[str] | None = field(default=None, repr=False)

    def log_tail(self, lines: int = 80) -> str:
        if self.log_path is None or not self.log_path.is_file():
            return ""
        try:
            content = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return ""
        return "\n".join(content[-lines:])

    def public(self, *, include_log: bool = True) -> dict[str, Any]:
        payload = {
            "job_id": self.job_id,
            "status": self.status,
            "stage": self.stage,
            "progress_message": self.progress_message,
            "progress_percent": round(self.progress_percent, 2),
            "current_frame": self.current_frame,
            "total_frames": self.total_frames,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "return_code": self.return_code,
            "error": self.error,
            "warnings": list(self.warnings),
            "can_cancel": self.status in {"queued", "running", "cancelling"},
            "can_resume": self.status in {"failed", "cancelled", "interrupted"},
            "video_ready": bool(self.video_path and self.video_path.is_file()),
            "blend_ready": bool(self.blend_path and self.blend_path.is_file()),
            "log_ready": bool(self.log_path and self.log_path.is_file()),
        }
        if include_log:
            payload["log_tail"] = self.log_tail()
        return payload


class RenderJobManager:
    def __init__(self, root: Path, series: SeriesRegistry):
        self.root = root.resolve()
        self.series = series
        self.jobs_root = self.root / "output" / "ui_jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, RenderJob] = {}
        self._lock = threading.RLock()
        self._load_existing_jobs()

    def _state_path(self, job: RenderJob) -> Path:
        return job.directory / "job_state.json"

    def _persist(self, job: RenderJob) -> None:
        payload = job.public(include_log=False)
        path = self._state_path(job)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)

    def _load_existing_jobs(self) -> None:
        for directory in sorted(self.jobs_root.iterdir() if self.jobs_root.is_dir() else []):
            state_path = directory / "job_state.json"
            request_path = directory / "request.json"
            if not directory.is_dir() or not state_path.is_file() or not request_path.is_file():
                continue
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                job_id = str(state["job_id"])
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
            status = str(state.get("status", "interrupted"))
            if status in {"queued", "running", "cancelling"}:
                status = "interrupted"
            job = RenderJob(
                job_id=job_id,
                directory=directory,
                status=status,
                stage=str(state.get("stage", status)),
                progress_message=(
                    "Tiến trình UI trước đã dừng; có thể Resume"
                    if status == "interrupted"
                    else str(state.get("progress_message", ""))
                ),
                progress_percent=float(state.get("progress_percent", 0)),
                current_frame=int(state.get("current_frame", 0)),
                total_frames=int(state.get("total_frames", 0)),
                created_at=str(state.get("created_at", _utc_now())),
                updated_at=str(state.get("updated_at", _utc_now())),
                return_code=state.get("return_code"),
                error=state.get("error"),
                warnings=list(state.get("warnings", [])),
                video_path=directory / "episode.mp4",
                blend_path=directory / "episode.blend",
                log_path=directory / "render.log",
            )
            self._jobs[job_id] = job
            self._persist(job)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [job.public() for job in jobs]

    def get(self, job_id: str) -> RenderJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _write_request(
        self,
        job: RenderJob,
        storyboard_payload: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        (job.directory / "request.json").write_text(
            json.dumps(
                {"storyboard": storyboard_payload, "options": options},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

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
        job = RenderJob(
            job_id=job_id,
            directory=directory,
            video_path=directory / "episode.mp4",
            blend_path=directory / "episode.blend",
            log_path=directory / "render.log",
        )
        job.warnings.extend(validation.warnings)
        options = {
            "with_tts": with_tts,
            "placeholder_missing_assets": placeholder_missing_assets,
            "keep_frames": keep_frames,
            "blender_bin": blender_bin,
        }
        self._write_request(job, storyboard_payload, options)
        with self._lock:
            self._jobs[job_id] = job
            self._persist(job)
        self._launch(job, storyboard_payload, options)
        return job

    def _launch(
        self,
        job: RenderJob,
        storyboard_payload: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        job.cancel_event.clear()
        thread = threading.Thread(
            target=self._run,
            args=(job, storyboard_payload, options),
            daemon=True,
            name=f"motion-comic-render-{job.job_id}",
        )
        thread.start()

    def resume(self, job_id: str) -> RenderJob:
        job = self.get(job_id)
        if job is None:
            raise ValueError("render job not found")
        if job.status not in {"failed", "cancelled", "interrupted"}:
            raise ValueError(f"job {job_id} cannot resume from state {job.status!r}")
        request = json.loads((job.directory / "request.json").read_text(encoding="utf-8"))
        storyboard = request.get("storyboard")
        options = request.get("options")
        if not isinstance(storyboard, dict) or not isinstance(options, dict):
            raise ValueError("persisted render request is invalid")
        self._update(
            job,
            status="queued",
            stage="queued",
            progress_message="Đã xếp hàng resume",
            error=None,
            return_code=None,
        )
        self._launch(job, storyboard, options)
        return job

    def cancel(self, job_id: str) -> RenderJob:
        job = self.get(job_id)
        if job is None:
            raise ValueError("render job not found")
        if job.status not in {"queued", "running", "cancelling"}:
            raise ValueError(f"job {job_id} cannot be cancelled from state {job.status!r}")
        job.cancel_event.set()
        self._update(job, status="cancelling", progress_message="Đang dừng tiến trình")
        process = job.process
        if process is not None and process.poll() is None:
            process.terminate()
        return job

    def _update(self, job: RenderJob, **values: Any) -> None:
        with self._lock:
            for key, value in values.items():
                setattr(job, key, value)
            job.updated_at = _utc_now()
            self._persist(job)

    def _run_command(self, job: RenderJob, command: list[str], log) -> None:
        if job.cancel_event.is_set():
            raise RenderCancelled("render cancelled")
        log.write("\n$ " + " ".join(command) + "\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=self.root,
            env={
                **os.environ,
                "MOTION_COMIC_ASSET_CACHE": str(self.root / "output" / ".asset-cache"),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        job.process = process
        try:
            assert process.stdout is not None
            for line in process.stdout:
                log.write(line)
                log.flush()
                stripped = line.strip()
                match = _FRAME_PROGRESS.search(stripped)
                if match:
                    current, total = int(match.group(1)), int(match.group(2))
                    self._update(
                        job,
                        current_frame=current,
                        total_frames=total,
                        progress_percent=round(12 + 87 * current / max(1, total), 2),
                        progress_message=stripped[-400:],
                    )
                elif stripped:
                    self._update(job, progress_message=stripped[-400:])
                if job.cancel_event.is_set() and process.poll() is None:
                    process.terminate()
            return_code = process.wait()
        finally:
            job.process = None
        if job.cancel_event.is_set():
            raise RenderCancelled("render cancelled")
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)

    def _run(
        self,
        job: RenderJob,
        storyboard_payload: dict[str, Any],
        options: dict[str, Any],
    ) -> None:
        try:
            self._update(
                job,
                status="running",
                stage="prepare",
                progress_message="Chuẩn bị storyboard",
                progress_percent=1,
                current_frame=0,
                total_frames=0,
            )
            prepared, warnings = prepare_storyboard_for_render(
                storyboard_payload,
                asset_root=self.root / "assets",
                placeholder_missing_assets=bool(options.get("placeholder_missing_assets", False)),
            )
            for warning in warnings:
                if warning not in job.warnings:
                    job.warnings.append(warning)
            storyboard_path = job.directory / "storyboard.json"
            storyboard_path.write_text(
                json.dumps(prepared, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            voice_dir = job.directory / "voice"
            audio_path = voice_dir / "voice.wav"
            lip_sync_path = voice_dir / "lip_sync.json"
            blender = discover_blender(options.get("blender_bin"))

            log_mode = "a" if job.log_path and job.log_path.exists() else "w"
            assert job.log_path is not None
            with job.log_path.open(log_mode, encoding="utf-8") as log:
                if log_mode == "a":
                    log.write(f"\n\n=== RESUME {job.updated_at} ===\n")
                if bool(options.get("placeholder_missing_assets", False)):
                    self._update(job, stage="assets", progress_message="Tạo asset placeholder", progress_percent=3)
                    self._run_command(
                        job,
                        [sys.executable, str(self.root / "scripts" / "generate_demo_assets.py")],
                        log,
                    )

                if bool(options.get("with_tts", True)):
                    self._update(job, stage="tts", progress_message="Tạo Edge-TTS (có cache)", progress_percent=5)
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

                self._update(job, stage="blender", progress_message="Render Blender", progress_percent=12)
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
                if bool(options.get("keep_frames", False)):
                    command.append("--keep-frames")
                if bool(options.get("with_tts", True)):
                    command.extend(["--audio", str(audio_path), "--lip-sync", str(lip_sync_path)])
                self._run_command(job, command, log)

            if not job.video_path or not job.video_path.is_file():
                raise RuntimeError("Blender finished but episode.mp4 was not created")
            self._update(
                job,
                status="completed",
                stage="completed",
                progress_message="Render hoàn tất",
                progress_percent=100,
                return_code=0,
            )
        except RenderCancelled:
            self._update(
                job,
                status="cancelled",
                stage="cancelled",
                progress_message="Đã hủy; có thể Resume để chạy lại với cache",
                error=None,
                return_code=None,
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
