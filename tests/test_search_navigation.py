from __future__ import annotations

from automation.fallback import ScreenText
from automation.search_controller import SearchController


class FakeTarget:
    def ensure_foreground(self) -> None:
        return None

    def descendants(self, control_type=None):
        return []


class FakeFallback:
    def __init__(self, on_search: bool = False, on_detail: bool = False,
                 detail_returns_to_search: bool = False) -> None:
        self.calibration = {"search_icon": {}, "back": {}}
        self.on_search = on_search
        self.on_detail = on_detail
        self.detail_returns_to_search = detail_returns_to_search
        self.clicks: list[str] = []

    def find_exact_text(self, expected: str, confidence: float) -> list[object]:
        if expected == "Search":
            return [object()] if self.on_search else []
        if expected == "Should Learn":
            return [object()] if self.on_detail else []
        return []

    def screen_text(self) -> list[ScreenText]:
        labels: list[str] = []
        if self.on_search:
            labels.append("Search")
        if self.on_detail:
            labels.append("ShouldLearn")
        return [ScreenText(label, 0.99, (0, 0, 10, 10)) for label in labels]

    def click_relative(self, name: str) -> None:
        self.clicks.append(name)
        if name == "back":
            self.on_detail = False
            if self.detail_returns_to_search:
                self.on_search = True
        if name == "search_icon":
            self.on_search = True

    def clear_search(self) -> None:
        self.clicks.append("clear_search")


def test_navigation_keeps_an_existing_search_screen() -> None:
    fallback = FakeFallback(on_search=True)
    SearchController(FakeTarget(), fallback, timeout=0.1).navigate()
    assert fallback.clicks == []


def test_navigation_leaves_detail_before_opening_search() -> None:
    fallback = FakeFallback(on_detail=True)
    SearchController(FakeTarget(), fallback, timeout=0.1).navigate()
    assert fallback.clicks == ["back", "search_icon"]


def test_navigation_reuses_search_screen_returned_by_detail_close() -> None:
    fallback = FakeFallback(on_detail=True, detail_returns_to_search=True)

    SearchController(FakeTarget(), fallback, timeout=0.1).navigate()

    assert fallback.clicks == ["back"]


def test_prepare_for_next_word_closes_detail_and_clears_old_query() -> None:
    fallback = FakeFallback(on_detail=True, detail_returns_to_search=True)

    SearchController(FakeTarget(), fallback, timeout=0.1).prepare_for_next_word()

    assert fallback.on_search
    assert fallback.clicks == ["back", "clear_search"]
