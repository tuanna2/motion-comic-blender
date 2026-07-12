"""Shared animation backend contract."""

from __future__ import annotations

from typing import Protocol

from ..assets import AssetBundle


class ActionBackend(Protocol):
    def apply(
        self,
        bundle: AssetBundle,
        action: str,
        start: int,
        end: int,
        params: dict,
        **context,
    ) -> None: ...
