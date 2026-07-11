"""Tiny dependency-free RGBA PNG writer for generated demo assets."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

Color = tuple[int, int, int, int]
Canvas = list[list[Color]]


def canvas(width: int, height: int) -> Canvas:
    return [[(0, 0, 0, 0) for _ in range(width)] for _ in range(height)]


def draw_rectangle(image: Canvas, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
    height = len(image)
    width = len(image[0]) if height else 0
    for y in range(max(0, y0), min(height, y1)):
        for x in range(max(0, x0), min(width, x1)):
            image[y][x] = color


def draw_ellipse(image: Canvas, cx: int, cy: int, rx: int, ry: int, color: Color) -> None:
    if rx <= 0 or ry <= 0:
        return
    height = len(image)
    width = len(image[0]) if height else 0
    for y in range(max(0, cy - ry), min(height, cy + ry + 1)):
        dy = (y - cy) / ry
        for x in range(max(0, cx - rx), min(width, cx + rx + 1)):
            dx = (x - cx) / rx
            if dx * dx + dy * dy <= 1.0:
                image[y][x] = color


def draw_line(
    image: Canvas,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: Color,
    thickness: int = 1,
) -> None:
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        draw_ellipse(image, x0, y0, thickness, thickness, color)
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += sx
        if doubled <= dx:
            error += dx
            y0 += sy


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def write_png(path: str | Path, image: Canvas) -> None:
    height = len(image)
    width = len(image[0]) if height else 0
    if width <= 0 or height <= 0 or any(len(row) != width for row in image):
        raise ValueError("PNG canvas must be a non-empty rectangle")
    raw = b"".join(b"\x00" + bytes(channel for pixel in row for channel in pixel) for row in image)
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    output = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_bytes(output)

