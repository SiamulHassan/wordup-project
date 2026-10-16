"""Semantic and visual safety verification helpers."""

from __future__ import annotations

import time

from automation.fallback import WindowFallback
from automation.wordup_window import WordUpWindow
from extraction.word_normalizer import comparison_key


def visible_names(target: WordUpWindow) -> list[str]:
    names: list[str] = []
    for control in target.descendants():
        try:
            if control.is_visible() and control.element_info.name:
                names.append(control.element_info.name.strip())
        except Exception:
            continue
    return names


def _compact_label(value: str) -> str:
    return "".join(character for character in comparison_key(value)
                   if character.isalnum())


def _has_should_learn(values: list[str]) -> bool:
    return any("shouldlearn" in _compact_label(value) for value in values)


def wait_for_detail_screen(target: WordUpWindow, fallback: WindowFallback, word: str,
                           timeout: float) -> bool:
    """Wait until WordUp has fully transitioned to the verified word-detail screen."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # The search page also contains the query and an exact result. Requiring the
        # detail action prevents that page from being mistaken for the destination.
        if detail_screen_is_safe(target, fallback, word):
            return True
        time.sleep(0.25)
    return False


def detail_screen_is_safe(target: WordUpWindow, fallback: WindowFallback, word: str) -> bool:
    if not target.is_foreground():
        return False
    visible = visible_names(target)
    names = [comparison_key(name) for name in visible]
    headword = comparison_key(word)
    has_headword = headword in names
    has_action = _has_should_learn(visible)
    if not has_headword or not has_action:
        screen = fallback.screen_text()
        screen_labels = [item.text for item in screen if item.confidence >= 0.72]
        screen_keys = [comparison_key(item) for item in screen_labels]
        has_headword = has_headword or headword in screen_keys
        has_action = has_action or _has_should_learn(screen_labels)
    return has_headword and has_action


def should_learn_action_is_visible(target: WordUpWindow,
                                   fallback: WindowFallback) -> bool:
    if _has_should_learn(visible_names(target)):
        return True
    return _has_should_learn([
        item.text for item in fallback.screen_text() if item.confidence >= 0.72
    ])


def already_should_learn_is_selected(target: WordUpWindow,
                                     fallback: WindowFallback) -> bool:
    """Recognize WordUp's post-selection knowledge-state footer."""
    labels = visible_names(target)

    def state_is_visible(values: list[str]) -> bool:
        compact = [_compact_label(value) for value in values]
        has_knowledge = any("yourknowledge" in value for value in compact)
        has_should_learn = any("shouldlearn" in value for value in compact)
        has_learn_now = any(value == "learnnow" for value in compact)
        return has_knowledge and has_should_learn and has_learn_now

    if state_is_visible(labels):
        return True
    screen_labels = [item.text for item in fallback.screen_text()
                     if item.confidence >= 0.72]
    return state_is_visible(screen_labels)
