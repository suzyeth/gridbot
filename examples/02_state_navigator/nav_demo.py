"""Walk through every layer of gridbot wired together: state + navigator.

What this script does:

1. Loads ``screens.yaml`` and validates it against the rule set in ``rules.py``.
2. Builds a :class:`gridbot.StateDetector` and :class:`gridbot.Navigator`.
3. Prints the loaded state graph.
4. Calls :meth:`Navigator.find_path` (a *pure* BFS — no device interaction)
   to demonstrate path-finding for several source/target pairs.
5. If a device is connected and the ``--live`` flag is passed, tries to
   :meth:`detect_current` and then :meth:`goto` ``"about"`` end-to-end.

Run:
    python examples/02_state_navigator/nav_demo.py
    python examples/02_state_navigator/nav_demo.py --live   # actually drive the device
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

from gridbot import (
    AdbCapture,
    AdbInput,
    Navigator,
    NavigatorContext,
    OcrEngine,
    StateDetector,
    load_screens,
)

HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="gridbot state + navigator demo")
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Actually drive the connected device. Without this flag the demo "
            "only validates the YAML and exercises the BFS path-finder."
        ),
    )
    parser.add_argument(
        "--target",
        default="about",
        help="State name to navigate to when --live is on (default: about).",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("gridbot state + navigator demo")
    logger.info("=" * 60)

    # 1. Load YAML.
    yaml_path = HERE / "screens.yaml"
    config = load_screens(yaml_path)
    logger.info(f"loaded {len(config.states)} states from {yaml_path.name}")
    for name, state in config.states.items():
        targets = ", ".join(t.to for t in state.transitions) or "<terminal>"
        logger.info(f"  {name:10s} -> {targets}")

    # 2. Bring in the StateRule list (kept in a sibling file so users can
    #    edit rules without touching this script).
    sys.path.insert(0, str(HERE))
    from rules import RULES  # noqa: E402

    logger.info(f"loaded {len(RULES)} state rules from rules.py")

    # 3. Pure BFS demo — no device needed.
    logger.info("")
    logger.info("--- find_path demo (no device interaction) ---")

    # Build a Navigator without any real ADB calls. We use a deliberately
    # minimal stand-in for AdbCapture/AdbInput since BFS doesn't touch them.
    # NOTE: this inline mock is ONLY safe because find_path is pure. For
    # detect_current / goto we instantiate the real classes below.
    if not args.live:
        from unittest.mock import MagicMock

        fake_detector = MagicMock()
        fake_detector.rules = RULES
        ctx = NavigatorContext(
            capture=MagicMock(),
            input=MagicMock(),
            state=fake_detector,
        )
        nav = Navigator(config, ctx)

        for src, dst in [("home", "about"), ("about", "home"), ("home", "home")]:
            path = nav.find_path(src, dst)
            if path is None:
                logger.info(f"  {src!r} -> {dst!r}: no path")
            elif not path:
                logger.info(f"  {src!r} -> {dst!r}: already there (empty path)")
            else:
                hops = " -> ".join([src] + [step[0] for step in path])
                logger.info(f"  {src!r} -> {dst!r} ({len(path)} step(s)): {hops}")

        logger.info("")
        logger.info("dry-run complete. pass --live to drive a real device.")
        return 0

    # 4. Live mode — needs a device.
    logger.info("")
    logger.info("--- live mode: connecting to device ---")
    cap = AdbCapture()
    inp = AdbInput()

    # `fast=True` keeps state detection responsive (~1-2s per call).
    detector = StateDetector(RULES, fast_ocr=True)

    # Optional accurate-OCR fallback for tap_text actions. Loading the server
    # model takes a few seconds on first use; remove this line if you don't
    # need the slow fallback.
    ocr_accurate = OcrEngine.get(fast=False)

    ctx = NavigatorContext(
        capture=cap,
        input=inp,
        state=detector,
        ocr_accurate=ocr_accurate,
    )
    nav = Navigator(config, ctx)

    logger.info("detecting current state...")
    current = nav.detect_current()
    logger.info(f"  current state: {current}")

    if current == StateDetector.UNKNOWN:
        logger.warning(
            "Detector couldn't classify the current screen — "
            "either the device is on a screen no rule covers, or the rules "
            "in rules.py need tuning for your device's language/version."
        )
        return 1

    logger.info(f"navigating to {args.target!r}...")
    ok = nav.goto(args.target, max_steps=10)
    logger.info(f"goto({args.target!r}) -> {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
