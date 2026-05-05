"""gridbot — black-box Android automation toolkit.

Public API:

    from gridbot import AdbCapture, AdbInput, OcrEngine, OcrResult

For the ADB path discovery rules see :mod:`gridbot._adb`.
"""

from gridbot._adb import AdbNotFoundError, find_adb
from gridbot.capture import AdbCapture, AdbCaptureError
from gridbot.input import (
    KEY_BACK,
    KEY_ENTER,
    KEY_HOME,
    KEY_MENU,
    KEY_POWER,
    KEY_VOLUME_DOWN,
    KEY_VOLUME_UP,
    AdbInput,
    AdbInputError,
)
from gridbot.ocr import OcrEngine, OcrError, OcrResult, draw_results
from gridbot.navigator import (
    KeyeventAction,
    Navigator,
    NavigatorContext,
    NavigatorError,
    ScreensConfig,
    StateConfig,
    SwipeAction,
    TapCoordsAction,
    TapTextAction,
    Transition,
    WaitUntilAction,
    load_screens,
)
from gridbot.recorder import ScreenRecorder, ScreenRecorderError
from gridbot.state import StateDetector, StateRule

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Capture
    "AdbCapture",
    "AdbCaptureError",
    # Input
    "AdbInput",
    "AdbInputError",
    "KEY_BACK",
    "KEY_HOME",
    "KEY_MENU",
    "KEY_POWER",
    "KEY_ENTER",
    "KEY_VOLUME_UP",
    "KEY_VOLUME_DOWN",
    # OCR
    "OcrEngine",
    "OcrResult",
    "OcrError",
    "draw_results",
    # Recorder
    "ScreenRecorder",
    "ScreenRecorderError",
    # State detection
    "StateDetector",
    "StateRule",
    # Navigator
    "Navigator",
    "NavigatorContext",
    "NavigatorError",
    "load_screens",
    "ScreensConfig",
    "StateConfig",
    "Transition",
    "TapTextAction",
    "TapCoordsAction",
    "KeyeventAction",
    "SwipeAction",
    "WaitUntilAction",
    # ADB discovery
    "AdbNotFoundError",
    "find_adb",
]
