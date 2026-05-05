"""StateRule list mapping the Android Settings-app screens to OCR signatures.

Each rule needs at least one stable bit of text that appears on the target
screen and (ideally) doesn't appear anywhere else in the app. For real apps,
the recipe is:

1. Capture screenshots of every screen with :class:`gridbot.AdbCapture`.
2. Run them through :class:`gridbot.OcrEngine` and look at what comes back.
3. Pick fragments that uniquely identify each screen.
4. Order the rules from most-specific to most-generic — :class:`StateDetector`
   returns the first match.
"""

from __future__ import annotations

from gridbot import StateRule

RULES = [
    # The "About" page contains things like "Build number", "Android version",
    # "Model" — those are stable across most Android builds in English.
    StateRule(
        name="about",
        description="Android Settings -> About phone (or About emulated device).",
        keywords_any=["Build number", "Android version", "Kernel version"],
    ),

    # Top-level Settings has "Network & internet" and "About" as siblings.
    # Listing both keywords as "all" makes the rule more specific so it
    # doesn't fire on the About sub-page (which has only "About" in the
    # action bar, plus version info that the rule above already handles).
    StateRule(
        name="settings",
        description="Top-level Settings app.",
        keywords_any=["Network & internet", "Connected devices", "Apps & notifications"],
        forbidden=["Build number"],   # exclude the About sub-page
    ),

    # Home screen / launcher. The literal "Settings" icon label is the
    # most reliable signal across launchers, but Pixel-style launchers also
    # show the search bar text "Search apps" or the date / weather widget.
    StateRule(
        name="home",
        description="Android home screen / launcher.",
        keywords_any=["Settings", "Phone", "Camera", "Chrome"],
        forbidden=["Network & internet", "Build number"],
    ),
]
