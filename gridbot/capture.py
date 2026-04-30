"""Take screenshots from any ADB-connected Android device or emulator.

The output is a BGR ``numpy`` array (the format OpenCV, PaddleOCR, and template
matching all expect), so the result drops straight into the rest of the
pipeline without conversion.

Example:
    >>> from gridbot import AdbCapture
    >>> cap = AdbCapture()
    >>> img = cap.screenshot()                  # BGR ndarray, shape (H, W, 3)
    >>> path = cap.screenshot_to_file("shot.png")
"""

from __future__ import annotations

import io
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np
from loguru import logger
from PIL import Image

from gridbot._adb import auto_detect_device, find_adb


class AdbCaptureError(Exception):
    """Raised when an ADB screenshot operation fails."""


class AdbCapture:
    """Capture screenshots over ADB.

    Args:
        serial: ADB device serial (e.g. ``"127.0.0.1:5555"`` for an emulator,
            or a USB device serial). If omitted, the first device in ``device``
            state is selected automatically.
        adb_path: Path to the ``adb`` binary. If omitted, it is discovered via
            ``$GRIDBOT_ADB_PATH``, the system ``PATH``, or a list of common
            install locations. See :mod:`gridbot._adb` for the full order.
    """

    def __init__(
        self,
        serial: Optional[str] = None,
        *,
        adb_path: Optional[str] = None,
    ):
        self.adb_path: str = find_adb(adb_path)
        self.serial: str = serial or auto_detect_device(self.adb_path)
        logger.info(f"AdbCapture using device: {self.serial}")

    def screenshot(self) -> np.ndarray:
        """Capture one frame as a BGR ``numpy`` array of shape ``(H, W, 3)``.

        Uses ``adb exec-out screencap -p`` which is binary-safe (avoids the
        Windows CRLF translation that corrupts PNG bytes on plain ``adb shell``).
        """
        result = subprocess.run(
            [self.adb_path, "-s", self.serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            raise AdbCaptureError(f"`screencap` failed: {err}")

        if not result.stdout:
            raise AdbCaptureError(
                "`screencap` returned no data — the device may not be ready yet."
            )

        try:
            img_pil = Image.open(io.BytesIO(result.stdout))
            img_rgb = np.array(img_pil)
        except Exception as e:
            raise AdbCaptureError(f"Failed to decode PNG bytes: {e}") from e

        if img_rgb.ndim == 3 and img_rgb.shape[2] == 3:
            return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        if img_rgb.ndim == 3 and img_rgb.shape[2] == 4:
            return cv2.cvtColor(img_rgb, cv2.COLOR_RGBA2BGR)
        return img_rgb  # Grayscale or other unusual mode — return as-is.

    def screenshot_to_file(
        self,
        path: Optional[Union[str, Path]] = None,
    ) -> Path:
        """Capture and write to disk.

        Args:
            path: Output path. If ``None``, writes to
                ``./screenshots/shot_<timestamp>.png`` under the current
                working directory.

        Returns:
            The path the file was written to.
        """
        img = self.screenshot()

        if path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = Path.cwd() / "screenshots" / f"shot_{ts}.png"

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        ok = cv2.imwrite(str(path), img)
        if not ok:
            raise AdbCaptureError(f"cv2.imwrite failed for: {path}")

        logger.info(f"Screenshot saved: {path}")
        return path
