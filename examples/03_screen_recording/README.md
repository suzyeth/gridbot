# 03 — Screen recording

Record device video over ADB using :class:`gridbot.ScreenRecorder`. Same
underlying mechanism as `adb shell screenrecord`: writes mp4 to the device,
then pulls it back to the host.

> ⚠️ **The mp4 this script produces captures whatever your device is
> showing in real time.** It saves to `./recordings/`, which gridbot's repo
> `.gitignore` already excludes — but if you copy this example into your
> own repo, double-check your `.gitignore` covers `recordings/` before
> running, especially if the device is showing anything you don't want to
> commit.

## Limits inherited from Android

- **180 seconds maximum per recording** (system-imposed).
- **1080p maximum resolution.**
- Default bitrate **4 Mbps** (~30 MB / minute). Adjust with the
  ``bitrate_mbps`` parameter on ``ScreenRecorder.record``.

## Run

### Blocking — record exactly N seconds, then return

```bash
python examples/03_screen_recording/record.py                 # 30s default
python examples/03_screen_recording/record.py --duration 10   # 10s
```

The script blocks for the full duration. Useful when you know up front how
long you want to capture.

### Async — record while the script does other things

```bash
python examples/03_screen_recording/record.py --async --duration 30
```

This calls ``rec.start()``, runs a countdown loop in the foreground (the
real version of this is your automation code), and then ``rec.stop()``
terminates the recording and pulls the file. Use this pattern when you want
to wrap an arbitrary block of work and stop the recording only when that
work finishes.

## Output

```
./recordings/rec_<timestamp>.mp4
```

Open with any standard video player (VLC / Windows Media Player / mpv).

## Code layout

The interesting parts of `record.py`:

```python
from gridbot import ScreenRecorder

# Blocking
rec = ScreenRecorder()
path = rec.record(duration_seconds=30)         # returns Path to local mp4

# Async — wrap arbitrary work
rec.start(max_duration_sec=60)
do_whatever_you_want_recorded()
path = rec.stop()
```

## Tips

- **Bitrate vs file size** — bumping `bitrate_mbps` to 8 makes recordings
  noticeably crisper but doubles the file size. 4 Mbps is plenty for
  scripted automation review.
- **Async mode flushes its own file** — `rec.stop()` waits ~1.5s after
  killing the device-side process to give `screenrecord` time to finalize
  the mp4 header. Don't be surprised if the file briefly looks zero-byte
  while that's happening.
- **Multiple devices** — if `adb devices` shows more than one entry, pass
  ``serial="..."`` to ``ScreenRecorder()`` to pick a specific device.
