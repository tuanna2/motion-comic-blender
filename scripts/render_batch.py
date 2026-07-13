#!/usr/bin/env python3
"""Render many storyboard episodes with resume, retries, cache, and status."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.batch import (  # noqa: E402
    BatchError,
    BatchJob,
    build_job_commands,
    empty_status,
    load_batch,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a production batch of motion comics")
    parser.add_argument("manifest", help="Batch JSON manifest")
    parser.add_argument(
        "--blender-bin",
        default=os.environ.get("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender"),
    )
    parser.add_argument("--python-bin", default=sys.executable)
    parser.add_argument("--workers", type=int, default=1, help="Parallel Blender processes")
    parser.add_argument("--force", action="store_true", help="Render existing outputs again")
    parser.add_argument("--force-voice", action="store_true", help="Bypass the voice cache")
    parser.add_argument("--dry-run", action="store_true", help="Print jobs without running them")
    return parser.parse_args()


def save_status(path: Path, status: dict, lock: threading.Lock) -> None:
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)


def run_job(job: BatchJob, plan, args, status: dict, lock: threading.Lock) -> tuple[str, str]:
    record = status["episodes"][job.job_id]
    if not job.enabled:
        record["state"] = "disabled"
        save_status(plan.status_path, status, lock)
        return job.job_id, "disabled"
    if job.output.is_file() and not args.force:
        record["state"] = "skipped"
        record["reason"] = "output_exists"
        save_status(plan.status_path, status, lock)
        return job.job_id, "skipped"
    if record.get("state") == "completed" and not args.force:
        record["state"] = "pending"

    commands = build_job_commands(
        plan,
        job,
        python_bin=args.python_bin,
        blender_bin=args.blender_bin,
        project_root=ROOT,
        force_voice=args.force_voice,
    )
    if args.dry_run:
        record["state"] = "dry_run"
        record["commands"] = commands
        save_status(plan.status_path, status, lock)
        return job.job_id, "dry_run"

    job.output.parent.mkdir(parents=True, exist_ok=True)
    last_error = ""
    for attempt in range(1, plan.retries + 2):
        record["state"] = "running"
        record["attempts"] = attempt
        record["started_at"] = datetime.now(timezone.utc).isoformat()
        save_status(plan.status_path, status, lock)
        try:
            for command_index, command in enumerate(commands, start=1):
                record["stage"] = f"command_{command_index}_of_{len(commands)}"
                record["command"] = command
                save_status(plan.status_path, status, lock)
                subprocess.run(
                    command,
                    cwd=ROOT,
                    check=True,
                    env={
                        **os.environ,
                        "MOTION_COMIC_ASSET_CACHE": str(plan.asset_cache_dir),
                    },
                )
            record["state"] = "completed"
            record["finished_at"] = datetime.now(timezone.utc).isoformat()
            save_status(plan.status_path, status, lock)
            return job.job_id, "completed"
        except subprocess.CalledProcessError as exc:
            last_error = f"command exited with {exc.returncode}: {' '.join(exc.cmd)}"
            record["last_error"] = last_error
            record["state"] = "retrying" if attempt <= plan.retries else "failed"
            save_status(plan.status_path, status, lock)
    return job.job_id, f"failed: {last_error}"


def main() -> int:
    args = parse_args()
    try:
        plan = load_batch(args.manifest)
    except BatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.workers < 1 or args.workers > 8:
        print("ERROR: --workers must be between 1 and 8", file=sys.stderr)
        return 2
    if not args.dry_run:
        if not Path(args.blender_bin).is_file():
            print(f"ERROR: Blender not found: {args.blender_bin}", file=sys.stderr)
            return 2
        if not shutil.which("ffmpeg"):
            print("ERROR: FFmpeg CLI was not found", file=sys.stderr)
            return 2
        subprocess.run([args.python_bin, str(ROOT / "scripts/generate_demo_assets.py")], cwd=ROOT, check=True)

    status = empty_status(plan)
    if plan.status_path.is_file() and not args.force:
        try:
            previous = json.loads(plan.status_path.read_text(encoding="utf-8"))
            previous_records = previous.get("episodes", {})
            for job_id, record in status["episodes"].items():
                if isinstance(previous_records.get(job_id), dict):
                    record.update(previous_records[job_id])
                    if record.get("state") in {"running", "retrying"}:
                        record["state"] = "interrupted"
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
    lock = threading.Lock()
    save_status(plan.status_path, status, lock)
    failures = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_job, job, plan, args, status, lock) for job in plan.jobs]
        for future in as_completed(futures):
            job_id, state = future.result()
            print(f"{job_id}: {state}")
            failures += int(state.startswith("failed"))
    print(f"Status: {plan.status_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
