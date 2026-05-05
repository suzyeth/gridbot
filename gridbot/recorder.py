"""Record device video via ADB ``screenrecord``.

How it works:

1. Run ``screenrecord`` on the device, writing an mp4 to ``/sdcard/``.
2. Once recording finishes, ``adb pull`` the file back to the host.
3. Delete the on-device temp file.

Limits imposed by Android:

- Maximum **180 seconds** per recording (hard system limit).
- Maximum 1080p resolution.
- Default bitrate 4 Mbps (~30 MB / minute).

Two usage modes:

- :meth:`ScreenRecorder.record` — blocks for the full duration, then returns.
- :meth:`ScreenRecorder.start` / :meth:`stop` — async; ``start`` returns
  immediately, ``stop`` terminates and pulls the file. Useful when the
  recording length depends on what happens during the run.

Example:
    >>> from gridbot import ScreenRecorder
    >>> rec = ScreenRecorder()
    >>> path = rec.record(duration_seconds=10)
    >>> # ...
    >>> rec.start(max_duration_sec=60)
    >>> # do stuff
    >>> rec.stop("debug.mp4")
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from loguru import logger

from gridbot._adb import auto_detect_device, find_adb


class ScreenRecorderError(Exception):
    """Raised when an ADB ``screenrecord`` operation fails."""


# Hard system limit on Android.
MAX_DURATION_SEC = 180


class ScreenRecorder:
    """Record device video via ADB ``screenrecord``.

    Args:
        serial: ADB device serial. Auto-detected if omitted.
        adb_path: Path to ``adb``. Discovered if omitted — see :mod:`gridbot._adb`.
    """

    def __init__(
        self,
        serial: Optional[str] = None,
        *,
        adb_path: Optional[str] = None,
    ):
        self.adb_path: str = find_adb(adb_path)
        self.serial: str = serial or auto_detect_device(self.adb_path)
        # Async-mode state.
        self._proc: Optional[subprocess.Popen] = None
        self._device_path: Optional[str] = None
        logger.info(f"ScreenRecorder using device: {self.serial}")

    def _run(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
        cmd = [self.adb_path, "-s", self.serial, *args]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    # ----- Blocking mode -----

    def record(
        self,
        duration_seconds: int = 30,
        output_path: Optional[Union[str, Path]] = None,
        bitrate_mbps: int = 4,
    ) -> Path:
        """Record for ``duration_seconds`` and return the local mp4 path.

        Args:
            duration_seconds: Recording duration; must be <= 180.
            output_path: Where to save the mp4. If ``None``, writes to
                ``./recordings/rec_<timestamp>.mp4`` under the current
                working directory.
            bitrate_mbps: Encoder bitrate in Mbps (default 4).
        """
        if duration_seconds > MAX_DURATION_SEC:
            raise ScreenRecorderError(
                f"Single recording is capped at {MAX_DURATION_SEC} seconds. "
                "Split into multiple calls for longer captures."
            )

        device_tmp = f"/sdcard/_recorder_tmp_{int(time.time())}.mp4"
        output_path = self._resolve_output_path(output_path)
        bitrate_bps = bitrate_mbps * 1_000_000

        logger.info(f"recording for {duration_seconds}s @ {bitrate_mbps} Mbps...")
        start = time.time()
        result = self._run(
            "shell", "screenrecord",
            "--time-limit", str(duration_seconds),
            "--bit-rate", str(bitrate_bps),
            device_tmp,
            timeout=duration_seconds + 30,  # buffer for screenrecord cleanup
        )
        elapsed = time.time() - start
        logger.info(f"recording stopped (actual {elapsed:.1f}s)")

        if result.returncode != 0:
            self._run("shell", "rm", "-f", device_tmp)
            raise ScreenRecorderError(
                "screenrecord failed: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

        # Give the device a moment to finish flushing the mp4 to disk.
        time.sleep(0.5)

        logger.info(f"pulling to host: {output_path}")
        pull_result = self._run("pull", device_tmp, str(output_path), timeout=60)
        if pull_result.returncode != 0:
            raise ScreenRecorderError(f"adb pull failed: {pull_result.stderr}")

        self._run("shell", "rm", "-f", device_tmp)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise ScreenRecorderError(f"output file is empty or missing: {output_path}")

        size_mb = output_path.stat().st_size / 1024 / 1024
        logger.info(f"recording saved: {output_path} ({size_mb:.1f} MB)")
        return output_path

    # ----- Async mode -----

    def start(self, max_duration_sec: int = MAX_DURATION_SEC) -> None:
        """Start recording in the background. Returns immediately.

        Pair with :meth:`stop` to terminate and pull the file. The recording
        will end on its own at ``max_duration_sec`` (capped at 180) even if
        ``stop`` is never called.
        """
        if self._proc is not None:
            raise ScreenRecorderError("already recording — call stop() first")

        if max_duration_sec > MAX_DURATION_SEC:
            max_duration_sec = MAX_DURATION_SEC

        self._device_path = f"/sdcard/_rec_async_{int(time.time())}.mp4"
        self._proc = subprocess.Popen(
            [
                self.adb_path, "-s", self.serial,
                "shell", "screenrecord",
                "--time-limit", str(max_duration_sec),
                self._device_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.debug(
            f"ScreenRecorder started async: pid={self._proc.pid} "
            f"device_path={self._device_path}"
        )

    def stop(
        self,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Optional[Path]:
        """Stop the async recording and pull the mp4 to the host.

        Args:
            output_path: Where to save the mp4. Defaults to
                ``./recordings/rec_<timestamp>.mp4``.

        Returns:
            The local mp4 path on success, or ``None`` if the file could not
            be pulled (the recording was too short to flush, the pull failed,
            etc.). A ``None`` return is logged as a warning, not raised, since
            stopping a never-properly-started recording is a recoverable error.
        """
        if self._proc is None:
            raise ScreenRecorderError("not currently recording — call start() first")

        # Terminating the adb shell process causes screenrecord to flush and
        # close the mp4 cleanly in most cases.
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()

        # Wait for the device-side mp4 to finish writing.
        time.sleep(1.5)

        device_path = self._device_path
        self._proc = None
        self._device_path = None

        if not device_path:
            return None

        output_path = self._resolve_output_path(output_path)

        pull = self._run("pull", device_path, str(output_path), timeout=60)
        self._run("shell", "rm", "-f", device_path)

        if pull.returncode != 0:
            logger.warning(f"adb pull failed: {pull.stderr.strip()}")
            return None
        if not output_path.exists() or output_path.stat().st_size < 1024:
            logger.warning(f"output file too small or missing: {output_path}")
            return None

        size_mb = output_path.stat().st_size / 1024 / 1024
        logger.info(f"recording saved: {output_path} ({size_mb:.1f} MB)")
        return output_path

    # ----- Helpers -----

    @staticmethod
    def _resolve_output_path(output_path: Optional[Union[str, Path]]) -> Path:
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path.cwd() / "recordings" / f"rec_{ts}.mp4"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        return output_path
