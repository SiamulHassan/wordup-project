"""Rotating file and GUI-friendly logging setup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: Path, level: str = "INFO", max_bytes: int = 2_097_152,
                      backup_count: int = 4) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "wordup_importer.log"
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))
        root.addHandler(handler)
    return log_path
