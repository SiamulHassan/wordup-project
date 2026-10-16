"""Import and export TXT, CSV, and JSON vocabulary lists."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from app.state import DetectedWord, ReviewStatus
from extraction.word_normalizer import deduplicate, normalize_display


def load_words(path: Path) -> list[DetectedWord]:
    suffix = path.suffix.lower()
    values: list[str]
    if suffix == ".txt":
        values = path.read_text(encoding="utf-8-sig").splitlines()
    elif suffix == ".csv":
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.reader(stream))
        if rows and rows[0] and rows[0][0].strip().casefold() in {"word", "text", "vocabulary"}:
            rows = rows[1:]
        values = [row[0] for row in rows if row]
    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            data = data.get("words", [])
        values = [item.get("word", item.get("text", "")) if isinstance(item, dict) else str(item)
                  for item in data]
    else:
        raise ValueError("Word lists must be TXT, CSV, or JSON")
    words = [DetectedWord(text=normalize_display(value), sources=[str(path)],
                          review_status=ReviewStatus.MANUAL)
             for value in values if normalize_display(value)]
    return deduplicate(words)


def save_words(words: list[DetectedWord], path: Path) -> None:
    selected = [word for word in words if word.selected]
    suffix = path.suffix.lower()
    if suffix == ".txt":
        path.write_text("\n".join(word.text for word in selected) + "\n", encoding="utf-8")
    elif suffix == ".csv":
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow(["word", "confidence", "source", "status"])
            for word in selected:
                writer.writerow([word.text, f"{word.confidence:.4f}", word.source_display,
                                 word.review_status.value])
    elif suffix == ".json":
        path.write_text(json.dumps({"words": [word.to_dict() for word in selected]}, indent=2),
                        encoding="utf-8")
    else:
        raise ValueError("Export filename must end with .txt, .csv, or .json")
