"""Retryable, pausable orchestration for one word at a time."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from app.state import DetectedWord, ImportResult
from automation.fallback import WindowFallback
from automation.search_controller import SearchController
from automation.verification import wait_for_detail_screen
from automation.word_controller import WordController
from automation.wordup_window import WordUpWindow
from utils.exceptions import WordNotFoundError, WordUpImporterError, WordMismatchError

LOGGER = logging.getLogger(__name__)
StatusCallback = Callable[[str], None]


class AutomationEngine:
    def __init__(self, target: WordUpWindow, config: dict[str, Any]) -> None:
        automation = config["automation"]
        self.target = target
        self.search_timeout = float(automation.get("search_timeout", 10.0))
        self.retries = int(automation.get("retry_count", 3))
        self.delay = float(automation.get("delay_between_words", 0.5))
        self.fallback = WindowFallback(
            target,
            automation.get("calibration", {}),
            float(automation.get("fallback_confidence", 0.88)),
        )
        self.search = SearchController(target, self.fallback, self.search_timeout)
        self.word_controller = WordController(target, self.fallback)
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.pause_event.set()

    def pause(self) -> None:
        self.pause_event.clear()

    def resume(self) -> None:
        self.pause_event.set()

    def stop(self) -> None:
        self.stop_event.set()
        self.pause_event.set()

    def reset_control(self) -> None:
        self.stop_event.clear()
        self.pause_event.set()

    def _checkpoint(self) -> bool:
        while not self.pause_event.wait(0.1):
            if self.stop_event.is_set():
                return False
        return not self.stop_event.is_set()

    def process_word(self, word: DetectedWord, dry_run: bool,
                     status: StatusCallback | None = None) -> ImportResult:
        last_error = ""
        for attempt in range(1, self.retries + 1):
            if not self._checkpoint():
                return ImportResult.SKIPPED
            word.attempts += 1
            try:
                if status:
                    status(f"Searching: {word.text} (attempt {attempt}/{self.retries})")
                self.target.ensure_foreground()
                self.search.search(word.text)
                self.search.select_exact_result(word.text)
                if status:
                    status(f"Waiting for verified detail page: {word.text}")
                if not wait_for_detail_screen(self.target, self.fallback, word.text,
                                              self.search_timeout):
                    raise WordMismatchError(
                        f"WordUp did not reach a verified detail screen for '{word.text}'."
                    )
                result = self.word_controller.mark_should_learn(word.text, dry_run)
                word.error = ""
                word.result = result
                if status:
                    status(f"{word.text}: {result.value}")
                    status(f"Preparing Search for the next word after: {word.text}")
                self.search.prepare_for_next_word()
                if self.delay > 0 and not self.stop_event.wait(self.delay):
                    return result
                return result
            except WordNotFoundError as exc:
                last_error = str(exc)
                LOGGER.warning("Word not found on attempt %s: %s", attempt, word.text)
            except WordUpImporterError as exc:
                last_error = str(exc)
                LOGGER.warning("Automation attempt failed for %s: %s", word.text, exc)
            except Exception as exc:
                last_error = f"Unexpected automation error: {exc}"
                LOGGER.exception("Unexpected automation failure for %s", word.text)
            if self.stop_event.wait(min(0.4 * attempt, 1.2)):
                return ImportResult.SKIPPED
        word.error = last_error
        if "Ambiguous" in last_error:
            word.result = ImportResult.AMBIGUOUS
        elif "No exact" in last_error:
            word.result = ImportResult.NOT_FOUND
        else:
            word.result = ImportResult.FAILED
        return word.result
