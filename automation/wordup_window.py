"""WordUp process/window discovery and foreground safety checks."""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass

from pywinauto import Desktop
from pywinauto.application import Application

from utils.exceptions import UnsafeAutomationError, WordUpNotFoundError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WindowSummary:
    handle: int
    title: str
    rectangle: tuple[int, int, int, int]
    process_id: int


def is_wordup_app_window(title: str, class_name: str) -> bool:
    """Reject unrelated windows whose titles merely contain the project name."""
    normalized_title = title.strip().casefold()
    if normalized_title == "wordup":
        return True
    return (
        normalized_title.startswith("wordup")
        and class_name.strip().casefold() == "flutter_runner_win32_window"
    )


class WordUpWindow:
    def __init__(self, title_regex: str = ".*WordUp.*") -> None:
        self.title_regex = title_regex
        self.application: Application | None = None
        self.window: object | None = None

    def discover(self) -> list[WindowSummary]:
        pattern = re.compile(self.title_regex, re.IGNORECASE)
        found: list[WindowSummary] = []
        for window in Desktop(backend="uia").windows():
            try:
                title = window.window_text().strip()
                class_name = str(window.class_name() or "")
                pid = int(window.process_id())
                rect = window.rectangle()
            except Exception:
                continue
            if (not title or not pattern.fullmatch(title) or pid == os.getpid()
                    or not is_wordup_app_window(title, class_name)):
                continue
            found.append(WindowSummary(
                handle=int(window.handle),
                title=title,
                rectangle=(rect.left, rect.top, rect.right, rect.bottom),
                process_id=pid,
            ))
        return found

    def connect(self, handle: int | None = None) -> WindowSummary:
        choices = self.discover()
        if handle is not None:
            choices = [item for item in choices if item.handle == handle]
        if not choices:
            raise WordUpNotFoundError("Open the WordUp Windows app, then click Refresh.")
        target = max(choices, key=lambda item: (
            item.title.strip().casefold() == "wordup",
            item.title.strip().casefold().startswith("wordup"),
            (item.rectangle[2] - item.rectangle[0]) * (item.rectangle[3] - item.rectangle[1]),
        ))
        self.application = Application(backend="uia").connect(handle=target.handle)
        self.window = self.application.window(handle=target.handle)
        LOGGER.info("Connected to WordUp: %s (handle=%s)", target.title, target.handle)
        return target

    @property
    def handle(self) -> int:
        if self.window is None:
            raise WordUpNotFoundError("WordUp is not connected.")
        return int(self.window.handle)

    def rectangle(self) -> tuple[int, int, int, int]:
        if self.window is None:
            raise WordUpNotFoundError("WordUp is not connected.")
        rect = self.window.rectangle()
        return rect.left, rect.top, rect.right, rect.bottom

    def bring_to_front(self, timeout: float = 4.0) -> None:
        if self.window is None:
            raise WordUpNotFoundError("WordUp is not connected.")
        try:
            if self.window.is_minimized():
                self.window.restore()
            self.window.set_focus()
        except Exception as exc:
            raise UnsafeAutomationError(f"Could not activate WordUp: {exc}") from exc
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_foreground():
                return
            time.sleep(0.08)
        raise UnsafeAutomationError("WordUp did not become the foreground window.")

    def is_foreground(self) -> bool:
        try:
            import win32gui
            foreground = win32gui.GetForegroundWindow()
            return foreground == self.handle or win32gui.IsChild(self.handle, foreground)
        except Exception:
            try:
                return bool(self.window.is_active())
            except Exception:
                return False

    def ensure_foreground(self) -> None:
        if not self.is_foreground():
            self.bring_to_front()
        if not self.is_foreground():
            raise UnsafeAutomationError("Automation paused because WordUp is not foreground.")

    def descendants(self, control_type: str | None = None) -> list[object]:
        if self.window is None:
            raise WordUpNotFoundError("WordUp is not connected.")
        try:
            return list(self.window.descendants(control_type=control_type))
        except Exception:
            return []
