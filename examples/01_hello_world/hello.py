"""Hello-world for gridbot.

What it does:

1. Connects to the first ADB device.
2. Takes one screenshot, saves it to ``./screenshots/``.
3. Runs OCR on the screenshot and prints every detected text snippet.
4. Saves an annotated copy showing where each detection landed.
5. Demonstrates the ``find_text`` helper by searching for a sample keyword.

Prereqs:
    pip install gridbot[ocr]
    # ADB must be on PATH, or set GRIDBOT_ADB_PATH to its full path.
    # An emulator or USB-debug-enabled phone must be connected.

Run:
    python examples/01_hello_world/hello.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
from loguru import logger

from gridbot import AdbCapture, AdbInput, OcrEngine, draw_results


# Change this to a string you expect to see on the device's current screen.
SAMPLE_KEYWORD = "Settings"


def main() -> int:
    out_dir = Path.cwd() / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("gridbot hello-world")
    logger.info("=" * 60)

    # ----- 1. Capture -----
    cap = AdbCapture()
    img = cap.screenshot()
    h, w = img.shape[:2]
    logger.info(f"captured {w}x{h} frame")

    raw_path = out_dir / "hello_raw.png"
    cv2.imwrite(str(raw_path), img)
    logger.info(f"raw screenshot saved: {raw_path.resolve()}")

    # ----- 2. OCR -----
    # `fast=True` uses PaddleOCR's mobile models — faster, slightly less accurate.
    # First run downloads the model (~30 MB) and may take a minute.
    ocr = OcrEngine.get(fast=True)
    t0 = time.time()
    results = ocr.read(img)
    logger.info(f"OCR took {time.time() - t0:.2f}s, found {len(results)} text regions")

    for i, r in enumerate(results[:20], 1):
        logger.info(f"  {i:2d}. [{r.confidence:.2f}] {r.text!r} @ {r.center}")
    if len(results) > 20:
        logger.info(f"  ... ({len(results) - 20} more omitted)")

    # ----- 3. Annotated visualisation -----
    annotated = draw_results(img, results)
    annotated_path = out_dir / "hello_annotated.png"
    cv2.imwrite(str(annotated_path), annotated)
    logger.info(f"annotated copy saved: {annotated_path.resolve()}")

    # ----- 4. find_text demo -----
    # Pass `results=` so we don't re-run OCR on the same frame.
    found = ocr.find_text(img, SAMPLE_KEYWORD, results=results)
    if found:
        logger.info(
            f"found {SAMPLE_KEYWORD!r} at {found.center} "
            f"(confidence {found.confidence:.2f})"
        )
        # Uncomment the next line to actually tap the matched text:
        # AdbInput().tap(*found.center)
    else:
        logger.info(
            f"keyword {SAMPLE_KEYWORD!r} not on this screen — "
            "edit SAMPLE_KEYWORD at the top of this file."
        )

    logger.info("=" * 60)
    logger.info("done. open the two PNGs above to see the result.")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
