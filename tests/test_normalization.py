from __future__ import annotations

from app.state import DetectedWord
from extraction.word_normalizer import comparison_key, deduplicate, looks_uncertain, normalize_display


def test_conservative_normalization() -> None:
    assert normalize_display("  Inevitable\n") == "Inevitable"
    assert normalize_display("state–of–the–art") == "state–of–the–art"
    assert normalize_display("learner’s choice") == "learner's choice"


def test_comparison_is_case_insensitive() -> None:
    assert comparison_key("Ambiguity") == comparison_key("AMBIGUITY")


def test_dedup_preserves_sources_and_best_confidence() -> None:
    words = [
        DetectedWord("Ambiguity", 0.80, ["a.png"]),
        DetectedWord(" ambiguity ", 0.95, ["b.png"]),
    ]
    unique = deduplicate(words)
    assert len(unique) == 1
    assert unique[0].confidence == 0.95
    assert unique[0].sources == ["a.png", "b.png"]


def test_ocr_digits_are_flagged_not_silently_corrected() -> None:
    assert looks_uncertain("Oppos1tion")
