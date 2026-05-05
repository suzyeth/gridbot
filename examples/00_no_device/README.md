# 00 — Zero-device install check

The fastest way to confirm gridbot is installed correctly. **No Android
device required.**

## What it does

1. Reads the bundled ``sample.png`` (a synthetic Android settings-page mockup
   shipped in this directory; ~57 KB, fully under our control, zero leak risk).
2. Runs OCR on it via :class:`gridbot.OcrEngine`.
3. Checks that a known set of English keywords is detected.

If the check passes, your install is good and you can move on to
[`examples/01_hello_world`](../01_hello_world/) — the first example that
actually drives a connected device.

## Run

```bash
python examples/00_no_device/test_install.py
```

Expected output:

```
loaded sample.png: 540x960
loading PaddleOCR (first call may download ~30 MB of model weights)...
running OCR...
detected 19 text regions:
  [1.00] 'Settings'
  [0.95] 'Network & internet'
  [0.99] 'Wi-Fi, Mobile, Data usage'
  ...
matched 6/6 expected keywords: ['Settings', 'Wi-Fi', 'Bluetooth', 'Battery', 'Storage', 'About phone']
install verified — gridbot + OCR are working
```

The first run takes 30–90 seconds because PaddleOCR auto-downloads its model
weights. Subsequent runs take 1–2 seconds.

## If it fails

Run the doctor:

```bash
gridbot doctor
```

Common causes:

- **`paddleocr not installed`** — you installed gridbot without the OCR extra.
  Run ``pip install -e .[ocr]`` from the repo root.
- **Model download failed** — usually a transient network issue. Re-run.
- **Fewer than 4 keywords detected** — your install isn't fully working.
  ``gridbot doctor`` will tell you exactly which dep is broken.
