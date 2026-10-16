"""Contour filtering and geometry-based vocabulary tile detection."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class TileCandidate:
    bbox: tuple[int, int, int, int]
    fill_ratio: float
    color_class: str


@dataclass(frozen=True, slots=True)
class TileRules:
    min_area_ratio: float = 0.0015
    max_area_ratio: float = 0.04
    min_aspect_ratio: float = 1.7
    max_aspect_ratio: float = 6.0
    min_fill_ratio: float = 0.72


class TileDetector:
    def __init__(self, rules: TileRules) -> None:
        self.rules = rules

    def detect(self, mask: np.ndarray, color_class: str) -> list[TileCandidate]:
        height, width = mask.shape[:2]
        image_area = float(height * width)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[TileCandidate] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            rect_area = float(w * h)
            area_ratio = rect_area / image_area
            aspect = w / max(h, 1)
            fill_ratio = cv2.contourArea(contour) / max(rect_area, 1.0)
            if not self.rules.min_area_ratio <= area_ratio <= self.rules.max_area_ratio:
                continue
            if not self.rules.min_aspect_ratio <= aspect <= self.rules.max_aspect_ratio:
                continue
            if fill_ratio < self.rules.min_fill_ratio:
                continue
            candidates.append(TileCandidate((x, y, w, h), fill_ratio, color_class))
        return self.sort_reading_order(self._remove_overlaps(candidates))

    @staticmethod
    def _remove_overlaps(candidates: list[TileCandidate]) -> list[TileCandidate]:
        kept: list[TileCandidate] = []
        for item in sorted(candidates, key=lambda c: c.bbox[2] * c.bbox[3], reverse=True):
            x, y, w, h = item.bbox
            duplicate = False
            for other in kept:
                ox, oy, ow, oh = other.bbox
                ix = max(0, min(x + w, ox + ow) - max(x, ox))
                iy = max(0, min(y + h, oy + oh) - max(y, oy))
                intersection = ix * iy
                if intersection / max(min(w * h, ow * oh), 1) > 0.75:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(item)
        return kept

    @staticmethod
    def sort_reading_order(candidates: list[TileCandidate]) -> list[TileCandidate]:
        """Cluster nearby vertical centers into rows, then order rows left-to-right."""
        if not candidates:
            return []
        median_height = float(np.median([item.bbox[3] for item in candidates]))
        tolerance = max(4.0, median_height * 0.55)
        rows: list[list[TileCandidate]] = []
        for item in sorted(candidates, key=lambda c: c.bbox[1] + c.bbox[3] / 2):
            center = item.bbox[1] + item.bbox[3] / 2
            if not rows:
                rows.append([item])
                continue
            row_center = float(np.mean([c.bbox[1] + c.bbox[3] / 2 for c in rows[-1]]))
            if abs(center - row_center) <= tolerance:
                rows[-1].append(item)
            else:
                rows.append([item])
        ordered: list[TileCandidate] = []
        for row in rows:
            ordered.extend(sorted(row, key=lambda c: c.bbox[0]))
        return ordered


def draw_tiles(image: np.ndarray, purple: list[TileCandidate],
               cyan: list[TileCandidate],
               white: list[TileCandidate] | None = None) -> np.ndarray:
    output = image.copy()
    for index, item in enumerate(purple, start=1):
        x, y, w, h = item.bbox
        cv2.rectangle(output, (x, y), (x + w, y + h), (40, 220, 40), 4)
        cv2.putText(output, f"P{index}", (x + 4, y + 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, (40, 220, 40), 2, cv2.LINE_AA)
    for index, item in enumerate(cyan, start=1):
        x, y, w, h = item.bbox
        cv2.rectangle(output, (x, y), (x + w, y + h), (0, 180, 255), 3)
        cv2.putText(output, f"C{index}", (x + 4, y + 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, (0, 180, 255), 2, cv2.LINE_AA)
    for index, item in enumerate(white or [], start=1):
        x, y, w, h = item.bbox
        cv2.rectangle(output, (x, y), (x + w, y + h), (255, 80, 40), 3)
        cv2.putText(output, f"W{index}", (x + 4, y + 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, (255, 80, 40), 2, cv2.LINE_AA)
    return output
