"""Verify gridbot is installed correctly — no Android device required.

Reads the bundled ``sample.png``, runs OCR on it, and asserts that a few
expected English keywords are detected. Useful as a 5-second smoke test
right after ``pip install`` to confirm OpenCV, NumPy, PaddleOCR, and the
gridbot package itself are all wired up correctly.

If this script prints "install verified" you're ready to move on to
``examples/01_hello_world`` (which needs a real device).
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

from gridbot import OcrEngine, draw_results

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / "sample.png"
EXPECTED = ["Settings", "Wi-Fi", "Bluetooth", "Battery", "Storage", "About phone"]


def main() -> int:
    if not SAMPLE.exists():
        print(f"sample image missing: {SAMPLE}", file=sys.stderr)
        return 2

    print("=" * 60)
    print("gridbot install check (no device required)")
    print("=" * 60)

    img = cv2.imread(str(SAMPLE))
    if img is None:
        print(f"could not read {SAMPLE} — OpenCV broken?", file=sys.stderr)
        return 2
    h, w = img.shape[:2]
    print(f"loaded {SAMPLE.name}: {w}x{h}")

    print("loading PaddleOCR (first call may download ~30 MB of model weights)...")
    ocr = OcrEngine.get(fast=True)

    print("running OCR...")
    results = ocr.read(img)
    print(f"detected {len(results)} text regions:")
    for r in results:
        print(f"  [{r.confidence:.2f}] {r.text!r}")

    found = [kw for kw in EXPECTED if any(kw in r.text for r in results)]
    missing = [kw for kw in EXPECTED if kw not in found]

    print()
    print(f"matched {len(found)}/{len(EXPECTED)} expected keywords: {found}")
    if missing:
        print(f"missing: {missing}")

    annotated = Path.cwd() / "sample.annotated.png"
    cv2.imwrite(str(annotated), draw_results(img, results))
    print(f"annotated copy: {annotated.resolve()}")

    if len(found) >= 4:
        print()
        print("install verified — gridbot + OCR are working")
        print("next: connect a device and run examples/01_hello_world/hello.py")
        return 0

    print()
    print("install incomplete — fewer expected keywords detected than expected.")
    print("most common cause: PaddleOCR model failed to download; re-run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
