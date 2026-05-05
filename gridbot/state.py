"""OCR-driven state classification.

Given a screenshot, decide which named "screen" or "mode" the device is
currently showing — login page, main menu, in-game battle, settings dialog,
etc. — by checking each :class:`StateRule` in order and returning the name
of the first one that matches.

The rules themselves are entirely **user-supplied** — gridbot ships *no*
default rule set, since rules are inherently app-specific. Authoring rules
typically looks like:

    1. Capture a few screenshots of each screen you care about with
       :class:`gridbot.AdbCapture`.
    2. Run :class:`gridbot.OcrEngine` on each and copy out a few stable
       text fragments (UI labels, headings).
    3. Encode each screen as a :class:`StateRule` using whichever combination
       of ``keywords_all`` / ``keywords_any`` / ``keyword_counts`` /
       ``forbidden`` / ``regex_any`` cleanly distinguishes it.
    4. Order rules from most-specific to most-generic. The detector returns
       the first match.

Example:
    >>> from gridbot import StateDetector, StateRule
    >>> rules = [
    ...     StateRule(
    ...         name="login",
    ...         keywords_any=["Tap to start", "Touch to play"],
    ...     ),
    ...     StateRule(
    ...         name="main_menu",
    ...         keywords_all=["Settings", "Inventory"],
    ...     ),
    ...     StateRule(
    ...         name="in_battle",
    ...         regex_any=[r"Stage \\d+", r"Wave \\d+"],
    ...     ),
    ... ]
    >>> detector = StateDetector(rules)
    >>> detector.detect(img)
    'main_menu'
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from loguru import logger

from gridbot.ocr import OcrEngine, OcrResult


@dataclass(frozen=True)
class StateRule:
    """Rule describing how to recognise one named state from OCR output.

    A rule matches if **all** of the following hold:

    - Every entry in ``keywords_all`` appears as a substring of some OCR text.
    - If ``keywords_any`` is non-empty, at least one of its entries appears.
    - For each ``(keyword, n)`` in ``keyword_counts``, ``keyword`` appears in
      at least ``n`` separate OCR detections.
    - **None** of the entries in ``forbidden`` appear anywhere.
    - If ``regex_any`` is non-empty, at least one of its patterns matches some
      OCR text (via :func:`re.search`).

    Args:
        name: Stable identifier returned by the detector when this rule wins.
            Conventionally lowercase_snake_case.
        description: Human-readable explanation, surfaced in debug output.
        keywords_all: All of these substrings must be present.
        keywords_any: At least one of these substrings must be present.
        keyword_counts: Map of substring → minimum occurrences across the
            OCR detection list.
        forbidden: If any of these substrings appear, the rule fails.
        regex_any: At least one of these regex patterns must match some
            individual OCR text.
    """

    name: str
    description: str = ""
    keywords_all: List[str] = field(default_factory=list)
    keywords_any: List[str] = field(default_factory=list)
    keyword_counts: Dict[str, int] = field(default_factory=dict)
    forbidden: List[str] = field(default_factory=list)
    regex_any: List[str] = field(default_factory=list)

    def match(self, results: List[OcrResult]) -> bool:
        """Return ``True`` if this rule matches the given OCR detections."""
        joined = " ".join(r.text for r in results)

        # 1. forbidden: any hit kills the rule.
        for kw in self.forbidden:
            if kw in joined:
                return False

        # 2. keywords_all: every entry must appear.
        for kw in self.keywords_all:
            if kw not in joined:
                return False

        # 3. keywords_any: at least one (only enforced when non-empty).
        if self.keywords_any:
            if not any(kw in joined for kw in self.keywords_any):
                return False

        # 4. keyword_counts: count individual detections, not raw substring hits.
        for kw, min_count in self.keyword_counts.items():
            count = sum(1 for r in results if kw in r.text)
            if count < min_count:
                return False

        # 5. regex_any: at least one pattern hits at least one detection.
        if self.regex_any:
            if not any(
                re.search(pat, r.text)
                for pat in self.regex_any
                for r in results
            ):
                return False

        return True


class StateDetector:
    """Classify a screenshot into one of a user-supplied list of named states.

    Args:
        rules: Rule list, **required**. Order matters — the first rule that
            matches wins, so order from most-specific to most-generic.
        fast_ocr: Use the PaddleOCR mobile model (faster, slightly less
            accurate). Recommended for live polling; flip to ``False`` for
            high-stakes one-shot reads.
        ocr_lang: PaddleOCR language code. Defaults to ``"ch"`` which handles
            both Simplified and Traditional Chinese plus English.

    Raises:
        ValueError: If ``rules`` is empty.
    """

    UNKNOWN = "unknown"

    def __init__(
        self,
        rules: List[StateRule],
        *,
        fast_ocr: bool = True,
        ocr_lang: str = "ch",
    ):
        if not rules:
            raise ValueError(
                "StateDetector requires a non-empty `rules` list. "
                "See the module docstring for an example of authoring rules."
            )
        self.rules = list(rules)
        self.ocr = OcrEngine.get(lang=ocr_lang, fast=fast_ocr)
        logger.info(
            f"StateDetector ready: {len(self.rules)} rule(s), fast_ocr={fast_ocr}"
        )

    def detect(
        self,
        image: np.ndarray,
        results: Optional[List[OcrResult]] = None,
    ) -> str:
        """Return the name of the first matching rule, or ``"unknown"``.

        Args:
            image: BGR ndarray (the format :class:`gridbot.AdbCapture` returns).
            results: Pre-computed OCR results to reuse — passing this skips
                a fresh OCR call. Useful when the caller already needs the
                detections for other purposes on the same frame.
        """
        if results is None:
            results = self.ocr.read(image)

        for rule in self.rules:
            if rule.match(results):
                logger.debug(f"matched: {rule.name}")
                return rule.name

        return self.UNKNOWN

    def detect_with_details(
        self,
        image: np.ndarray,
        results: Optional[List[OcrResult]] = None,
    ) -> Dict:
        """Return a diagnostic dict — useful for debugging or logging.

        The dict contains ``state`` (the matched rule name or ``"unknown"``),
        ``description``, ``ocr_count``, and ``ocr_texts_top10`` (a list of the
        first 10 detections formatted as ``"[conf] text"``).
        """
        if results is None:
            results = self.ocr.read(image)

        top10 = [f"[{r.confidence:.2f}] {r.text}" for r in results[:10]]

        for rule in self.rules:
            if rule.match(results):
                return {
                    "state": rule.name,
                    "description": rule.description,
                    "ocr_count": len(results),
                    "ocr_texts_top10": top10,
                }

        return {
            "state": self.UNKNOWN,
            "description": "no rule matched",
            "ocr_count": len(results),
            "ocr_texts_top10": top10,
        }
