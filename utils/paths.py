"""Runtime-safe filesystem locations for source and frozen builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "WordUpVocabularyImporter"


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def data_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_runtime_dirs() -> dict[str, Path]:
    root = data_root()
    paths = {
        "root": root,
        "logs": root / "logs",
        "sessions": root / "sessions",
        "cache": root / "cache",
        "debug": root / "debug",
        "reports": root / "reports",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
