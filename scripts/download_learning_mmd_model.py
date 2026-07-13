#!/usr/bin/env python3
"""Download the upstream Miku v2 MMD learning model without redistributing it."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets/characters/mmd_demo/source"
UPSTREAM = "https://raw.githubusercontent.com/mrdoob/three.js/r160/examples/models/mmd"
FILES = {
    "character.pmd": ("miku/miku_v2.pmd", 712126),
    "eyeM2.bmp": ("miku/eyeM2.bmp", 49206),
    "README_UPSTREAM.txt": ("miku/readme.txt", 203),
    "README_MODEL_JA.txt": ("miku/readme_miku_v2.txt", 19465),
    "MMD_ASSETS_LICENSE.txt": ("LICENSE", 150),
    "MMD_ASSETS_README.txt": ("Readme.txt", 1156),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a non-commercial MMD learning model")
    parser.add_argument(
        "--accept-noncommercial-license",
        action="store_true",
        help="Confirm this model will be used only under its upstream and Piapro terms",
    )
    parser.add_argument("--force", action="store_true", help="Replace files already downloaded")
    return parser.parse_args()


def download(url: str, destination: Path, expected_size: int) -> str:
    temporary = destination.with_suffix(destination.suffix + ".download")
    request = urllib.request.Request(url, headers={"User-Agent": "motion-comic-blender/0.4"})
    with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
    size = temporary.stat().st_size
    if size != expected_size:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"unexpected size for {destination.name}: got {size}, expected {expected_size}"
        )
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    temporary.replace(destination)
    return digest


def main() -> int:
    args = parse_args()
    if not args.accept_noncommercial_license:
        print(
            "This learning model is not under the repository MIT license. Read:\n"
            "  https://github.com/mrdoob/three.js/tree/r160/examples/models/mmd\n"
            "  https://piapro.net/intl/en_for_creators.html\n"
            "Re-run with --accept-noncommercial-license for learning/non-commercial use.",
            file=sys.stderr,
        )
        return 2
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for local_name, (relative_url, expected_size) in FILES.items():
        destination = OUTPUT / local_name
        if destination.is_file() and not args.force:
            print(f"Keep existing: {destination}")
            continue
        digest = download(f"{UPSTREAM}/{relative_url}", destination, expected_size)
        print(f"Downloaded: {destination} (sha256 {digest[:12]}…)")
    print("Learning model ready: assets/characters/mmd_demo/source/character.pmd")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
