"""Application use-cases independent of Qt widgets."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.state import DetectedWord, ExtractionStats, ImportResult, SessionState
from automation.automation_engine import AutomationEngine
from automation.ui_inspector import UIInspector
from automation.wordup_window import WindowSummary, WordUpWindow
from extraction.extractor import VocabularyExtractor
from storage.history import HistoryStore
from storage.session_store import SessionStore
from storage.word_store import load_words, save_words
from utils.config import Config, load_config
from utils.logger import configure_logging
from utils.paths import ensure_runtime_dirs


class AppController:
    def __init__(self) -> None:
        self.paths = ensure_runtime_dirs()
        self.config: Config = load_config()
        configure_logging(
            self.paths["logs"],
            str(self.config.get("logging.level", "INFO")),
            int(self.config.get("logging.max_bytes", 2_097_152)),
            int(self.config.get("logging.backup_count", 4)),
        )
        self.session_store = SessionStore(self.paths["sessions"])
        self.history = HistoryStore(self.paths["root"] / "history.jsonl")
        self.target = WordUpWindow(
            str(self.config.get("wordup.window_title_regex", ".*WordUp.*"))
        )
        self.engine: AutomationEngine | None = None
        self.session: SessionState | None = None

    def create_extractor(self, debug: bool = False) -> VocabularyExtractor:
        self.config.set("debug.extraction", debug)
        return VocabularyExtractor(self.config.values, self.paths["cache"], self.paths["debug"])

    def extract(self, screenshots: list[Path], debug: bool = False,
                progress: Callable[[int, int, str], None] | None = None,
                use_cache: bool = True) -> tuple[list[DetectedWord], ExtractionStats]:
        return self.create_extractor(debug).extract(screenshots, progress, use_cache)

    @staticmethod
    def load_word_list(path: Path) -> list[DetectedWord]:
        return load_words(path)

    @staticmethod
    def save_word_list(words: list[DetectedWord], path: Path) -> None:
        save_words(words, path)

    def discover_wordup(self) -> list[WindowSummary]:
        return self.target.discover()

    def connect_wordup(self, handle: int | None = None) -> WindowSummary:
        summary = self.target.connect(handle)
        self.engine = AutomationEngine(self.target, self.config.values)
        return summary

    def inspect_wordup(self) -> Path:
        if self.target.window is None:
            self.connect_wordup()
        output = self.paths["logs"] / "wordup_ui_tree.txt"
        UIInspector().inspect(self.target, output)
        return output

    def start_session(self, words: list[DetectedWord], dry_run: bool) -> SessionState:
        self.session = self.session_store.create(words, dry_run)
        self.session_store.save(self.session)
        return self.session

    def persist_word(self, index: int) -> None:
        if self.session is None:
            return
        self.session.current_index = index + 1
        self.session_store.save(self.session)
        self.history.append(self.session.words[index], self.session.session_id)

    def finish_session(self, clean: bool = True) -> None:
        if self.session is not None:
            self.session.stopped_cleanly = clean
            self.session_store.save(self.session)

    def resumable_session(self) -> SessionState | None:
        latest = self.session_store.latest_resumable()
        return latest[1] if latest else None

    def retryable_words(self, words: list[DetectedWord]) -> list[DetectedWord]:
        retry_states = {ImportResult.NOT_FOUND, ImportResult.AMBIGUOUS, ImportResult.FAILED}
        return [word for word in words if word.selected and word.result in retry_states]
