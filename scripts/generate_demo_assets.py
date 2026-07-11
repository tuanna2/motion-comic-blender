#!/usr/bin/env python3
"""Generate transparent layered PNGs used by the reusable character demo."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from motion_comic.png import canvas, draw_ellipse, draw_line, draw_rectangle, write_png  # noqa: E402


OUTPUT = ROOT / "assets/characters/angler/generated"
INK = (17, 24, 39, 255)
SKIN = (242, 179, 138, 255)
SHIRT = (239, 68, 68, 255)


def outlined_ellipse(width: int, height: int, fill, outline=INK, border: int = 8):
    image = canvas(width, height)
    draw_ellipse(image, width // 2, height // 2, width // 2 - 2, height // 2 - 2, outline)
    draw_ellipse(
        image,
        width // 2,
        height // 2,
        width // 2 - border,
        height // 2 - border,
        fill,
    )
    return image


def main() -> int:
    body = outlined_ellipse(240, 300, SHIRT)
    head = outlined_ellipse(220, 220, SKIN)
    # A fixed hair silhouette is baked into the reusable head asset.
    draw_ellipse(head, 110, 38, 94, 35, INK)

    arm = outlined_ellipse(260, 76, SKIN, border=6)
    leg = outlined_ellipse(72, 220, (30, 41, 59, 255), border=6)
    rod = canvas(520, 24)
    draw_rectangle(rod, 2, 5, 518, 19, (66, 32, 6, 255))

    eyes_normal = canvas(170, 58)
    draw_ellipse(eyes_normal, 48, 29, 12, 17, INK)
    draw_ellipse(eyes_normal, 122, 29, 12, 17, INK)

    eyes_angry = canvas(170, 64)
    draw_ellipse(eyes_angry, 48, 38, 12, 15, INK)
    draw_ellipse(eyes_angry, 122, 38, 12, 15, INK)
    draw_line(eyes_angry, 25, 12, 67, 28, INK, 5)
    draw_line(eyes_angry, 103, 28, 145, 12, INK, 5)

    mouth_closed = canvas(110, 32)
    draw_ellipse(mouth_closed, 55, 16, 48, 7, (127, 29, 29, 255))
    mouth_open = outlined_ellipse(84, 74, (127, 29, 29, 255), border=5)

    assets = {
        "body.png": body,
        "head.png": head,
        "arm_front.png": arm,
        "leg_left.png": leg,
        "leg_right.png": leg,
        "rod.png": rod,
        "eyes_normal.png": eyes_normal,
        "eyes_angry.png": eyes_angry,
        "mouth_closed.png": mouth_closed,
        "mouth_open.png": mouth_open,
    }
    for filename, image in assets.items():
        write_png(OUTPUT / filename, image)
    print(f"Generated {len(assets)} layered PNG assets in {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

