"""Internal helpers for locating the ``adb`` binary and listing devices.

Resolution order for the ADB path:

1. Explicit ``adb_path`` argument passed by the caller.
2. ``GRIDBOT_ADB_PATH`` environment variable.
3. ``adb`` on ``PATH`` (via :func:`shutil.which`).
4. A short list of common emulator install locations (LDPlayer, NoxPlayer,
   MEmu, BlueStacks, Android SDK) on Windows / macOS / Linux.

A clear error is raised if none of those work, telling the caller exactly
which environment variable to set.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional


class AdbNotFoundError(RuntimeError):
    """Raised when the ``adb`` binary cannot be located."""


_ENV_VAR = "GRIDBOT_ADB_PATH"

# Best-effort fallbacks. Order matters: most specific emulator paths first.
_COMMON_PATHS: List[str] = [
    # Windows — emulators
    r"D:\LDPlayer\adb.exe",
    r"C:\LDPlayer\adb.exe",
    r"D:\LDPlayer9\adb.exe",
    r"C:\LDPlayer9\adb.exe",
    r"C:\Program Files\Nox\bin\nox_adb.exe",
    r"C:\Program Files (x86)\Nox\bin\nox_adb.exe",
    r"C:\Program Files\Microvirt\MEmu\adb.exe",
    r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
    # Windows — Android SDK
    os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
    # macOS / Linux — Android SDK
    os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
    os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
    "/usr/local/bin/adb",
    "/opt/homebrew/bin/adb",
]


def find_adb(adb_path: Optional[str] = None) -> str:
    """Return a usable path to the ``adb`` executable.

    Args:
        adb_path: If provided, this exact path is used (no further lookup).

    Raises:
        AdbNotFoundError: If no working ``adb`` binary can be located.
    """
    if adb_path:
        if not Path(adb_path).exists():
            raise AdbNotFoundError(f"adb_path does not exist: {adb_path}")
        return adb_path

    env_path = os.environ.get(_ENV_VAR)
    if env_path:
        if not Path(env_path).exists():
            raise AdbNotFoundError(
                f"${_ENV_VAR} points to a missing file: {env_path}"
            )
        return env_path

    on_path = shutil.which("adb")
    if on_path:
        return on_path

    for candidate in _COMMON_PATHS:
        if candidate and Path(candidate).exists():
            return candidate

    raise AdbNotFoundError(
        "Could not locate the 'adb' binary. Either:\n"
        "  - install Android platform-tools and put adb on your PATH, or\n"
        f"  - set the {_ENV_VAR} environment variable to its full path, or\n"
        "  - pass adb_path=... when constructing AdbCapture / AdbInput."
    )


def list_devices(adb_path: str) -> List[str]:
    """Return the serials of devices in ``device`` state (excluding offline / unauthorized)."""
    result = subprocess.run(
        [adb_path, "devices"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"`adb devices` failed: {result.stderr.strip()}")

    # Skip the "List of devices attached" header.
    lines = result.stdout.strip().split("\n")[1:]
    return [
        line.split("\t")[0]
        for line in lines
        if "\tdevice" in line
    ]


def auto_detect_device(adb_path: str) -> str:
    """Pick the first connected device. Raises if none is available."""
    from loguru import logger

    devices = list_devices(adb_path)
    if not devices:
        raise RuntimeError(
            "No devices in 'device' state. Connect a phone via USB (with "
            "USB debugging enabled) or start an Android emulator first."
        )
    if len(devices) > 1:
        logger.warning(f"Multiple devices found {devices}; using the first: {devices[0]}")
    return devices[0]
