from __future__ import annotations

import cv2
import numpy as np

from extraction.tile_detector import TileDetector, TileRules


def test_filters_noise_and_non_tile_shapes() -> None:
    mask = np.zeros((800, 600), dtype=np.uint8)
    cv2.rectangle(mask, (20, 50), (220, 115), 255, -1)
    cv2.rectangle(mask, (260, 50), (460, 115), 255, -1)
    cv2.rectangle(mask, (10, 10), (18, 18), 255, -1)
    cv2.circle(mask, (500, 500), 35, 255, -1)
    detector = TileDetector(TileRules(min_area_ratio=0.005, max_area_ratio=0.1))
    tiles = detector.detect(mask, "purple")
    assert len(tiles) == 2


def test_reading_order_is_row_then_column() -> None:
    mask = np.zeros((500, 600), dtype=np.uint8)
    for x, y in ((320, 200), (20, 40), (320, 40), (20, 200)):
        cv2.rectangle(mask, (x, y), (x + 220, y + 80), 255, -1)
    detector = TileDetector(TileRules(min_area_ratio=0.01, max_area_ratio=0.1))
    boxes = [item.bbox[:2] for item in detector.detect(mask, "purple")]
    assert boxes == [(20, 40), (320, 40), (20, 200), (320, 200)]
