"""Append-only JSON Lines history plus CSV report export."""

from __future__ import annotations

import csv
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.state import DetectedWord


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, word: DetectedWord, session_id: str) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": session_id,
            "word": word.text,
            "result": word.result.value,
            "attempts": word.attempts,
            "sources": word.sources,
            "confidence": word.confidence,
            "error": word.error,
        }
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        result: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return result

    @staticmethod
    def export_report(words: list[DetectedWord], path: Path) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "word", "result", "attempts", "confidence", "sources", "error"
            ])
            writer.writeheader()
            for word in words:
                writer.writerow({
                    "word": word.text,
                    "result": word.result.value,
                    "attempts": word.attempts,
                    "confidence": f"{word.confidence:.4f}",
                    "sources": " | ".join(word.sources),
                    "error": word.error,
                })
