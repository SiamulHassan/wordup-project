from __future__ import annotations

from app.state import DetectedWord
from storage.word_store import load_words, save_words


def test_txt_import_deduplicates(tmp_path) -> None:
    path = tmp_path / "words.txt"
    path.write_text("Scale\nscale\nThick\n", encoding="utf-8")
    words = load_words(path)
    assert [word.text for word in words] == ["Scale", "Thick"]


def test_json_round_trip(tmp_path) -> None:
    path = tmp_path / "words.json"
    save_words([DetectedWord("Collapse")], path)
    assert load_words(path)[0].text == "Collapse"
