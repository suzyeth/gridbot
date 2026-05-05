"""Command-line entry point for gridbot.

Run ``gridbot --help`` after installing the package to see the available
subcommands. The CLI is a thin wrapper over the public Python API and is
the fastest way to verify your install before writing any code.

Subcommands:

- ``gridbot doctor`` — preflight check: Python, deps, adb, devices, models.
- ``gridbot devices`` — list ADB devices.
- ``gridbot screenshot`` — capture a screenshot to a file.
- ``gridbot ocr <image>`` — run OCR on a local image file.
- ``gridbot watch`` — repeated capture + OCR, live in the terminal.
"""

from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional


# ---------- Output helpers (no color, no extra deps) ----------

OK = "[ok]  "
WARN = "[warn]"
FAIL = "[fail]"
INFO = "[info]"


def _print(prefix: str, msg: str, fix: Optional[str] = None) -> None:
    print(f"{prefix} {msg}")
    if fix:
        print(f"       fix: {fix}")


# ---------- doctor ----------

def cmd_doctor(_args) -> int:
    """Preflight check. Returns 0 if everything looks usable, 1 otherwise."""
    print("gridbot doctor — checking your install")
    print("-" * 60)

    failures = 0
    warnings = 0

    # Python version
    py = sys.version_info
    if py >= (3, 9):
        _print(OK, f"python {py.major}.{py.minor}.{py.micro}")
    else:
        _print(FAIL, f"python {py.major}.{py.minor}.{py.micro} — gridbot needs >= 3.9",
               fix="upgrade your Python interpreter")
        failures += 1

    # Core deps (always required)
    for mod in ["numpy", "cv2", "PIL", "loguru", "pydantic", "yaml"]:
        try:
            importlib.import_module(mod)
            _print(OK, f"{mod} importable")
        except ImportError as e:
            _print(FAIL, f"{mod} import failed: {e}",
                   fix="pip install -e . (or pip install gridbot)")
            failures += 1

    # OCR (optional)
    try:
        importlib.import_module("paddleocr")
        _print(OK, "paddleocr importable")
    except ImportError:
        _print(WARN, "paddleocr not installed — OCR features unavailable",
               fix="pip install -e .[ocr]  (or pip install gridbot[ocr])")
        warnings += 1

    # PaddleOCR model cache
    cache_dir = Path.home() / ".paddlex" / "official_models"
    if cache_dir.exists() and any(cache_dir.iterdir()):
        cached = sorted(p.name for p in cache_dir.iterdir() if p.is_dir())
        _print(OK, f"paddleocr model cache: {len(cached)} model(s) at {cache_dir}")
    else:
        _print(INFO, f"paddleocr model cache empty at {cache_dir}",
               fix="first OCR call will auto-download (~30 MB)")

    # adb binary
    try:
        from gridbot._adb import find_adb
        adb_path = find_adb()
        _print(OK, f"adb located: {adb_path}")
    except Exception as e:
        _print(FAIL, f"adb not found: {e}",
               fix="install Android platform-tools and put adb on PATH, "
                   "or set GRIDBOT_ADB_PATH=/full/path/to/adb")
        failures += 1
        adb_path = None

    # adb runs (returncode 0)
    if adb_path:
        try:
            result = subprocess.run(
                [adb_path, "version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                first_line = result.stdout.strip().split("\n")[0]
                _print(OK, f"adb runs: {first_line}")
            else:
                _print(FAIL, f"`adb version` exit code {result.returncode}",
                       fix="reinstall Android platform-tools — adb binary is broken")
                failures += 1
        except Exception as e:
            _print(FAIL, f"`adb version` raised: {e}")
            failures += 1

    # Devices in `device` state
    if adb_path:
        try:
            from gridbot._adb import list_devices
            devices = list_devices(adb_path)
            if devices:
                _print(OK, f"{len(devices)} device(s) connected: {', '.join(devices)}")
            else:
                _print(WARN, "no devices in 'device' state",
                       fix="connect a USB phone with debugging on, or start an emulator")
                warnings += 1
        except Exception as e:
            _print(FAIL, f"could not list devices: {e}")
            failures += 1

    print("-" * 60)
    if failures:
        print(f"summary: {failures} failure(s), {warnings} warning(s)")
        return 1
    if warnings:
        print(f"summary: clean (with {warnings} warning(s))")
        return 0
    print("summary: all good")
    return 0


# ---------- devices ----------

def cmd_devices(_args) -> int:
    from gridbot._adb import find_adb, list_devices

    try:
        adb_path = find_adb()
    except Exception as e:
        print(f"adb not found: {e}", file=sys.stderr)
        return 1

    try:
        devices = list_devices(adb_path)
    except Exception as e:
        print(f"could not list devices: {e}", file=sys.stderr)
        return 1

    if not devices:
        print("no devices connected (state != 'device')")
        return 1

    for d in devices:
        print(d)
    return 0


# ---------- screenshot ----------

def cmd_screenshot(args) -> int:
    from gridbot import AdbCapture

    cap = AdbCapture(serial=args.serial)
    out = args.path
    if out is None:
        out = Path.cwd() / "shot.png"
    path = cap.screenshot_to_file(out)
    print(f"saved: {path.resolve()}")
    return 0


# ---------- ocr ----------

def cmd_ocr(args) -> int:
    import cv2

    from gridbot import OcrEngine

    if not args.image.exists():
        print(f"image not found: {args.image}", file=sys.stderr)
        return 2

    img = cv2.imread(str(args.image))
    if img is None:
        print(f"could not read image (unsupported format?): {args.image}", file=sys.stderr)
        return 2

    ocr = OcrEngine.get(lang=args.lang, fast=args.fast)

    if args.region:
        x1, y1, x2, y2 = args.region
        results = ocr.read_region(img, x1, y1, x2, y2)
        print(f"OCR'd region ({x1},{y1})->({x2},{y2}): {len(results)} regions")
    else:
        results = ocr.read(img)
        print(f"OCR'd full image: {len(results)} regions")

    for r in results:
        print(f"  [{r.confidence:.2f}] {r.text!r}  @ {r.center}")

    if args.save_annotated:
        from gridbot import draw_results
        out = args.image.with_suffix(".annotated.png")
        cv2.imwrite(str(out), draw_results(img, results))
        print(f"annotated copy: {out.resolve()}")

    return 0


# ---------- watch ----------

def cmd_watch(args) -> int:
    """Loop: capture -> OCR -> print top-N results, until Ctrl-C."""
    from gridbot import AdbCapture, OcrEngine

    cap = AdbCapture(serial=args.serial)
    ocr = OcrEngine.get(lang=args.lang, fast=True)

    print(f"watching every {args.interval}s — Ctrl-C to stop")
    print("-" * 60)
    iteration = 0
    try:
        while True:
            iteration += 1
            t0 = time.time()
            img = cap.screenshot()
            results = ocr.read(img)
            elapsed = time.time() - t0
            top = sorted(results, key=lambda r: -r.confidence)[: args.top]

            print(f"\n[{iteration}] {len(results)} regions in {elapsed:.2f}s — top {len(top)}:")
            for r in top:
                print(f"  [{r.confidence:.2f}] {r.text!r}")
            time.sleep(max(0.0, args.interval - elapsed))
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0


# ---------- warmup ----------

def cmd_warmup(args) -> int:
    """Pre-download / load PaddleOCR models so the first real call is fast.

    First-time OcrEngine construction downloads ~30 MB of model weights
    from PaddleOCR's CDN. Run this once after install if you want to
    avoid the surprise pause on the first real OCR call (or to verify
    network access in restricted environments).
    """
    import numpy as np

    from gridbot import OcrEngine

    print(f"warming up PaddleOCR (lang={args.lang}, fast={args.fast})...")
    print("first run downloads ~30 MB of model weights — please be patient")
    t0 = time.time()
    engine = OcrEngine.get(lang=args.lang, fast=args.fast)

    # Run one OCR call on a tiny black image to flush any deferred init.
    dummy = np.zeros((64, 64, 3), dtype=np.uint8)
    engine.read(dummy)

    elapsed = time.time() - t0
    print(f"done in {elapsed:.1f}s")

    cache_dir = Path.home() / ".paddlex" / "official_models"
    if cache_dir.exists():
        models = sorted(p.name for p in cache_dir.iterdir() if p.is_dir())
        print(f"cached models ({len(models)}): {', '.join(models)}")
    return 0


# ---------- main ----------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gridbot",
        description="Black-box Android automation toolkit — CLI for the gridbot library.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("doctor", help="check Python, deps, adb, devices, OCR models")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("devices", help="list connected ADB devices")
    sp.set_defaults(func=cmd_devices)

    sp = sub.add_parser("screenshot", help="capture one screenshot to a file")
    sp.add_argument("path", nargs="?", type=Path, default=None,
                    help="output path (default: ./shot.png)")
    sp.add_argument("--serial", help="ADB device serial (default: auto-detect)")
    sp.set_defaults(func=cmd_screenshot)

    sp = sub.add_parser("ocr", help="run OCR on a local image file")
    sp.add_argument("image", type=Path, help="path to a PNG/JPEG")
    sp.add_argument("--lang", default="ch",
                    help="PaddleOCR language code (default: ch — handles "
                         "Simplified + Traditional Chinese + English; "
                         "use 'en' for pure English, 'ja', 'ko', etc.)")
    sp.add_argument("--fast", action="store_true",
                    help="use the mobile (fast, slightly less accurate) model")
    sp.add_argument("--region", nargs=4, type=int,
                    metavar=("X1", "Y1", "X2", "Y2"),
                    help="OCR only this rectangle of the image")
    sp.add_argument("--save-annotated", action="store_true",
                    help="save a copy with detection boxes drawn on")
    sp.set_defaults(func=cmd_ocr)

    sp = sub.add_parser("watch", help="loop: capture + OCR + print, until Ctrl-C")
    sp.add_argument("--serial", help="ADB device serial (default: auto-detect)")
    sp.add_argument("--lang", default="ch",
                    help="PaddleOCR language code (default: ch)")
    sp.add_argument("--interval", type=float, default=2.0,
                    help="seconds between captures (default: 2.0)")
    sp.add_argument("--top", type=int, default=10,
                    help="show this many highest-confidence detections per frame")
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser("warmup", help="pre-download PaddleOCR models")
    sp.add_argument("--lang", default="ch",
                    help="PaddleOCR language code (default: ch)")
    sp.add_argument("--fast", action="store_true",
                    help="warm up the mobile (fast) model instead of the server one")
    sp.set_defaults(func=cmd_warmup)

    return parser


def _quiet_loguru() -> None:
    """Reroute loguru to WARNING-and-above on stderr.

    CLI users running ``gridbot screenshot`` shouldn't see the same INFO
    chatter a script author sees. This must run *before* gridbot's own
    modules log anything (i.e. at the very start of main()).
    """
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="WARNING")
    except ImportError:
        pass  # loguru missing — doctor will surface it


def main(argv: Optional[List[str]] = None) -> int:
    _quiet_loguru()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
