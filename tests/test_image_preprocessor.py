from __future__ import annotations

import cv2
import numpy as np

from extraction.image_preprocessor import preprocess_tile


def test_dark_text_on_light_tile_becomes_black_on_white() -> None:
    tile = np.full((80, 220, 3), (230, 230, 236), dtype=np.uint8)
    cv2.putText(tile, "Fin", (70, 53), cv2.FONT_HERSHEY_SIMPLEX,
                1.2, (20, 20, 20), 3, cv2.LINE_AA)

    processed = preprocess_tile(tile, scale=2, dark_text=True)

    assert processed[10, 10] == 255
    assert np.min(processed) < 50
    assert np.mean(processed) > 200
