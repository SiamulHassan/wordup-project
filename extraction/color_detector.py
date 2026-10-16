"""Robust HSV background segmentation for WordUp tile classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class HSVRange:
    hue_min: int
    hue_max: int
    saturation_min: int
    value_min: int

    @classmethod
    def from_config(cls, values: dict[str, Any]) -> "HSVRange":
        return cls(
            hue_min=int(values["hue_min"]),
            hue_max=int(values["hue_max"]),
            saturation_min=int(values["saturation_min"]),
            value_min=int(values["value_min"]),
        )


@dataclass(frozen=True, slots=True)
class NeutralRange:
    saturation_max: int = 45
    value_min: int = 170
    value_max: int = 244

    @classmethod
    def from_config(cls, values: dict[str, Any]) -> "NeutralRange":
        return cls(
            saturation_max=int(values.get("saturation_max", 45)),
            value_min=int(values.get("value_min", 170)),
            value_max=int(values.get("value_max", 244)),
        )


class ColorDetector:
    def __init__(self, purple: HSVRange, cyan: HSVRange, morph_kernel: int = 5,
                 neutral: NeutralRange | None = None) -> None:
        self.purple = purple
        self.cyan = cyan
        self.neutral = neutral or NeutralRange()
        self.morph_kernel = max(1, morph_kernel | 1)

    def _clean(self, mask: np.ndarray) -> np.ndarray:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (self.morph_kernel, self.morph_kernel)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    def _mask(self, image: np.ndarray, color_range: HSVRange) -> np.ndarray:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower = np.array([
            color_range.hue_min, color_range.saturation_min, color_range.value_min
        ], dtype=np.uint8)
        upper = np.array([color_range.hue_max, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        return self._clean(mask)

    def purple_mask(self, image: np.ndarray) -> np.ndarray:
        return self._mask(image, self.purple)

    def cyan_mask(self, image: np.ndarray) -> np.ndarray:
        return self._mask(image, self.cyan)

    def neutral_mask(self, image: np.ndarray) -> np.ndarray:
        """Select light, low-saturation uncoloured tiles but not pure page white."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower = np.array([0, 0, self.neutral.value_min], dtype=np.uint8)
        upper = np.array([
            179, self.neutral.saturation_max, self.neutral.value_max
        ], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        # White-tile gutters are narrow. A second close pass would bridge them
        # and merge the complete grid into one contour.
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (self.morph_kernel, self.morph_kernel)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
        return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
