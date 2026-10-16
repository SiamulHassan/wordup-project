"""Adaptive search navigation and exact-result selection."""

from __future__ import annotations

import time

from automation.fallback import WindowFallback
from automation.locators import ControlLocator
from automation.verification import should_learn_action_is_visible
from automation.wordup_window import WordUpWindow
from extraction.word_normalizer import comparison_key
from utils.exceptions import (AutomationTimeoutError, SearchControlNotFoundError,
                              WordNotFoundError)


SEARCH_BUTTON = ControlLocator(names=("Search",), control_types=("Button", "Text"))
SEARCH_EDIT = ControlLocator(control_types=("Edit",))


def _safe_name(control: object) -> str:
    try:
        return (control.element_info.name or control.window_text() or "").strip()
    except Exception:
        return ""


def screen_result_candidates(matches: list[object], window_height: int) -> list[object]:
    """Exclude the query echoed inside WordUp's top search field."""
    minimum_center_y = max(120.0, window_height * 0.18)
    return [item for item in matches
            if (item.bbox[1] + item.bbox[3]) / 2 >= minimum_center_y]


class SearchController:
    def __init__(self, target: WordUpWindow, fallback: WindowFallback, timeout: float = 10.0) -> None:
        self.target = target
        self.fallback = fallback
        self.timeout = timeout

    def _edits(self) -> list[object]:
        edits: list[object] = []
        for item in self.target.descendants("Edit"):
            try:
                if item.is_visible() and item.is_enabled() and SEARCH_EDIT.matches(item):
                    edits.append(item)
            except Exception:
                continue
        return edits

    def _is_search_screen(self) -> bool:
        # Flutter exposes the search box through UIA on some builds, while OCR of
        # the page heading is the dependable fallback on others.
        return bool(self._edits()) or bool(self.fallback.find_exact_text("Search", 0.65))

    def navigate(self) -> None:
        self.target.ensure_foreground()
        if self._is_search_screen():
            return
        if should_learn_action_is_visible(self.target, self.fallback):
            if "back" not in self.fallback.calibration:
                raise SearchControlNotFoundError(
                    "WordUp is on a detail screen and its close point is not calibrated."
                )
            self.fallback.click_relative("back")
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                # WordUp normally closes a detail card back to the same Search
                # screen. Reuse it instead of clicking the Home search position,
                # which is not a search icon on this screen.
                if self._is_search_screen():
                    return
                if not should_learn_action_is_visible(self.target, self.fallback):
                    break
                time.sleep(0.2)
            else:
                raise AutomationTimeoutError("WordUp did not leave the word detail screen.")
            # If closing landed on Home, give its short transition time to settle
            # before using the calibrated Home search icon below.
            time.sleep(0.35)
            if self._is_search_screen():
                return
        buttons = [item for item in self.target.descendants() if SEARCH_BUTTON.matches(item)]
        if buttons:
            try:
                buttons[0].invoke()
            except Exception:
                buttons[0].click_input()
        elif "search_icon" in self.fallback.calibration:
            self.fallback.click_relative("search_icon")
        else:
            raise SearchControlNotFoundError(
                "Search was not exposed through UIA and no fallback point is calibrated."
            )
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self._edits():
                return
            if self.fallback.find_exact_text("Search", 0.65):
                return
            time.sleep(0.2)
        raise AutomationTimeoutError("WordUp did not transition to the Search screen.")

    def clear_query(self) -> None:
        """Clear both the previous query and its result list before another word."""
        self.target.ensure_foreground()
        edits = self._edits()
        if edits:
            edit = edits[0]
            try:
                edit.set_edit_text("")
                return
            except Exception:
                try:
                    edit.click_input()
                    edit.type_keys("^a{BACKSPACE}", set_foreground=False)
                    return
                except Exception:
                    pass
        self.fallback.clear_search()

    def prepare_for_next_word(self) -> None:
        self.navigate()
        self.clear_query()

    def search(self, word: str) -> None:
        self.navigate()
        self.clear_query()
        self.target.ensure_foreground()
        edits = self._edits()
        if edits:
            edit = edits[0]
            try:
                edit.set_edit_text(word)
                edit.type_keys("{ENTER}")
                return
            except Exception:
                try:
                    edit.click_input()
                    edit.type_keys("^a{BACKSPACE}" + word.replace(" ", "{SPACE}") + "{ENTER}",
                                   with_spaces=True, set_foreground=False)
                    return
                except Exception:
                    pass
        self.fallback.enter_search(word)

    def _wait_for_result_transition(self, deadline: float) -> bool:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.75, remaining))
        # WordUp can paint OCR-readable result text before its row accepts clicks.
        # A successful transition removes the Search edit and exposes the detail action.
        return (not self._edits()
                and should_learn_action_is_visible(self.target, self.fallback))

    def select_exact_result(self, word: str) -> None:
        expected = comparison_key(word)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            matches: list[object] = []
            for item in self.target.descendants():
                try:
                    if (item.is_visible() and item.is_enabled()
                            and comparison_key(_safe_name(item)) == expected):
                        matches.append(item)
                except Exception:
                    continue
            clickable = [item for item in matches
                         if (item.element_info.control_type or "") in {"ListItem", "Button", "Text"}]
            if clickable:
                target = clickable[-1]
                try:
                    target.invoke()
                except Exception:
                    target.click_input()
                if self._wait_for_result_transition(deadline):
                    return
                continue
            screen_matches = self.fallback.find_exact_text(word, 0.74)
            left, top, right, bottom = self.target.rectangle()
            result_matches = screen_result_candidates(screen_matches, bottom - top)
            if len(result_matches) == 1:
                item = result_matches[0]
                x1, y1, x2, y2 = item.bbox
                self.target.ensure_foreground()
                import pyautogui
                pyautogui.click(left + (x1 + x2) // 2, top + (y1 + y2) // 2)
                if self._wait_for_result_transition(deadline):
                    return
                continue
            if len(result_matches) > 1:
                raise WordNotFoundError(f"Ambiguous result-list matches for '{word}'.")
            time.sleep(0.25)
        raise WordNotFoundError(f"No exact WordUp search result found for '{word}'.")
