from __future__ import annotations

from app.state import ImportResult
from automation.fallback import ScreenText
from automation.verification import already_should_learn_is_selected
from automation.word_controller import WordController


class FakeTarget:
    def ensure_foreground(self) -> None:
        return None

    def is_foreground(self) -> bool:
        return True

    def descendants(self):
        return []


class FakeFallback:
    def __init__(self, labels: list[str]) -> None:
        self.labels = labels
        self.clicked = False

    def screen_text(self) -> list[ScreenText]:
        return [ScreenText(label, 0.99, (0, 0, 10, 10)) for label in self.labels]

    def click_text(self, expected: str) -> None:
        self.clicked = True


def test_recognizes_already_should_learn_footer() -> None:
    fallback = FakeFallback(["Your knowledge:", "Should Learn", "Learn Now"])

    assert already_should_learn_is_selected(FakeTarget(), fallback)


def test_new_word_buttons_are_not_an_already_selected_state() -> None:
    fallback = FakeFallback(["Should Learn", "Already Know"])

    assert not already_should_learn_is_selected(FakeTarget(), fallback)


def test_already_selected_word_is_not_clicked_again() -> None:
    fallback = FakeFallback([
        "Thick", "Your knowledge:", "Should Learn", "Learn Now"
    ])

    result = WordController(FakeTarget(), fallback).mark_should_learn("Thick", False)

    assert result == ImportResult.ALREADY_SHOULD_LEARN
    assert not fallback.clicked
