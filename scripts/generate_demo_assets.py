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
PROP_OUTPUT = ROOT / "assets/props/straw_hat/generated"
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

    arm_upper = outlined_ellipse(170, 62, SKIN, border=6)
    forearm = outlined_ellipse(170, 62, SKIN, border=6)
    leg_upper = outlined_ellipse(74, 140, (30, 41, 59, 255), border=6)
    leg_lower = outlined_ellipse(74, 140, (30, 41, 59, 255), border=6)
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

    eyes_closed = canvas(170, 58)
    draw_line(eyes_closed, 28, 32, 68, 32, INK, 6)
    draw_line(eyes_closed, 102, 32, 142, 32, INK, 6)

    eyes_sad = canvas(170, 64)
    draw_ellipse(eyes_sad, 48, 38, 11, 15, INK)
    draw_ellipse(eyes_sad, 122, 38, 11, 15, INK)
    draw_line(eyes_sad, 26, 27, 67, 12, INK, 5)
    draw_line(eyes_sad, 103, 12, 144, 27, INK, 5)

    eyes_surprised = canvas(170, 66)
    draw_ellipse(eyes_surprised, 48, 33, 18, 24, INK)
    draw_ellipse(eyes_surprised, 122, 33, 18, 24, INK)
    draw_ellipse(eyes_surprised, 48, 33, 7, 11, (255, 255, 255, 255))
    draw_ellipse(eyes_surprised, 122, 33, 7, 11, (255, 255, 255, 255))

    blush = canvas(190, 54)
    draw_ellipse(blush, 36, 27, 28, 14, (244, 63, 94, 150))
    draw_ellipse(blush, 154, 27, 28, 14, (244, 63, 94, 150))

    tears = canvas(170, 120)
    draw_line(tears, 48, 22, 48, 104, (56, 189, 248, 210), 9)
    draw_line(tears, 122, 22, 122, 104, (56, 189, 248, 210), 9)
    draw_ellipse(tears, 48, 104, 11, 13, (56, 189, 248, 210))
    draw_ellipse(tears, 122, 104, 11, 13, (56, 189, 248, 210))

    mouth_closed = canvas(110, 32)
    draw_ellipse(mouth_closed, 55, 16, 48, 7, (127, 29, 29, 255))
    mouth_open = outlined_ellipse(84, 74, (127, 29, 29, 255), border=5)

    hat = canvas(280, 120)
    draw_ellipse(hat, 140, 88, 132, 25, (120, 53, 15, 255))
    draw_rectangle(hat, 73, 25, 207, 88, (217, 119, 6, 255))
    draw_ellipse(hat, 140, 28, 67, 22, (245, 158, 11, 255))
    draw_rectangle(hat, 73, 68, 207, 82, (127, 29, 29, 255))

    assets = {
        "body.png": body,
        "head.png": head,
        "arm_upper.png": arm_upper,
        "forearm.png": forearm,
        "leg_left_upper.png": leg_upper,
        "leg_left_lower.png": leg_lower,
        "leg_right_upper.png": leg_upper,
        "leg_right_lower.png": leg_lower,
        "rod.png": rod,
        "eyes_normal.png": eyes_normal,
        "eyes_angry.png": eyes_angry,
        "eyes_closed.png": eyes_closed,
        "eyes_sad.png": eyes_sad,
        "eyes_surprised.png": eyes_surprised,
        "blush.png": blush,
        "tears.png": tears,
        "mouth_closed.png": mouth_closed,
        "mouth_open.png": mouth_open,
    }
    for filename, image in assets.items():
        write_png(OUTPUT / filename, image)
    write_png(PROP_OUTPUT / "hat.png", hat)
    print(f"Generated {len(assets)} character layers in {OUTPUT}")
    print(f"Generated reusable prop in {PROP_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
