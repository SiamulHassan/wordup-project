"""Lazy OCR adapter with RapidOCR and Tesseract backends."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from utils.exceptions import OCRFailureError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OCRResult:
    text: str
    confidence: float


class OCREngine:
    def __init__(self, engine: str = "auto", tesseract_cmd: str = "") -> None:
        self.preference = engine.lower()
        self.tesseract_cmd = tesseract_cmd
        self._backend_name = ""
        self._backend: object | None = None

    @property
    def backend_name(self) -> str:
        self._ensure_backend()
        return self._backend_name

    def _ensure_backend(self) -> None:
        if self._backend is not None:
            return
        errors: list[str] = []
        if self.preference in {"auto", "rapidocr"}:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._backend = RapidOCR()
                self._backend_name = "rapidocr"
                return
            except Exception as exc:  # optional native dependency discovery
                errors.append(f"RapidOCR: {exc}")
        if self.preference in {"auto", "tesseract"}:
            try:
                import pytesseract
                if self.tesseract_cmd:
                    pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
                pytesseract.get_tesseract_version()
                self._backend = pytesseract
                self._backend_name = "tesseract"
                return
            except Exception as exc:
                errors.append(f"Tesseract: {exc}")
        raise OCRFailureError("No OCR backend is available. " + " | ".join(errors))

    def recognize(self, image: np.ndarray) -> OCRResult:
        self._ensure_backend()
        if self._backend_name == "rapidocr":
            # Detection remains constrained to this one tile crop. It supplies a reliable line
            # boundary and substantially better confidence than recognition-only mode.
            result, _ = self._backend(image)  # type: ignore[operator]
            if not result:
                return OCRResult("", 0.0)
            candidates: list[tuple[str, float]] = []
            for item in result:
                if len(item) >= 3:  # [quadrilateral, text, confidence]
                    candidates.append((str(item[1]), float(item[2])))
                elif len(item) == 2:  # recognition-only compatibility
                    candidates.append((str(item[0]), float(item[1])))
            best = max(candidates, key=lambda item: item[1], default=("", 0.0))
            return OCRResult(*best)
        data = self._backend.image_to_data(  # type: ignore[union-attr]
            image, config="--psm 7", output_type=self._backend.Output.DICT  # type: ignore[union-attr]
        )
        candidates: list[tuple[str, float]] = []
        for text, confidence in zip(data["text"], data["conf"]):
            try:
                score = float(confidence) / 100.0
            except (TypeError, ValueError):
                continue
            if str(text).strip() and score >= 0:
                candidates.append((str(text).strip(), score))
        if not candidates:
            return OCRResult("", 0.0)
        return OCRResult(" ".join(item[0] for item in candidates), min(item[1] for item in candidates))
