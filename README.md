# gridbot

[![tests](https://github.com/suzyeth/gridbot/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/suzyeth/gridbot/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://github.com/suzyeth/gridbot/blob/main/pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![status](https://img.shields.io/badge/status-alpha-orange)](#status)

[中文 README](./README.zh-CN.md)

**Black-box Android automation toolkit.** Take ADB screenshots, send taps and
swipes, and drive UIs by OCR-matching the text already on screen — no app
internals, no instrumentation, no rooted device required.

```python
from gridbot import AdbCapture, AdbInput, OcrEngine

cap = AdbCapture()
inp = AdbInput()
ocr = OcrEngine.get(fast=True)

img = cap.screenshot()
btn = ocr.find_text(img, "Settings")
if btn:
    inp.tap(*btn.center)
```

That's the whole pitch.

## When to use this

- You want to script a **third-party Android app or game** you can't modify.
- A real OCR + ADB loop is a better fit than UIAutomator / Appium because the
  app uses a custom rendering engine (most games do) and standard view-hierarchy
  inspection returns nothing useful.
- You're fine with a "what a human sees" black-box approach: pixels in, taps out.

## When *not* to use this

- You control the app — use Espresso / UIAutomator / Appium for cleaner tests.
- You need millisecond-precision timing — OCR adds 50–500 ms per query.
- You need iOS — this is ADB-only.

## Install

> ⚠️ **Alpha — not yet on PyPI.** The public API may still change between
> 0.1.x releases. Once v0.2 lands on PyPI the canonical command will be
> `pip install gridbot[ocr]`. Until then, install directly from this repo.

**From a clone** (recommended if you want to run the bundled examples):

```bash
git clone https://github.com/suzyeth/gridbot
cd gridbot
pip install -e ".[ocr]"
```

**Without cloning**:

```bash
pip install "gridbot[ocr] @ git+https://github.com/suzyeth/gridbot.git"
```

The `[ocr]` extra pulls in PaddleOCR (~500 MB once model weights cache).
If you only need the capture / input / recorder layers, drop it:

```bash
pip install "gridbot @ git+https://github.com/suzyeth/gridbot.git"
```

> 🐍 **Python 3.13 note.** PaddlePaddle's wheel release cadence lags
> CPython's. If `pip install gridbot[ocr]` fails on 3.13, fall back to
> 3.12 — the no-OCR install (`pip install gridbot`) works on every Python
> 3.9+.

You also need the **`adb`** binary. Either:

- Install Android platform-tools and put `adb` on your `PATH`, **or**
- Set `GRIDBOT_ADB_PATH` to its full path:
  ```bash
  export GRIDBOT_ADB_PATH=/path/to/adb            # macOS / Linux
  set    GRIDBOT_ADB_PATH=D:\LDPlayer\adb.exe     # Windows cmd
  $env:GRIDBOT_ADB_PATH = "D:\LDPlayer\adb.exe"   # Windows PowerShell
  ```

Verify with `adb devices` — you should see one entry in `device` state.

Or use the bundled CLI to check everything in one command:

```bash
gridbot doctor
```

It checks Python version, every required dep, the optional OCR dep, the
PaddleOCR model cache, the adb binary, and connected devices — and prints
a concrete fix for each thing that's missing.

## First-run notes

A few things that aren't obvious until you trip on them:

- **OCR models download lazily on first use** (~30 MB from PaddleOCR's CDN
  to `~/.paddlex/official_models/`). Run `gridbot warmup` once after install
  to grab them eagerly, especially in restricted networks where the
  download may stall an unsuspecting first OCR call.
- **Linux + USB device** needs udev rules so non-root users can access the
  device. Follow Android's [setup guide](https://developer.android.com/studio/run/device.html#setting-up)
  and write the rules into `/etc/udev/rules.d/51-android.rules`. Emulators
  don't need this.
- **Multiple devices connected?** `AdbCapture` / `AdbInput` /
  `ScreenRecorder` all auto-pick the first device in `device` state. Pass
  `serial="..."` or `--serial ...` to target a specific one.
- **OCR language** defaults to `"ch"` (Simplified + Traditional Chinese
  *and* English — PaddleOCR's catch-all model). For other languages pass
  `lang="en"`, `"ja"`, `"ko"`, etc. to `OcrEngine.get`, or `--lang en` to
  the `gridbot ocr` / `gridbot watch` commands.

## CLI quick reference

After ``pip install``, a ``gridbot`` command is on your PATH:

```bash
gridbot doctor                                # preflight check (no device needed)
gridbot devices                               # list connected devices
gridbot screenshot ./shot.png                 # capture once
gridbot ocr ./shot.png --fast                 # OCR a local image (default lang=ch)
gridbot ocr ./shot.png --lang en              # English-only OCR
gridbot ocr ./shot.png --save-annotated       # ...with detection boxes drawn
gridbot watch --interval 2                    # live capture + OCR loop
gridbot warmup                                # pre-download OCR models
```

Useful for verifying your install and exploring a device's screens before
writing any Python.

## Quick start

```python
from gridbot import AdbCapture, AdbInput, OcrEngine

cap = AdbCapture()             # auto-detects the first connected device
inp = AdbInput()
ocr = OcrEngine.get(fast=True) # mobile model — faster, slightly less accurate

# 1) Capture
img = cap.screenshot()                          # BGR ndarray
cap.screenshot_to_file("debug.png")             # also saves to disk

# 2) Read all the text on screen
results = ocr.read(img)
for r in results:
    print(f"{r.text!r}  conf={r.confidence:.2f}  centre={r.center}")

# 3) Find a specific button and tap it
btn = ocr.find_text(img, "Settings", results=results)
if btn:
    inp.tap(*btn.center)

# 4) Or scope the OCR to a region for speed
header = ocr.read_region(img, 0, 0, img.shape[1], 200)
```

A runnable end-to-end version lives in [`examples/01_hello_world/`](./examples/01_hello_world/).

## Public API

| Symbol | Purpose |
|---|---|
| `AdbCapture(serial=None, *, adb_path=None)` | Take screenshots over ADB. |
| `AdbCapture.screenshot()` | Return one frame as a BGR ndarray. |
| `AdbCapture.screenshot_to_file(path=None)` | Same, but write a PNG to disk. |
| `AdbInput(serial=None, *, adb_path=None)` | Send input events. |
| `AdbInput.tap(x, y)` | Single tap. |
| `AdbInput.swipe(x1, y1, x2, y2, duration_ms=300)` | Drag / fling. |
| `AdbInput.long_press(x, y, duration_ms=1000)` | Long press. |
| `AdbInput.keyevent(code)` / `back()` / `home()` | Hardware keys. |
| `AdbInput.text(content)` | Type ASCII (no CJK / emoji). |
| `OcrEngine.get(lang="ch", fast=False)` | Cached PaddleOCR engine. |
| `OcrEngine.read(image)` | Full-image OCR. |
| `OcrEngine.read_region(image, x1, y1, x2, y2)` | Cropped OCR (5–10× faster). |
| `OcrEngine.find_text(image, keyword, *, results=None, ...)` | First match. |
| `OcrEngine.find_all_texts(...)` | All matches. |
| `OcrResult.text / .confidence / .center / .rect` | Detection record. |
| `draw_results(image, results)` | Annotate detections for debugging. |

## Project layout

```
gridbot/
├── gridbot/
│   ├── _adb.py          # ADB binary discovery + device listing
│   ├── capture.py       # AdbCapture
│   ├── cli.py           # `gridbot` CLI (doctor / devices / screenshot / ocr / watch)
│   ├── input.py         # AdbInput, KEY_* constants
│   ├── navigator.py     # Navigator + screens.yaml schema (BFS state-graph driver)
│   ├── ocr.py           # OcrEngine, OcrResult, draw_results
│   ├── recorder.py      # ScreenRecorder (blocking + async modes)
│   └── state.py         # StateRule, StateDetector
├── examples/
│   ├── 00_no_device/    # OCR a bundled image — verify install in 5 seconds
│   ├── 01_hello_world/  # capture → OCR → annotate, on a real device
│   ├── 02_state_navigator/  # screens.yaml + StateDetector + Navigator.goto
│   └── 03_screen_recording/ # ScreenRecorder blocking + async demo
├── tests/
├── .github/workflows/test.yml  # pytest + ruff matrix
├── pyproject.toml
└── LICENSE              # MIT
```

## Status

**Alpha (0.1.x).** The capture / input / OCR primitives are stable and
battle-tested in a real downstream project. State / navigator / recorder are
newer and may evolve. Public API is not yet locked — pin the version if that
matters to you.

## Credits

- **PaddleOCR** ([Apache-2.0](https://github.com/PaddlePaddle/PaddleOCR)) does
  all of the heavy lifting on the OCR side.
- Inspired by black-box automation tools like
  [BetterGI](https://github.com/babalae/better-genshin-impact) and
  [March7thAssistant](https://github.com/moesnow/March7thAssistant).

## License

MIT — see [LICENSE](./LICENSE).
