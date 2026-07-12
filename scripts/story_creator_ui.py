#!/usr/bin/env python3
"""Local UI for series characters, prompt generation, and AI-result validation."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.series import SeriesError, load_series, validate_story_source  # noqa: E402
from motion_comic.story_prompt import build_story_creation_prompt  # noqa: E402


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


def make_handler(series_path: Path, html_path: Path):
    series = load_series(series_path)
    html = html_path.read_bytes()

    class StoryCreatorHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            elif path == "/api/series":
                json_response(self, 200, series.data)
            else:
                json_response(self, 404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 5_000_000:
                    raise ValueError("invalid request size")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
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
                    source_text = body.get("story_source")
                    if not isinstance(source_text, str):
                        raise ValueError("story_source must be JSON text")
                    payload = json.loads(source_text)
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
                json_response(self, 404, {"error": "not found"})
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                json_response(self, 400, {"error": str(exc)})

    return StoryCreatorHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local AI story-creation UI")
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
    print(f"Story Creator UI: http://{args.host}:{args.port}")
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
