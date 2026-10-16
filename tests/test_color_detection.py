from __future__ import annotations

import cv2
import numpy as np

from extraction.color_detector import ColorDetector, HSVRange


def detector() -> ColorDetector:
    return ColorDetector(HSVRange(128, 160, 105, 95), HSVRange(82, 105, 80, 90), 3)


def test_purple_is_selected_and_cyan_is_rejected() -> None:
    image = np.full((160, 500, 3), 245, dtype=np.uint8)
    cv2.rectangle(image, (20, 20), (230, 110), (248, 32, 176), -1)  # BGR purple
    cv2.rectangle(image, (270, 20), (480, 110), (208, 192, 48), -1)  # BGR cyan
    purple = detector().purple_mask(image)
    assert purple[60, 100] == 255
    assert purple[60, 350] == 0


def test_cyan_mask_does_not_include_purple() -> None:
    image = np.full((100, 240, 3), (248, 32, 176), dtype=np.uint8)
    cyan = detector().cyan_mask(image)
    assert np.count_nonzero(cyan) == 0


def test_neutral_mask_selects_light_tile_but_not_white_page_or_colours() -> None:
    image = np.full((180, 760, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (20, 30), (220, 130), (230, 230, 236), -1)
    cv2.putText(image, "Fin", (85, 90), cv2.FONT_HERSHEY_SIMPLEX,
                1.0, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.rectangle(image, (270, 30), (470, 130), (248, 32, 176), -1)
    cv2.rectangle(image, (520, 30), (720, 130), (208, 192, 48), -1)

    neutral = detector().neutral_mask(image)

    assert neutral[50, 50] == 255
    assert neutral[10, 10] == 0
    assert neutral[50, 300] == 0
    assert neutral[50, 550] == 0
