"""Smoke tests that don't need a real device or PaddleOCR install."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow running tests without `pip install -e .`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_public_api_imports():
    """Everything in __all__ should be importable from the top-level package."""
    import gridbot

    for name in gridbot.__all__:
        assert hasattr(gridbot, name), f"gridbot.{name} missing"

    # Spot-check key symbols and their kinds.
    assert callable(gridbot.AdbCapture)
    assert callable(gridbot.AdbInput)
    assert callable(gridbot.OcrEngine.get)
    assert isinstance(gridbot.KEY_BACK, int)
    assert isinstance(gridbot.__version__, str)


def test_find_adb_explicit_path_must_exist(tmp_path):
    """An explicit adb_path that doesn't exist must raise."""
    from gridbot import AdbNotFoundError, find_adb

    missing = tmp_path / "no-such-adb"
    with pytest.raises(AdbNotFoundError):
        find_adb(str(missing))


def test_find_adb_env_var_must_exist(monkeypatch, tmp_path):
    """A bad GRIDBOT_ADB_PATH must raise (rather than silently fall through)."""
    from gridbot import AdbNotFoundError, find_adb

    monkeypatch.setenv("GRIDBOT_ADB_PATH", str(tmp_path / "no-such-adb"))
    with pytest.raises(AdbNotFoundError):
        find_adb()


def test_find_adb_explicit_path_wins(tmp_path, monkeypatch):
    """An explicit adb_path should win over PATH and the env var."""
    from gridbot import find_adb

    fake_adb = tmp_path / "fake-adb"
    fake_adb.write_text("")
    # Set a bogus env var to confirm it's ignored when adb_path is explicit.
    monkeypatch.setenv("GRIDBOT_ADB_PATH", str(tmp_path / "no-such-adb"))

    assert find_adb(str(fake_adb)) == str(fake_adb)


def test_ocr_result_geometry():
    """OcrResult.center and .rect should be derived from the bbox correctly."""
    from gridbot import OcrResult

    r = OcrResult(
        text="hello",
        confidence=0.95,
        bbox=((10, 20), (110, 20), (110, 60), (10, 60)),
    )
    assert r.center == (60, 40)
    assert r.rect == (10, 20, 110, 60)
