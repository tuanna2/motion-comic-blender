#!/usr/bin/env python3
"""Local UI for story creation, AI storyboard compilation, and Blender rendering."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.series import SeriesError, load_series, validate_story_source  # noqa: E402
from motion_comic.compiler import compile_episode_plan  # noqa: E402
from motion_comic.story_prompt import build_story_creation_prompt  # noqa: E402
from motion_comic.storyboard_ai import (  # noqa: E402
    build_storyboard_creation_prompt,
    validate_storyboard_payload,
)
from motion_comic.ui_render import RenderJobManager  # noqa: E402


MAX_REQUEST_BYTES = 30_000_000


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


def parse_json_text(value: Any, field_name: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be JSON text or an object")
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name} root must be an object")
    return payload


def make_handler(series_path: Path, html_path: Path):
    series = load_series(series_path)
    html = html_path.read_bytes()
    render_jobs = RenderJobManager(ROOT, series)

    class StoryCreatorHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("invalid request size")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("request body must be an object")
            return body

        def _serve_file(self, path: Path) -> None:
            size = path.stat().st_size
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", f'inline; filename="{path.name}"')
            self.end_headers()
            with path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    self.wfile.write(chunk)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            if path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if path == "/api/series":
                json_response(self, 200, series.data)
                return
            if path == "/api/render-status":
                job_id = query.get("job_id", [""])[0]
                job = render_jobs.get(job_id)
                if job is None:
                    json_response(self, 404, {"error": "render job not found"})
                else:
                    json_response(self, 200, job.public())
                return
            if path == "/api/render-jobs":
                json_response(self, 200, {"jobs": render_jobs.list()})
                return
            if path == "/api/render-file":
                job_id = query.get("job_id", [""])[0]
                kind = query.get("kind", ["video"])[0]
                file_path = render_jobs.resolve_file(job_id, kind)
                if file_path is None:
                    json_response(self, 404, {"error": "render file not found"})
                else:
                    self._serve_file(file_path)
                return
            json_response(self, 404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                body = self._body()
                path = urlparse(self.path).path
                if path == "/api/prompt":
                    prompt = build_story_creation_prompt(
                        series,
                        minutes=int(body.get("minutes", 15)),
                        genre=str(body.get("genre", "")),
                        narration_mode=str(body.get("narration_mode", "first_person")),
                        protagonist_id=str(body.get("protagonist_id", "char_minh_khang")),
                        premise=str(body.get("premise", "")),
                    )
                    json_response(self, 200, {"prompt": prompt})
                    return

                if path == "/api/validate":
                    payload = parse_json_text(body.get("story_source"), "story_source")
                    result = validate_story_source(payload, series)
                    json_response(
                        self,
                        200,
                        {
                            "valid": result.valid,
                            "errors": list(result.errors),
                            "warnings": list(result.warnings),
                            "word_count": result.word_count,
                            "estimated_minutes": round(result.estimated_minutes, 2),
                            "story_source": payload if result.valid else None,
                        },
                    )
                    return

                if path == "/api/storyboard-prompt":
                    story_source = parse_json_text(body.get("story_source"), "story_source")
                    prompt = build_storyboard_creation_prompt(story_source, series)
                    json_response(self, 200, {"prompt": prompt})
                    return

                if path == "/api/validate-storyboard":
                    plan = parse_json_text(body.get("storyboard"), "storyboard")
                    storyboard = compile_episode_plan(plan, series, asset_root=ROOT / "assets")
                    raw_story_source = body.get("story_source")
                    story_source = (
                        parse_json_text(raw_story_source, "story_source")
                        if raw_story_source not in (None, "")
                        else None
                    )
                    result = validate_storyboard_payload(
                        storyboard,
                        series,
                        story_source=story_source,
                        asset_root=ROOT / "assets",
                    )
                    json_response(
                        self,
                        200,
                        {
                            "valid": result.valid,
                            "errors": list(result.errors),
                            "warnings": list(result.warnings),
                            "scene_count": result.scene_count,
                            "duration_seconds": round(result.duration_seconds, 2),
                            "subtitle_count": result.subtitle_count,
                            "text_coverage": round(result.text_coverage * 100, 2),
                            "storyboard": storyboard if result.valid else None,
                        },
                    )
                    return

                if path == "/api/render":
                    plan = parse_json_text(body.get("storyboard"), "storyboard")
                    storyboard = compile_episode_plan(plan, series, asset_root=ROOT / "assets")
                    raw_story_source = body.get("story_source")
                    story_source = (
                        parse_json_text(raw_story_source, "story_source")
                        if raw_story_source not in (None, "")
                        else None
                    )
                    job = render_jobs.start(
                        storyboard,
                        story_source=story_source,
                        with_tts=bool(body.get("with_tts", True)),
                        placeholder_missing_assets=bool(
                            body.get("placeholder_missing_assets", True)
                        ),
                        keep_frames=bool(body.get("keep_frames", False)),
                        blender_bin=(str(body["blender_bin"]).strip() or None)
                        if body.get("blender_bin") is not None
                        else None,
                    )
                    json_response(self, 202, job.public())
                    return

                if path == "/api/render-cancel":
                    job = render_jobs.cancel(str(body.get("job_id", "")))
                    json_response(self, 200, job.public())
                    return

                if path == "/api/render-resume":
                    job = render_jobs.resume(str(body.get("job_id", "")))
                    json_response(self, 202, job.public())
                    return

                json_response(self, 404, {"error": "not found"})
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                json_response(self, 400, {"error": str(exc)})
            except Exception as exc:
                json_response(self, 500, {"error": str(exc)})

    return StoryCreatorHandler


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the local story, storyboard, and Blender render UI"
    )
    parser.add_argument("--series", default="series/urban_mystery/series.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        handler = make_handler(
            Path(args.series).expanduser().resolve(),
            ROOT / "ui/story_creator.html",
        )
    except (SeriesError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Motion Comic UI: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
