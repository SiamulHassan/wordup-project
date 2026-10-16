"""Safety-gated detail action and post-click verification."""

from __future__ import annotations

import time

from app.state import ImportResult
from automation.fallback import WindowFallback
from automation.verification import (already_should_learn_is_selected,
                                     detail_screen_is_safe, visible_names)
from automation.wordup_window import WordUpWindow
from extraction.word_normalizer import comparison_key
from utils.exceptions import ShouldLearnButtonNotFoundError, UnsafeAutomationError


class WordController:
    def __init__(self, target: WordUpWindow, fallback: WindowFallback) -> None:
        self.target = target
        self.fallback = fallback

    def mark_should_learn(self, word: str, dry_run: bool) -> ImportResult:
        self.target.ensure_foreground()
        if not detail_screen_is_safe(self.target, self.fallback, word):
            raise UnsafeAutomationError(
                "Refused to click: foreground, detail headword, or Should Learn verification failed."
            )
        if already_should_learn_is_selected(self.target, self.fallback):
            return ImportResult.ALREADY_SHOULD_LEARN
        if dry_run:
            return ImportResult.DRY_RUN_OK
        candidates = []
        for control in self.target.descendants():
            try:
                if (comparison_key(control.element_info.name or "") ==
                        comparison_key("Should Learn")):
                    candidates.append(control)
            except Exception:
                continue
        actionable = [control for control in candidates
                      if (control.element_info.control_type or "") in
                      {"Button", "CheckBox", "RadioButton"}]
        if actionable:
            candidates = actionable
        for candidate in candidates:
            try:
                if hasattr(candidate, "get_toggle_state") and candidate.get_toggle_state() == 1:
                    return ImportResult.ALREADY_SHOULD_LEARN
                if hasattr(candidate, "is_selected") and candidate.is_selected():
                    return ImportResult.ALREADY_SHOULD_LEARN
            except Exception:
                continue
        before = {comparison_key(value) for value in visible_names(self.target)}
        if len(candidates) == 1:
            try:
                candidates[0].invoke()
            except Exception:
                candidates[0].click_input()
        elif len(candidates) == 0:
            self.fallback.click_text("Should Learn")
        else:
            raise ShouldLearnButtonNotFoundError(
                "Multiple Should Learn controls were visible; refusing an ambiguous click."
            )
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            after = {comparison_key(value) for value in visible_names(self.target)}
            if comparison_key("Should Learn") not in after or after != before:
                return ImportResult.UPDATED
            time.sleep(0.2)
        return ImportResult.CLICKED_UNVERIFIED
