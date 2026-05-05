# 02 — State detection + navigation

The hello-world example shows the three primitives (capture / input / OCR).
This one shows the layer above: turning OCR text into named **states**, and
then BFS-driving the UI from any state to any other state via a YAML-described
**screen graph**.

The example targets the Android system Settings app — a stable, vendor-agnostic
UI you can drive without installing anything else.

## Files

```
02_state_navigator/
├── screens.yaml   # state graph: home <-> settings <-> about
├── rules.py       # StateRule list mapping screen -> OCR signature
├── nav_demo.py    # wires it all together
└── README.md      # you are here
```

## Run it

### Dry run (no device required)

```bash
python examples/02_state_navigator/nav_demo.py
```

Validates the YAML, builds the rule list, and exercises the BFS path-finder
with a few sample queries. Useful as a smoke test that gridbot is installed
correctly.

### Live (drives a connected Android device)

```bash
python examples/02_state_navigator/nav_demo.py --live
python examples/02_state_navigator/nav_demo.py --live --target home
```

Detects the current screen, then tries to navigate to the target. To
reproduce the demo, start with the device on its launcher.

## Adapting to your own app

The pattern is the same for any Android app or game:

1. **Capture screenshots of every screen you care about** with
   `AdbCapture.screenshot_to_file()`. Open them and decide on a small set of
   named states (`login`, `main_menu`, `inventory`, ...).

2. **Write a rule per state** in `rules.py`-style. Each rule needs a few
   stable text fragments unique to that screen. Use ``OcrEngine.read()`` on
   the screenshots to see what comes through clearly.

3. **Order rules from most-specific to most-generic.** The detector returns
   the first match. Use ``forbidden=[...]`` to disambiguate sub-pages from
   their parent (this example uses `Build number` as a forbidden keyword on
   the top-level Settings rule).

4. **Author `screens.yaml`.** For each state, list the outgoing transitions:
   the action that triggers the move, the destination state, and how long to
   wait for the transition. Five action types are available:
   - ``tap_text`` — OCR-find the text and tap it (fastest path, with optional
     ``fallback_coords`` for when fast OCR misses).
   - ``tap_coords`` — fixed `(x, y)`.
   - ``keyevent`` — `BACK` or `HOME`.
   - ``swipe`` — gesture from one point to another.
   - ``wait_until`` — no-op; just wait for the state to change on its own.

5. **Run with `--live`** and watch the logs. When BFS picks a path it prints
   each `current -> next` hop. Misclassifications and dead transitions are
   logged loudly so you can iterate on rules / YAML.

## Tips

- **`fast_ocr=True` for state detection** — you'll classify the screen many
  times per navigation, so you want each classification fast (~1.5s). Reserve
  the accurate model for one-shot reads where precision matters.
- **`fallback_coords` is a huge latency win** — once you've measured a
  button's stable position, add it to the YAML so the worst case is a coord
  tap, not a 30–60s slow-OCR pass.
- **Dead-transition detection** — if the same `(state, action_type)` fires
  twice in a row without the state changing, the navigator gives up. This
  catches stale YAML quickly.
