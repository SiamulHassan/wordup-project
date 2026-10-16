"""Conservative normalization and case-insensitive deduplication."""

from __future__ import annotations

import re
import unicodedata

from app.state import DetectedWord, ReviewStatus


_SPACE_RE = re.compile(r"\s+")
_SAFE_TEXT_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\- ]*$")


def normalize_display(text: str) -> str:
    value = unicodedata.normalize("NFC", text).replace("’", "'")
    return _SPACE_RE.sub(" ", value).strip(" \t\r\n|_.,:;[]{}()")


def comparison_key(text: str) -> str:
    return unicodedata.normalize("NFKC", normalize_display(text)).casefold()


def looks_uncertain(text: str) -> bool:
    value = normalize_display(text)
    return not value or not _SAFE_TEXT_RE.fullmatch(value) or len(value) > 80


def deduplicate(words: list[DetectedWord]) -> list[DetectedWord]:
    result: dict[str, DetectedWord] = {}
    order: list[str] = []
    for word in words:
        word.text = normalize_display(word.text)
        key = comparison_key(word.text)
        if not key:
            continue
        if key not in result:
            result[key] = word
            order.append(key)
            continue
        existing = result[key]
        for source in word.sources:
            if source not in existing.sources:
                existing.sources.append(source)
        if word.confidence > existing.confidence:
            existing.confidence = word.confidence
            existing.bbox = word.bbox
        if word.review_status == ReviewStatus.LOW_CONFIDENCE:
            existing.review_status = ReviewStatus.LOW_CONFIDENCE
    return [result[key] for key in order]
