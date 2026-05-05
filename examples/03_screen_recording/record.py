"""Record device video with :class:`gridbot.ScreenRecorder`.

Two ways to use the recorder are demonstrated:

- **Blocking** (default) — ``rec.record(duration_seconds=N)`` returns after N
  seconds with the local mp4 path.
- **Async** (``--async``) — ``rec.start()`` returns immediately, then
  ``rec.stop()`` terminates the recording and pulls the file. Useful when
  the recording length is decided by what happens at runtime (e.g. wrap a
  whole automation routine and stop only when it finishes).

Run:
    python examples/03_screen_recording/record.py
    python examples/03_screen_recording/record.py --duration 10
    python examples/03_screen_recording/record.py --async
"""

from __future__ import annotations

import argparse
import sys
import time

from loguru import logger

from gridbot import ScreenRecorder


def run_blocking(duration: int) -> int:
    rec = ScreenRecorder()
    logger.info(f"recording for {duration} seconds (blocking mode)...")
    logger.info("interact with the device however you want — it'll all be captured")

    path = rec.record(duration_seconds=duration)

    size_mb = path.stat().st_size / 1024 / 1024
    logger.info(f"saved: {path.resolve()} ({size_mb:.1f} MB)")
    return 0


def run_async(duration: int) -> int:
    rec = ScreenRecorder()
    logger.info(f"recording asynchronously for ~{duration} seconds...")

    rec.start(max_duration_sec=duration + 10)  # cap above duration as a safety net

    # In a real script this is where you'd run whatever you want recorded.
    # Below is just a visible countdown so you can interact with the device
    # while the recorder runs in the background.
    for remaining in range(duration, 0, -1):
        logger.info(f"  recording... ({remaining}s left)")
        time.sleep(1)

    logger.info("stopping...")
    path = rec.stop()
    if path is None:
        logger.error("recorder.stop() returned None — recording was too short or failed")
        return 1

    size_mb = path.stat().st_size / 1024 / 1024
    logger.info(f"saved: {path.resolve()} ({size_mb:.1f} MB)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="gridbot screen-recording demo")
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Recording length in seconds (default: 30, max: 180).",
    )
    parser.add_argument(
        "--async",
        dest="async_mode",
        action="store_true",
        help="Use start()/stop() async mode instead of blocking record().",
    )
    args = parser.parse_args()

    if args.duration < 1 or args.duration > 180:
        logger.error("--duration must be between 1 and 180 seconds")
        return 2

    logger.info("=" * 60)
    logger.info("gridbot screen-recording demo")
    logger.info("=" * 60)

    if args.async_mode:
        return run_async(args.duration)
    return run_blocking(args.duration)


if __name__ == "__main__":
    sys.exit(main())
