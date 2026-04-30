"""Send input events (taps, swipes, keys, text) to an ADB-connected device.

Coordinate system: top-left is ``(0, 0)``, X grows right, Y grows down. For a
1080x1920 portrait device, the screen centre is ``(540, 960)``.

Example:
    >>> from gridbot import AdbInput
    >>> inp = AdbInput()
    >>> inp.tap(540, 960)
    >>> inp.swipe(540, 1500, 540, 500, duration_ms=400)
    >>> inp.back()
"""

from __future__ import annotations

import subprocess
from typing import Optional

from loguru import logger

from gridbot._adb import auto_detect_device, find_adb


class AdbInputError(Exception):
    """Raised when an ADB input command fails."""


# Common Android KeyEvent codes.
# Full list: https://developer.android.com/reference/android/view/KeyEvent
KEY_BACK = 4
KEY_HOME = 3
KEY_MENU = 82
KEY_POWER = 26
KEY_VOLUME_UP = 24
KEY_VOLUME_DOWN = 25
KEY_ENTER = 66


class AdbInput:
    """Send input events via ``adb shell input``.

    Args:
        serial: ADB device serial. Auto-detected if omitted.
        adb_path: Path to the ``adb`` binary. Discovered if omitted — see
            :mod:`gridbot._adb` for the lookup order.
    """

    def __init__(
        self,
        serial: Optional[str] = None,
        *,
        adb_path: Optional[str] = None,
    ):
        self.adb_path: str = find_adb(adb_path)
        self.serial: str = serial or auto_detect_device(self.adb_path)
        logger.info(f"AdbInput using device: {self.serial}")

    def _shell(self, *args: str) -> None:
        """Run ``adb -s <serial> shell <args...>``."""
        cmd = [self.adb_path, "-s", self.serial, "shell", *args]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise AdbInputError(
                f"`adb shell {' '.join(args)}` failed: {result.stderr.strip()}"
            )

    # ----- Tap / swipe / long-press -----

    def tap(self, x: int, y: int) -> None:
        """Tap once at ``(x, y)``."""
        logger.debug(f"tap({x}, {y})")
        self._shell("input", "tap", str(x), str(y))

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
    ) -> None:
        """Swipe from ``(x1, y1)`` to ``(x2, y2)`` over ``duration_ms`` milliseconds.

        Rules of thumb:

        - ``< 100ms``: fling (inertial fast scroll)
        - ``200–500ms``: standard swipe
        - ``> 1000ms``: long-press drag
        """
        logger.debug(f"swipe({x1},{y1}) -> ({x2},{y2}) {duration_ms}ms")
        self._shell(
            "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration_ms),
        )

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """Long-press at ``(x, y)`` (an in-place swipe)."""
        self.swipe(x, y, x, y, duration_ms)

    # ----- Keys -----

    def keyevent(self, key_code: int) -> None:
        """Send an Android ``KeyEvent``. Common codes are exposed as ``KEY_*`` constants."""
        logger.debug(f"keyevent({key_code})")
        self._shell("input", "keyevent", str(key_code))

    def back(self) -> None:
        """Press the system Back key."""
        self.keyevent(KEY_BACK)

    def home(self) -> None:
        """Press the system Home key."""
        self.keyevent(KEY_HOME)

    # ----- Text -----

    def text(self, content: str) -> None:
        """Type ASCII text into the focused field.

        Note:
            ``adb shell input text`` only handles ASCII. For non-ASCII text
            (CJK, emoji, etc.) you need an IME or clipboard-based approach,
            which this minimal toolkit does not yet provide.
        """
        if not content:
            return
        # `input text` treats space as a separator; %s is the documented escape.
        escaped = (
            content
            .replace(" ", "%s")
            .replace("'", r"\'")
            .replace('"', r'\"')
        )
        logger.debug(f"text({content!r})")
        self._shell("input", "text", escaped)
