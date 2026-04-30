"""OCR engine wrapping PaddleOCR.

The wrapper:

- Lazily loads PaddleOCR (the first call takes 1–3 seconds; subsequent calls
  are milliseconds).
- Caches one engine per ``(lang, fast)`` pair.
- Returns structured :class:`OcrResult` objects with text, confidence, the
  four-corner bbox, and convenience accessors for the centre point and the
  axis-aligned bounding rect.
- Supports both PaddleOCR 3.x (``predict()``) and 2.x (``ocr()``) automatically.

Example:
    >>> from gridbot import AdbCapture, OcrEngine
    >>> ocr = OcrEngine.get(fast=True)
    >>> img = AdbCapture().screenshot()
    >>> for r in ocr.read(img):
    ...     print(r.text, r.confidence, r.center)
    >>> btn = ocr.find_text(img, "Settings")
    >>> if btn:
    ...     print("found at", btn.center)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger

BBox = Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int], Tuple[int, int]]


class OcrError(Exception):
    """Raised when OCR fails or PaddleOCR is not installed."""


@dataclass(frozen=True)
class OcrResult:
    """One detected text region."""

    text: str
    confidence: float           # 0.0 to 1.0
    bbox: BBox                  # Four corners, clockwise: TL, TR, BR, BL.

    @property
    def center(self) -> Tuple[int, int]:
        """Centre of the bbox — the natural target for ``AdbInput.tap``."""
        xs = [p[0] for p in self.bbox]
        ys = [p[1] for p in self.bbox]
        return (sum(xs) // 4, sum(ys) // 4)

    @property
    def rect(self) -> Tuple[int, int, int, int]:
        """Axis-aligned bounding rect ``(x_min, y_min, x_max, y_max)``."""
        xs = [p[0] for p in self.bbox]
        ys = [p[1] for p in self.bbox]
        return (min(xs), min(ys), max(xs), max(ys))


class OcrEngine:
    """PaddleOCR wrapper with per-(lang, fast) singleton caching.

    PaddleOCR ships two model families:

    - **Server** (``fast=False``, default): higher accuracy, slower on CPU.
    - **Mobile** (``fast=True``): roughly 3–5x faster, ~5% accuracy hit.

    A typical mix: use ``fast=True`` for quick state-detection polls, and
    ``fast=False`` for high-stakes reads like extracting numbers from a
    rewards screen.
    """

    _instances: Dict[str, "OcrEngine"] = {}

    @classmethod
    def get(cls, lang: str = "ch", fast: bool = False) -> "OcrEngine":
        """Return the cached engine for ``(lang, fast)``, constructing it on first use.

        Args:
            lang: PaddleOCR language code. ``"ch"`` handles both Simplified
                and Traditional Chinese plus English; ``"en"`` is English-only;
                see PaddleOCR docs for the full list.
            fast: ``True`` to use mobile models, ``False`` for server models.
        """
        key = f"{lang}_{'fast' if fast else 'server'}"
        if key not in cls._instances:
            cls._instances[key] = cls(lang=lang, fast=fast)
        return cls._instances[key]

    def __init__(self, lang: str = "ch", fast: bool = False):
        try:
            from paddleocr import PaddleOCR
        except ImportError as e:
            raise OcrError(
                "paddleocr is not installed. Install the OCR extras with:\n"
                "    pip install 'gridbot[ocr]'"
            ) from e

        mode = "mobile (fast)" if fast else "server (accurate)"
        logger.info(f"Loading PaddleOCR lang={lang} mode={mode}...")

        common_kwargs = dict(
            lang=lang,
            use_textline_orientation=True,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
        )
        if fast:
            common_kwargs.update(
                text_detection_model_name="PP-OCRv5_mobile_det",
                text_recognition_model_name="PP-OCRv5_mobile_rec",
            )

        # PaddleOCR 3.x API; fall back to 2.x on TypeError.
        try:
            self._ocr = PaddleOCR(**common_kwargs)
            self._api = "v3"
        except TypeError:
            logger.warning("PaddleOCR 3.x API unavailable; falling back to 2.x")
            self._ocr = PaddleOCR(use_angle_cls=True, lang=lang)
            self._api = "v2"

        self._fast = fast
        logger.info(f"PaddleOCR loaded ({self._api} API, {mode})")

    def read(self, image: np.ndarray) -> List[OcrResult]:
        """Run OCR on a BGR image.

        Args:
            image: BGR ``numpy`` array (the format :class:`AdbCapture` returns).

        Returns:
            List of :class:`OcrResult`. Empty list for empty images or no
            detected text.
        """
        if image is None or image.size == 0:
            return []

        if self._api == "v3":
            return self._read_v3(image)
        return self._read_v2(image)

    def find_text(
        self,
        image: np.ndarray,
        keyword: str,
        *,
        exact: bool = False,
        min_confidence: float = 0.7,
        results: Optional[List[OcrResult]] = None,
    ) -> Optional[OcrResult]:
        """Return the first detection containing ``keyword``, or ``None``.

        Args:
            keyword: The text to search for.
            exact: ``True`` for equality, ``False`` for substring (default).
            min_confidence: Drop detections below this confidence.
            results: A pre-computed result list. If provided, OCR is **not**
                re-run — pass this when querying multiple keywords on the
                same frame to avoid the cost of repeated OCR.

        Example:
            >>> all_results = ocr.read(img)
            >>> btn = ocr.find_text(img, "Settings", results=all_results)
            >>> exit_btn = ocr.find_text(img, "Exit", results=all_results)
            >>> if btn:
            ...     inp.tap(*btn.center)
        """
        if results is None:
            results = self.read(image)
        for r in results:
            if r.confidence < min_confidence:
                continue
            if exact:
                if r.text == keyword:
                    return r
            else:
                if keyword in r.text:
                    return r
        return None

    def find_all_texts(
        self,
        image: np.ndarray,
        keyword: str,
        *,
        exact: bool = False,
        min_confidence: float = 0.7,
        results: Optional[List[OcrResult]] = None,
    ) -> List[OcrResult]:
        """Return *every* detection matching ``keyword``."""
        if results is None:
            results = self.read(image)
        out = []
        for r in results:
            if r.confidence < min_confidence:
                continue
            if exact and r.text == keyword:
                out.append(r)
            elif not exact and keyword in r.text:
                out.append(r)
        return out

    def read_region(
        self,
        image: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> List[OcrResult]:
        """OCR only the rectangle ``(x1, y1) -> (x2, y2)`` of ``image``.

        Often 5–10x faster than full-image OCR and reduces background noise.
        Useful when you know exactly where the value lives (e.g. "the gold
        counter in the top-right corner").

        Returned bboxes are translated back to the **original** image
        coordinate system, not the cropped one.
        """
        h, w = image.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return []

        crop = image[y1:y2, x1:x2]
        results = self.read(crop)

        translated = []
        for r in results:
            new_bbox = tuple((p[0] + x1, p[1] + y1) for p in r.bbox)
            translated.append(OcrResult(
                text=r.text,
                confidence=r.confidence,
                bbox=new_bbox,  # type: ignore[arg-type]
            ))
        return translated

    # ----- Private: API-version dispatch -----

    def _read_v3(self, image: np.ndarray) -> List[OcrResult]:
        """PaddleOCR 3.x: ``predict()`` returns a list of result objects."""
        try:
            raw = self._ocr.predict(input=image)
        except Exception as e:
            raise OcrError(f"OCR predict() failed: {e}") from e

        results: List[OcrResult] = []
        for page in raw:
            texts = self._safe_get(page, "rec_texts", [])
            scores = self._safe_get(page, "rec_scores", [])
            polys = self._safe_get(page, "rec_polys", [])

            for text, score, poly in zip(texts, scores, polys):
                bbox = tuple((int(pt[0]), int(pt[1])) for pt in poly)
                if len(bbox) != 4:
                    continue
                results.append(OcrResult(
                    text=str(text),
                    confidence=float(score),
                    bbox=bbox,  # type: ignore[arg-type]
                ))
        return results

    def _read_v2(self, image: np.ndarray) -> List[OcrResult]:
        """PaddleOCR 2.x: ``ocr()`` returns a nested list."""
        try:
            raw = self._ocr.ocr(image, cls=True)
        except Exception as e:
            raise OcrError(f"OCR failed: {e}") from e

        results: List[OcrResult] = []
        if not raw or not raw[0]:
            return results

        for line in raw[0]:
            bbox_pts, (text, conf) = line
            bbox = tuple((int(p[0]), int(p[1])) for p in bbox_pts)
            if len(bbox) != 4:
                continue
            results.append(OcrResult(
                text=text,
                confidence=float(conf),
                bbox=bbox,  # type: ignore[arg-type]
            ))
        return results

    @staticmethod
    def _safe_get(obj, key: str, default):
        """Read ``key`` from a dict or attribute from an object — whichever it is."""
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)


def draw_results(image: np.ndarray, results: List[OcrResult]) -> np.ndarray:
    """Draw OCR detections onto a copy of ``image`` for visual debugging.

    - Green box: high confidence (>= 0.9)
    - Yellow box: medium confidence (0.7–0.9)
    - Red box: low confidence (< 0.7)
    """
    out = image.copy()
    for r in results:
        if r.confidence >= 0.9:
            color = (0, 255, 0)
        elif r.confidence >= 0.7:
            color = (0, 255, 255)
        else:
            color = (0, 0, 255)

        pts = np.array(r.bbox, dtype=np.int32)
        cv2.polylines(out, [pts], isClosed=True, color=color, thickness=2)
        x_min, y_min, _, _ = r.rect
        label = f"{r.text} ({r.confidence:.2f})"
        cv2.putText(
            out, label, (x_min, max(y_min - 5, 15)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA,
        )
    return out
