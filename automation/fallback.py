"""Window-relative keyboard/OCR/coordinate fallback isolated from UIA logic."""

from __future__ import annotations

import logging
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
import pyautogui

from automation.wordup_window import WordUpWindow
from extraction.word_normalizer import comparison_key
from utils.exceptions import SearchControlNotFoundError, ShouldLearnButtonNotFoundError

LOGGER = logging.getLogger(__name__)
pyautogui.FAILSAFE = True


@dataclass(frozen=True, slots=True)
class ScreenText:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int]


class ScreenOCR:
    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR()

    def recognize(self, image: np.ndarray) -> list[ScreenText]:
        result, _ = self.engine(image)
        texts: list[ScreenText] = []
        for item in result or []:
            points, text, score = item
            xs = [int(point[0]) for point in points]
            ys = [int(point[1]) for point in points]
            texts.append(ScreenText(str(text), float(score),
                                    (min(xs), min(ys), max(xs), max(ys))))
        return texts


class WindowFallback:
    def __init__(self, target: WordUpWindow, calibration: dict[str, Any],
                 confidence: float = 0.88) -> None:
        self.target = target
        self.calibration = calibration
        self.confidence = confidence
        self._ocr: ScreenOCR | None = None

    def _screen_ocr(self) -> ScreenOCR:
        if self._ocr is None:
            self._ocr = ScreenOCR()
        return self._ocr

    def screenshot(self) -> np.ndarray:
        self.target.ensure_foreground()
        left, top, right, bottom = self.target.rectangle()
        shot = pyautogui.screenshot(region=(left, top, right - left, bottom - top))
        return cv2.cvtColor(np.asarray(shot), cv2.COLOR_RGB2BGR)

    def screen_text(self) -> list[ScreenText]:
        return self._screen_ocr().recognize(self.screenshot())

    def find_exact_text(self, expected: str, minimum_confidence: float | None = None) -> list[ScreenText]:
        threshold = self.confidence if minimum_confidence is None else minimum_confidence
        key = comparison_key(unicodedata.normalize("NFKC", expected))
        return [item for item in self.screen_text()
                if item.confidence >= threshold and comparison_key(item.text) == key]

    def click_relative(self, name: str) -> None:
        value = self.calibration.get(name)
        if not isinstance(value, dict) or "x" not in value or "y" not in value:
            raise SearchControlNotFoundError(
                f"Fallback point '{name}' is not calibrated. Open Advanced → Calibration."
            )
        left, top, right, bottom = self.target.rectangle()
        x = left + round(float(value["x"]) * (right - left))
        y = top + round(float(value["y"]) * (bottom - top))
        self.target.ensure_foreground()
        pyautogui.click(x, y)

    def clear_search(self) -> None:
        self.click_relative("search_box")
        self.target.ensure_foreground()
        pyautogui.hotkey("ctrl", "a")
        self.target.ensure_foreground()
        pyautogui.press("backspace")

    def enter_search(self, word: str) -> None:
        self.clear_search()
        self.target.ensure_foreground()
        pyautogui.write(word, interval=0.025)
        self.target.ensure_foreground()
        pyautogui.press("enter")

    def click_text(self, expected: str) -> None:
        matches = self.find_exact_text(expected)
        if len(matches) != 1:
            raise ShouldLearnButtonNotFoundError(
                f"Expected exactly one high-confidence '{expected}' label; found {len(matches)}."
            )
        item = matches[0]
        left, top, _, _ = self.target.rectangle()
        x1, y1, x2, y2 = item.bbox
        self.target.ensure_foreground()
        pyautogui.click(left + (x1 + x2) // 2, top + (y1 + y2) // 2)

    def wait_for_exact_text(self, expected: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.find_exact_text(expected, 0.72):
                return True
            time.sleep(0.25)
        return False
