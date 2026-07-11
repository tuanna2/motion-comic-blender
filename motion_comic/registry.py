"""Versioned asset manifest discovery for reusable production libraries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AssetRegistryError(ValueError):
    """Raised when an asset manifest is missing, invalid, or ambiguous."""


@dataclass(frozen=True)
class AssetManifest:
    asset_id: str
    version: int
    path: Path
    data: dict[str, Any]

    @property
    def reference(self) -> str:
        return f"{self.asset_id}@{self.version}"

    @property
    def directory(self) -> Path:
        return self.path.parent


class AssetRegistry:
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self._by_reference: dict[str, AssetManifest] = {}
        self._latest: dict[str, AssetManifest] = {}

    def scan(self) -> "AssetRegistry":
        if not self.root.is_dir():
            raise AssetRegistryError(f"asset library not found: {self.root}")
        for path in sorted(self.root.rglob("manifest.json")):
            manifest = self._load_manifest(path)
            if manifest.reference in self._by_reference:
                previous = self._by_reference[manifest.reference]
                raise AssetRegistryError(
                    f"duplicate asset reference {manifest.reference!r}: {previous.path} and {path}"
                )
            self._by_reference[manifest.reference] = manifest
            current = self._latest.get(manifest.asset_id)
            if current is None or manifest.version > current.version:
                self._latest[manifest.asset_id] = manifest
        return self

    def resolve(self, reference: str) -> AssetManifest:
        if "@" in reference:
            manifest = self._by_reference.get(reference)
        else:
            manifest = self._latest.get(reference)
        if manifest is None:
            known = ", ".join(sorted(self._by_reference)) or "none"
            raise AssetRegistryError(f"unknown asset_ref {reference!r}; registered assets: {known}")
        return manifest

    @staticmethod
    def _load_manifest(path: Path) -> AssetManifest:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AssetRegistryError(f"invalid manifest JSON {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise AssetRegistryError(f"manifest root must be an object: {path}")
        asset_id = data.get("id")
        version = data.get("version")
        if not isinstance(asset_id, str) or not asset_id:
            raise AssetRegistryError(f"manifest id is required: {path}")
        if not isinstance(version, int) or version < 1:
            raise AssetRegistryError(f"manifest version must be a positive integer: {path}")
        if data.get("type") != "layered_character":
            raise AssetRegistryError(f"unsupported manifest type in {path}: {data.get('type')!r}")
        appearances = data.get("appearances")
        if not isinstance(appearances, dict) or not appearances:
            raise AssetRegistryError(f"manifest appearances are required: {path}")
        return AssetManifest(asset_id=asset_id, version=version, path=path, data=data)

