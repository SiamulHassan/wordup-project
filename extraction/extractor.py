"""End-to-end screenshot extraction with caching and debug artifacts."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable

import cv2

from app.state import DetectedWord, ExtractionStats, ReviewStatus
from extraction.color_detector import ColorDetector, HSVRange, NeutralRange
from extraction.image_preprocessor import crop_with_padding, preprocess_tile
from extraction.ocr_engine import OCREngine
from extraction.screenshot_loader import load_image
from extraction.tile_detector import TileDetector, TileRules, draw_tiles
from extraction.word_normalizer import deduplicate, looks_uncertain, normalize_display

LOGGER = logging.getLogger(__name__)
CACHE_VERSION = b"wordup-extractor-v2-white-tiles\0"
ProgressCallback = Callable[[int, int, str], None]


class VocabularyExtractor:
    def __init__(self, config: dict[str, Any], cache_dir: Path, debug_dir: Path) -> None:
        purple_config = config["purple_detection"]
        white_config = config.get("white_detection", {})
        self.color_detector = ColorDetector(
            HSVRange.from_config(purple_config),
            HSVRange.from_config(config["cyan_detection"]),
            int(purple_config.get("morph_kernel", 5)),
            NeutralRange.from_config(config.get("white_detection", {})),
        )
        self.tile_detector = TileDetector(TileRules(
            min_area_ratio=float(purple_config.get("min_area_ratio", 0.0015)),
            max_area_ratio=float(purple_config.get("max_area_ratio", 0.04)),
            min_aspect_ratio=float(purple_config.get("min_aspect_ratio", 1.7)),
            max_aspect_ratio=float(purple_config.get("max_aspect_ratio", 6.0)),
            min_fill_ratio=float(purple_config.get("min_fill_ratio", 0.72)),
        ))
        self.white_tile_detector = TileDetector(TileRules(
            min_area_ratio=float(white_config.get("min_area_ratio", 0.0015)),
            max_area_ratio=float(white_config.get("max_area_ratio", 0.08)),
            min_aspect_ratio=float(white_config.get("min_aspect_ratio", 1.7)),
            max_aspect_ratio=float(white_config.get("max_aspect_ratio", 6.0)),
            min_fill_ratio=float(white_config.get("min_fill_ratio", 0.72)),
        ))
        ocr = config["ocr"]
        self.ocr = OCREngine(str(ocr.get("engine", "auto")), str(ocr.get("tesseract_cmd", "")))
        self.minimum_confidence = float(ocr.get("minimum_confidence", 0.75))
        self.cache_dir = cache_dir
        self.debug_dir = debug_dir
        self.debug_enabled = bool(config.get("debug", {}).get("extraction", False))

    @staticmethod
    def _cache_key(path: Path) -> str:
        digest = hashlib.sha256()
        digest.update(CACHE_VERSION)
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def extract(self, paths: list[Path], progress: ProgressCallback | None = None,
                use_cache: bool = True) -> tuple[list[DetectedWord], ExtractionStats]:
        all_words: list[DetectedWord] = []
        stats = ExtractionStats(screenshots=len(paths))
        for index, path in enumerate(paths, start=1):
            if progress:
                progress(index - 1, len(paths), f"Analyzing {path.name}")
            words, purple_count, white_count, cyan_count = self.extract_one(path, use_cache)
            all_words.extend(words)
            stats.purple_tiles += purple_count
            stats.white_tiles += white_count
            stats.cyan_tiles += cyan_count
        unique = deduplicate(all_words)
        stats.unique_words = len(unique)
        stats.low_confidence = sum(
            word.review_status == ReviewStatus.LOW_CONFIDENCE for word in unique
        )
        if progress:
            progress(len(paths), len(paths), "Extraction complete")
        return unique, stats

    def extract_one(self, path: Path, use_cache: bool = True
                    ) -> tuple[list[DetectedWord], int, int, int]:
        cache_key = self._cache_key(path)
        cache_path = self.cache_dir / f"{cache_key}.json"
        if use_cache and cache_path.exists():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return ([DetectedWord.from_dict(item) for item in data["words"]],
                    int(data["purple_count"]), int(data["white_count"]),
                    int(data["cyan_count"]))
        image = load_image(path)
        purple_mask = self.color_detector.purple_mask(image)
        cyan_mask = self.color_detector.cyan_mask(image)
        white_mask = self.color_detector.neutral_mask(image)
        purple_tiles = self.tile_detector.detect(purple_mask, "purple")
        cyan_tiles = self.tile_detector.detect(cyan_mask, "cyan")
        white_tiles = self.white_tile_detector.detect(white_mask, "white")
        import_tiles = self.tile_detector.sort_reading_order(purple_tiles + white_tiles)
        words: list[DetectedWord] = []
        debug_crops: list[tuple[int, Any]] = []
        for index, tile in enumerate(import_tiles, start=1):
            crop = crop_with_padding(image, tile.bbox)
            processed = preprocess_tile(crop, dark_text=tile.color_class == "white")
            result = self.ocr.recognize(processed)
            text = normalize_display(result.text)
            review = (ReviewStatus.LOW_CONFIDENCE
                      if result.confidence < self.minimum_confidence or looks_uncertain(text)
                      else ReviewStatus.READY)
            words.append(DetectedWord(
                text=text or f"Unrecognized tile {index}",
                confidence=result.confidence,
                sources=[str(path)],
                bbox=tile.bbox,
                color_class=tile.color_class,
                review_status=review,
            ))
            debug_crops.append((index, processed))
        data = {
            "words": [word.to_dict() for word in words],
            "purple_count": len(purple_tiles),
            "white_count": len(white_tiles),
            "cyan_count": len(cyan_tiles),
        }
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temporary = cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(cache_path)
        if self.debug_enabled:
            self._write_debug(path, image, purple_mask, cyan_mask, white_mask,
                              purple_tiles, cyan_tiles, white_tiles, debug_crops, words)
        return words, len(purple_tiles), len(white_tiles), len(cyan_tiles)

    def _write_debug(self, source: Path, image: Any, purple_mask: Any, cyan_mask: Any,
                     white_mask: Any, purple_tiles: list[Any], cyan_tiles: list[Any],
                     white_tiles: list[Any], crops: list[tuple[int, Any]],
                     words: list[DetectedWord]) -> None:
        output = self.debug_dir / f"{source.stem}_{self._cache_key(source)[:8]}"
        crop_dir = output / "crops"
        crop_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output / "original.png"), image)
        cv2.imwrite(str(output / "purple_mask.png"), purple_mask)
        cv2.imwrite(str(output / "cyan_mask.png"), cyan_mask)
        cv2.imwrite(str(output / "white_mask.png"), white_mask)
        cv2.imwrite(str(output / "detected_tiles.png"),
                    draw_tiles(image, purple_tiles, cyan_tiles, white_tiles))
        for index, crop in crops:
            cv2.imwrite(str(crop_dir / f"tile_{index:03d}.png"), crop)
        (output / "ocr_results.json").write_text(
            json.dumps([word.to_dict() for word in words], indent=2), encoding="utf-8"
        )
