"""Shared, serializable application state models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ReviewStatus(StrEnum):
    READY = "Ready"
    LOW_CONFIDENCE = "Review"
    MANUAL = "Manual"
    EXCLUDED = "Excluded"


class ImportResult(StrEnum):
    PENDING = "PENDING"
    UPDATED = "UPDATED"
    ALREADY_SHOULD_LEARN = "ALREADY_SHOULD_LEARN"
    CLICKED_UNVERIFIED = "CLICKED_UNVERIFIED"
    DRY_RUN_OK = "DRY_RUN_OK"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(slots=True)
class DetectedWord:
    text: str
    confidence: float = 1.0
    sources: list[str] = field(default_factory=list)
    bbox: tuple[int, int, int, int] | None = None
    color_class: str = "purple"
    review_status: ReviewStatus = ReviewStatus.READY
    selected: bool = True
    result: ImportResult = ImportResult.PENDING
    attempts: int = 0
    error: str = ""

    @property
    def source_display(self) -> str:
        return ", ".join(Path(item).name for item in self.sources)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["review_status"] = self.review_status.value
        data["result"] = self.result.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DetectedWord":
        copied = dict(data)
        if copied.get("bbox") is not None:
            copied["bbox"] = tuple(copied["bbox"])
        copied["review_status"] = ReviewStatus(copied.get("review_status", "Ready"))
        copied["result"] = ImportResult(copied.get("result", "PENDING"))
        return cls(**copied)


@dataclass(slots=True)
class ExtractionStats:
    screenshots: int = 0
    purple_tiles: int = 0
    white_tiles: int = 0
    cyan_tiles: int = 0
    unique_words: int = 0
    low_confidence: int = 0


@dataclass(slots=True)
class SessionState:
    session_id: str
    words: list[DetectedWord] = field(default_factory=list)
    current_index: int = 0
    created_at: str = ""
    updated_at: str = ""
    dry_run: bool = True
    stopped_cleanly: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "words": [word.to_dict() for word in self.words],
            "current_index": self.current_index,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "dry_run": self.dry_run,
            "stopped_cleanly": self.stopped_cleanly,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        copied = dict(data)
        copied["words"] = [DetectedWord.from_dict(item) for item in copied.get("words", [])]
        return cls(**copied)
