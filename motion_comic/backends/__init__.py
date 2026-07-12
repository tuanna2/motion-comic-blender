"""Animation backends selected by character asset manifests."""

from .mmd import MMDActionBackend
from .sprite2d import SpriteActionBackend

__all__ = ["MMDActionBackend", "SpriteActionBackend"]
