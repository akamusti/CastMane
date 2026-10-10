---
title: Usage
description: Record, pause, stop, and recover recordings with CastMane.
---

## Recording

1. **Start the app.** The status line shows the active backend, e.g.
   `Ready [portal (Wayland)]`.
2. **Pick a source:** Full-screen, Window, or Ask / Select region.
   On Wayland the system dialog lists monitors or windows; on X11, *Ask*
   opens a drag-to-select frame.
3. **Press Record.** On Wayland the system screen-share dialog appears —
   pick the monitor or window and confirm (you have 180 seconds).
4. **Press Stop.** The finished file lands in `~/Videos/CastMane` as
   `castmane_YYYY-MM-DD_HH-MM-SS.mp4`.

## Language

The interface is English by default. To switch to Turkish, pick
**Türkçe** from the **Language** dropdown in Recording Settings.
In code: `AppConfig(language="tr")`.

## Pause and resume

Press **Pause** mid-recording to freeze the encoder (`SIGSTOP`); the timer
stops and the paused stretch is left out of the footage. **Resume** continues
into the same file. Stopping while paused resumes first, so the trailer is
always written cleanly.

## Recovering an interrupted recording

Look for the `*.mkv.part` (Wayland) or `*.mp4.part` (X11) file in the same
folder — it plays as-is. Just rename it (on Wayland, optionally remux to MP4
yourself):

```bash
ffmpeg -i file.mkv.part -c copy file.mp4
```

See [Crash-safety](../guides/crash-safety/) for why this works.
