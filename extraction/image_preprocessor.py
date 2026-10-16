"""Create OCR-friendly black text on white crops from colored tiles."""

from __future__ import annotations

import cv2
import numpy as np


def crop_with_padding(image: np.ndarray, bbox: tuple[int, int, int, int],
                      inset_ratio: float = 0.04) -> np.ndarray:
    x, y, w, h = bbox
    inset_x = int(w * inset_ratio)
    inset_y = int(h * inset_ratio)
    return image[y + inset_y:y + h - inset_y, x + inset_x:x + w - inset_x]


def preprocess_tile(tile: np.ndarray, scale: int = 3,
                    dark_text: bool = False) -> np.ndarray:
    if dark_text:
        processed = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
    else:
        hsv = cv2.cvtColor(tile, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        white_text = ((saturation < 105) & (value > 135)).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        white_text = cv2.morphologyEx(white_text, cv2.MORPH_CLOSE, kernel)
        processed = cv2.bitwise_not(white_text)
    resized = cv2.resize(processed, None, fx=scale, fy=scale,
                         interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(resized, 24, 24, 32, 32, cv2.BORDER_CONSTANT, value=255)
