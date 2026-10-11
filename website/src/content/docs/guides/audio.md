---
title: Audio
description: Microphone and system-sound capture with software gain.
---

Tick **Record audio** in the window and pick the source — **Mic**,
**Desktop** (system sound), or **Both** (mixed into one track) — or in code:

```python
from castmane.config import AppConfig
cfg = AppConfig(audio_enabled=True)  # default mic
# system sound instead:
# cfg = AppConfig(audio_enabled=True, audio_mode="desktop")
# mic + system sound mixed:
# cfg = AppConfig(audio_enabled=True, audio_mode="both")
```

List devices with `pactl list short sources`. "Desktop" auto-detects the
first `.monitor` source; paste a device name into the desktop-source field
(or `audio_desktop_source`) when auto-detection picks the wrong sink. Audio
is encoded as AAC
(`avenc_aac` on Wayland, `aac` on X11) into the same crash-safe file, so a
`kill -9` recording and its MP4 remux both keep the audio track.

:::tip[Quiet system sound?]
Monitor sources have no mic-style input boost, so system audio can sound much
fainter than mic recordings. Raise the gain in the window (**%**) or in code
(`AppConfig(audio_gain=2.0)` ~ +6 dB, `3.0` ~ +9.5 dB). Stay at or below
`5.0` to avoid clipping.
:::
