---
title: Architecture
description: How CastMane is put together.
---

```
src/castmane/
|-- app.py               # Qt main window (Record/Stop, timer, status)
|__ config.py            # Output dir, fps, bitrate, fragment settings
+-- recorder.py          # Crash-safe core: FfmpegX11Recorder + finalize_part()
+-- backends/__init__.py # create_backend(): portal on Wayland, ffmpeg on X11
`-- backends/portal.py   # PortalRecorder: ScreenCast D-Bus + gst-launch pipe
                           (MKV record, MP4 remux on stop)
```

Portal signatures are discovered from the broker at runtime
(`session_handle` type, `Start` argument order), so the client keeps working
across `xdg-desktop-portal` versions.

## Roadmap

- [x] Full-screen recording (Wayland + X11)
- [x] Crash-safe output pipeline
- [x] Audio capture (mic by default; system sound via `audio_source` monitor device)
- [x] Window / region selection
- [x] Pause / resume, configurable quality presets
- [x] One-file AppImage distribution
