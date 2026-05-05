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


def test_state_rule_match_keywords_all():
    """keywords_all requires every entry; missing one means no match."""
    from gridbot import OcrResult, StateRule

    rule = StateRule(name="x", keywords_all=["Settings", "Inventory"])
    results = [
        OcrResult("Settings", 0.99, ((0, 0), (1, 0), (1, 1), (0, 1))),
        OcrResult("Inventory", 0.99, ((0, 0), (1, 0), (1, 1), (0, 1))),
    ]
    assert rule.match(results) is True

    # Drop one keyword -> no match
    assert rule.match(results[:1]) is False


def test_state_rule_forbidden():
    """A forbidden hit kills the rule even if everything else matches."""
    from gridbot import OcrResult, StateRule

    rule = StateRule(name="x", keywords_any=["Login"], forbidden=["Settings"])
    hit_only = [OcrResult("Login", 0.99, ((0, 0), (1, 0), (1, 1), (0, 1)))]
    with_forbidden = hit_only + [OcrResult("Settings", 0.99, ((0, 0), (1, 0), (1, 1), (0, 1)))]
    assert rule.match(hit_only) is True
    assert rule.match(with_forbidden) is False


def test_state_rule_regex_any():
    """regex_any matches against individual OCR text strings."""
    from gridbot import OcrResult, StateRule

    rule = StateRule(name="x", regex_any=[r"Stage \d+"])
    results = [OcrResult("Stage 17", 0.95, ((0, 0), (1, 0), (1, 1), (0, 1)))]
    assert rule.match(results) is True

    no_match = [OcrResult("hello", 0.95, ((0, 0), (1, 0), (1, 1), (0, 1)))]
    assert rule.match(no_match) is False


def test_load_screens_missing_file_raises(tmp_path):
    """A missing screens.yaml path should produce a clear NavigatorError."""
    from gridbot import NavigatorError, load_screens

    with pytest.raises(NavigatorError):
        load_screens(tmp_path / "nope.yaml")


def test_screens_config_validates_action_types(tmp_path):
    """ScreensConfig should accept all five action types via discriminator."""
    from gridbot import load_screens

    yaml_path = tmp_path / "screens.yaml"
    yaml_path.write_text(
        """
states:
  a:
    transitions:
      - to: b
        action: { type: tap_text, text: "Go" }
  b:
    transitions:
      - to: a
        action: { type: tap_coords, x: 10, y: 20 }
      - to: c
        action: { type: keyevent, key: "BACK" }
      - to: d
        action: { type: swipe, x1: 0, y1: 0, x2: 100, y2: 100 }
      - to: e
        action: { type: wait_until }
  c: {}
  d: {}
  e: {}
""",
        encoding="utf-8",
    )

    config = load_screens(yaml_path)
    assert set(config.states.keys()) == {"a", "b", "c", "d", "e"}
    assert config.states["b"].transitions[0].action.type == "tap_coords"
    assert config.states["b"].transitions[2].action.duration_ms == 300  # swipe default
    assert config.states["b"].transitions[3].action.type == "wait_until"


def test_navigator_rejects_unknown_state_in_yaml(tmp_path):
    """Building a Navigator should fail if YAML names a state the detector doesn't know."""
    from unittest.mock import MagicMock

    from gridbot import (
        Navigator,
        NavigatorContext,
        NavigatorError,
        StateRule,
        load_screens,
    )

    yaml_path = tmp_path / "screens.yaml"
    yaml_path.write_text(
        """
states:
  not_in_detector:
    transitions: []
""",
        encoding="utf-8",
    )
    config = load_screens(yaml_path)

    # Build a fake StateDetector with one rule that doesn't include the YAML's state.
    fake_detector = MagicMock()
    fake_detector.rules = [StateRule(name="some_other_state")]

    ctx = NavigatorContext(
        capture=MagicMock(),
        input=MagicMock(),
        state=fake_detector,
    )

    with pytest.raises(NavigatorError, match="unknown state"):
        Navigator(config, ctx)


def test_navigator_find_path_bfs(tmp_path):
    """BFS should find shortest paths and return None for unreachable targets."""
    from unittest.mock import MagicMock

    from gridbot import Navigator, NavigatorContext, StateRule, load_screens

    yaml_path = tmp_path / "screens.yaml"
    yaml_path.write_text(
        """
states:
  a:
    transitions:
      - to: b
        action: { type: tap_coords, x: 0, y: 0 }
      - to: c
        action: { type: tap_coords, x: 0, y: 0 }
  b:
    transitions:
      - to: d
        action: { type: tap_coords, x: 0, y: 0 }
  c:
    transitions: []
  d:
    transitions: []
  island:
    transitions: []
""",
        encoding="utf-8",
    )
    config = load_screens(yaml_path)

    fake_detector = MagicMock()
    fake_detector.rules = [StateRule(name=n) for n in ["a", "b", "c", "d", "island"]]
    ctx = NavigatorContext(
        capture=MagicMock(),
        input=MagicMock(),
        state=fake_detector,
    )
    nav = Navigator(config, ctx)

    # Same source/dest -> empty path.
    assert nav.find_path("a", "a") == []

    # Direct neighbour -> 1-step path.
    path_ab = nav.find_path("a", "b")
    assert path_ab is not None
    assert [step[0] for step in path_ab] == ["b"]

    # Two hops -> a -> b -> d.
    path_ad = nav.find_path("a", "d")
    assert path_ad is not None
    assert [step[0] for step in path_ad] == ["b", "d"]

    # Unreachable.
    assert nav.find_path("a", "island") is None
