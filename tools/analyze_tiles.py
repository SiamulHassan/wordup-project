"""Generate color-mask and tile-overlay diagnostics without invoking OCR."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from extraction.color_detector import ColorDetector, HSVRange
from extraction.screenshot_loader import load_image
from extraction.tile_detector import TileDetector, TileRules, draw_tiles
from utils.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screenshot", type=Path)
    parser.add_argument("--output", type=Path, default=Path("debug-output"))
    args = parser.parse_args()
    config = load_config().values
    purple = config["purple_detection"]
    detector = ColorDetector(
        HSVRange.from_config(purple),
        HSVRange.from_config(config["cyan_detection"]),
        int(purple["morph_kernel"]),
    )
    tiles = TileDetector(TileRules(
        min_area_ratio=float(purple["min_area_ratio"]),
        max_area_ratio=float(purple["max_area_ratio"]),
        min_aspect_ratio=float(purple["min_aspect_ratio"]),
        max_aspect_ratio=float(purple["max_aspect_ratio"]),
        min_fill_ratio=float(purple["min_fill_ratio"]),
    ))
    image = load_image(args.screenshot)
    purple_mask = detector.purple_mask(image)
    cyan_mask = detector.cyan_mask(image)
    purple_tiles = tiles.detect(purple_mask, "purple")
    cyan_tiles = tiles.detect(cyan_mask, "cyan")
    args.output.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output / "purple_mask.png"), purple_mask)
    cv2.imwrite(str(args.output / "cyan_mask.png"), cyan_mask)
    cv2.imwrite(str(args.output / "detected_tiles.png"),
                draw_tiles(image, purple_tiles, cyan_tiles))
    print(f"Purple tiles: {len(purple_tiles)}")
    print(f"Cyan tiles ignored: {len(cyan_tiles)}")
    print(f"Debug output: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
