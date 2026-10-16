from __future__ import annotations

from automation.fallback import ScreenText
from automation.verification import detail_screen_is_safe, wait_for_detail_screen


class FakeTarget:
    def is_foreground(self) -> bool:
        return True

    def descendants(self):
        return []


class TransitioningFallback:
    def __init__(self) -> None:
        self.calls = 0

    def screen_text(self) -> list[ScreenText]:
        self.calls += 1
        if self.calls == 1:
            # This is the search screen: the word is visible, but the action is not.
            return [
                ScreenText("Inevitable", 0.99, (0, 0, 10, 10)),
                ScreenText("Search", 0.99, (0, 0, 10, 10)),
            ]
        return [
            ScreenText("Inevitable", 0.99, (0, 0, 10, 10)),
            ScreenText("Should Learn", 0.99, (0, 0, 10, 10)),
        ]


class SearchOnlyFallback:
    def screen_text(self) -> list[ScreenText]:
        return [
            ScreenText("Inevitable", 0.99, (0, 0, 10, 10)),
            ScreenText("Search", 0.99, (0, 0, 10, 10)),
        ]


def test_wait_does_not_accept_word_visible_only_on_search_screen() -> None:
    fallback = TransitioningFallback()

    assert wait_for_detail_screen(FakeTarget(), fallback, "Inevitable", 0.6)
    assert fallback.calls >= 2


def test_wait_times_out_if_detail_action_never_appears() -> None:
    assert not wait_for_detail_screen(
        FakeTarget(), SearchOnlyFallback(), "Inevitable", 0.05
    )


def test_detail_accepts_ocr_joined_should_learn_label() -> None:
    fallback = SearchOnlyFallback()
    fallback.screen_text = lambda: [
        ScreenText("Thick", 0.99, (0, 0, 10, 10)),
        ScreenText("ShouldLearn", 0.99, (0, 0, 10, 10)),
    ]

    assert detail_screen_is_safe(FakeTarget(), fallback, "Thick")
