# 01 — Hello, world

The smallest possible end-to-end demo: capture a screen, OCR it, draw the
detections, and look for a sample keyword.

## What you need

1. **Python 3.9+**
2. **ADB on `PATH`** — verify with `adb version`. If your `adb` lives somewhere
   non-standard (e.g. bundled with LDPlayer at `D:\LDPlayer\adb.exe`), either
   add that directory to `PATH` or set the `GRIDBOT_ADB_PATH` environment
   variable to the full path.
3. **A device** — one of:
   - An Android phone connected via USB with **USB debugging** enabled.
   - An emulator (LDPlayer, NoxPlayer, MEmu, BlueStacks, Android Studio) with
     ADB exposed on the standard local port.

   Verify with `adb devices` — you should see one entry in `device` state
   (not `offline` or `unauthorized`).

4. **gridbot installed with OCR extras**:

   ```bash
   pip install gridbot[ocr]
   ```

   This pulls in PaddleOCR and PaddlePaddle. The very first OCR call will
   download model weights (~30 MB) into your user cache directory.

## Run it

```bash
python examples/01_hello_world/hello.py
```

You should see logs like:

```
captured 1080x1920 frame
raw screenshot saved: .../screenshots/hello_raw.png
OCR took 1.42s, found 17 text regions
   1. [0.99] 'Settings' @ (240, 1820)
   2. [0.96] '12:34' @ (108, 60)
   ...
annotated copy saved: .../screenshots/hello_annotated.png
```

Open the two PNGs in `./screenshots/` to verify the screenshot was captured
correctly and the detections are where you'd expect.

## Try changing things

- Edit `SAMPLE_KEYWORD` at the top of `hello.py` to a string actually on the
  device's current screen.
- Uncomment the `AdbInput().tap(*found.center)` line to actually tap the match.
- Set `fast=False` on `OcrEngine.get()` to use the more accurate (and slower)
  server model.
