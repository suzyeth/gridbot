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

```bash
pip install gridbot[ocr]
```

The `[ocr]` extra pulls in PaddleOCR. PaddleOCR is heavy (~500 MB with model
weights); skip it if you only need the capture/input layer:

```bash
pip install gridbot
```

You also need the **`adb`** binary. Either:

- Install Android platform-tools and put `adb` on your `PATH`, **or**
- Set `GRIDBOT_ADB_PATH` to its full path:
  ```bash
  export GRIDBOT_ADB_PATH=/path/to/adb            # macOS / Linux
  set    GRIDBOT_ADB_PATH=D:\LDPlayer\adb.exe     # Windows cmd
  $env:GRIDBOT_ADB_PATH = "D:\LDPlayer\adb.exe"   # Windows PowerShell
  ```

Verify with `adb devices` — you should see one entry in `device` state.

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
│   ├── input.py         # AdbInput, KEY_* constants
│   └── ocr.py           # OcrEngine, OcrResult, draw_results
├── examples/
│   └── 01_hello_world/  # capture → OCR → annotate
├── tests/
├── pyproject.toml
└── LICENSE              # MIT
```

## Status

**Alpha (0.1.x).** The capture / input / OCR primitives are stable and
battle-tested in a real downstream project, but the public API may still
change. State machines, screen graphs, and a higher-level task runner are
deliberately out of scope for this minimal release — they belong in the layer
above gridbot, where game-specific knowledge lives.

## Credits

- **PaddleOCR** ([Apache-2.0](https://github.com/PaddlePaddle/PaddleOCR)) does
  all of the heavy lifting on the OCR side.
- Inspired by black-box automation tools like
  [BetterGI](https://github.com/babalae/better-genshin-impact) and
  [March7thAssistant](https://github.com/moesnow/March7thAssistant).

## License

MIT — see [LICENSE](./LICENSE).
