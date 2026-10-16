"""Atomic session persistence and resume discovery."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.state import DetectedWord, SessionState


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SessionStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def create(self, words: list[DetectedWord], dry_run: bool) -> SessionState:
        now = utc_now()
        return SessionState(
            session_id=f"{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:8]}",
            words=words,
            created_at=now,
            updated_at=now,
            dry_run=dry_run,
        )

    def save(self, session: SessionState) -> Path:
        session.updated_at = utc_now()
        path = self.directory / f"{session.session_id}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
        temporary.replace(path)
        return path

    @staticmethod
    def load(path: Path) -> SessionState:
        return SessionState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def latest_resumable(self) -> tuple[Path, SessionState] | None:
        for path in sorted(self.directory.glob("*.json"), key=lambda item: item.stat().st_mtime,
                           reverse=True):
            try:
                session = self.load(path)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
            if not session.stopped_cleanly and any(
                    word.result.value == "PENDING" for word in session.words):
                return path, session
        return None
