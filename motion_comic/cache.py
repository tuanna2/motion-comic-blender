"""Content-addressed cache helpers for compiled MMD model/action artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path


def file_digest(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    source = Path(path).expanduser().resolve()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def cached_artifact(source: str | Path, cache_root: str | Path | None = None) -> Path:
    """Return a stable cached copy of a compiled blend, or the source when disabled."""
    source_path = Path(source).expanduser().resolve()
    configured = cache_root or os.environ.get("MOTION_COMIC_ASSET_CACHE")
    if not configured or not source_path.is_file():
        return source_path
    root = Path(configured).expanduser().resolve()
    digest = file_digest(source_path)
    target = root / "blends" / f"{digest}{source_path.suffix.lower()}"
    metadata = root / "metadata" / f"{digest}.json"
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            os.link(source_path, temporary)
        except OSError:
            shutil.copy2(source_path, temporary)
        temporary.replace(target)
    if not metadata.is_file():
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(
            json.dumps(
                {"sha256": digest, "source": str(source_path), "cached": str(target)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return target
