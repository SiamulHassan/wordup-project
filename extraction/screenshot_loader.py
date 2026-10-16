"""Validated screenshot loading helpers."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def discover_images(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in SUPPORTED_EXTENSIONS else []
    if not path.is_dir():
        return []
    return sorted(
        item for item in path.iterdir()
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def load_image(path: Path) -> np.ndarray:
    """Load Unicode Windows paths without relying on cv2.imread path handling."""
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported image type: {path.suffix}")
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode screenshot: {path}")
    return image
