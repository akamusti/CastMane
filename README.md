# CastMane

**A crash-safe screen recorder for Linux (Wayland-first).**

[🇹🇷 Türkçe için tıklayın](README.tr.md)

OBS is powerful — but if it crashes mid-recording, the whole `.mp4` file is often
lost. CastMane is built around a single principle: **a crash must never cost you
the footage.**

## Why CastMane?

Classic recorders finalize the MP4 container (`moov` atom) only when recording
stops cleanly. Crash or `kill` the process and the file is unplayable. CastMane
instead:

1. Stages the recording in a **crash-tolerant container** — fragmented MP4 on
   X11 (`frag_keyframe+empty_moov`), MKV on Wayland (`matroskamux`, which
   tolerates the timestamp-less first frame PipeWire delivers) — so every
   chunk is playable on its own, then delivers MP4.
2. Records to a **`.part` file** and renames it to the final name **atomically**
   only after a clean stop. A leftover `.part` file is still watchable.
3. Stops the encoder **gracefully** (`SIGINT` first, trailer included) and watches
   the encoder process, so an unexpected death is reported instead of silently
   losing footage.

> Verified: a recording killed with `kill -9` remains fully playable
> (`h264`, `ffprobe`-checked). The Wayland pipeline records MKV because
> `mp4mux` aborts on the timestamp-less first frame PipeWire delivers
> ("Buffer has no PTS"); the MKV is remuxed to MP4 with `ffmpeg -c copy`
> on clean stop. See [Crash-safety](#crash-safety) below.

## Features

- 🖥️ Full-screen recording on **Wayland** via `xdg-desktop-portal` ScreenCast +
  GStreamer (`pipewiresrc → openh264enc → matroskamux`), remuxed losslessly to
  MP4 on stop — no OBS, no compositor plugins
- 🖥️ **X11 fallback** via `ffmpeg` (`x11grab`), selected automatically
- 🛡️ Crash-safe output pipeline (fragmented MP4, `.part` staging, atomic rename,
  encoder watchdog)
- 🪶 Minimal Qt interface: Record / Stop, elapsed timer, status line
- 🔊 Optional audio capture (mic by default, system sound via monitor device),
  AAC in the same crash-safe MKV → MP4 pipeline
- 📁 Timestamped files in `~/Videos/CastMane` (`castmane_YYYY-MM-DD_HH-MM-SS.mp4`)

## Requirements

- Linux, Python ≥ 3.10 (developed and tested on **Fedora 44, KDE Plasma, Wayland**)
- `ffmpeg` — for the X11 backend
- `gst-launch-1.0` with the `pipewiresrc`, `openh264enc` and `mp4mux` elements —
  for the Wayland backend (present on stock Fedora KDE; check with
  `gst-inspect-1.0 pipewiresrc`)
- A running `xdg-desktop-portal` with a ScreenCast backend (KDE/GNOME provide one)

## Installation

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python3 -m castmane
```

No system Python packages or compiler toolchain required: the Wayland backend
drives the portal over D-Bus (`dbus-next`) and runs GStreamer as a subprocess,
so `PyGObject` is not needed.

## Usage

1. Start the app. The status line shows the active backend, e.g.
   `Ready [portal (Wayland)]`.
2. Press **Record**. On Wayland, the system screen-share dialog appears —
   pick the monitor and confirm (you have 180 seconds).
3. Press **Stop**. The finished file lands in `~/Videos/CastMane`.

If recording is interrupted (crash, power loss, `kill -9`), look for the
`*.mkv.part` (Wayland) or `*.mp4.part` (X11) file in the same folder — it plays
as-is. Just rename it (and on Wayland, optionally remux to MP4 yourself:
`ffmpeg -i file.mkv.part -c copy file.mp4`).

## Crash-safety

| Layer | Mechanism |
|---|---|
| Container | MKV staging (`matroskamux` tolerates missing timestamps), MP4 via lossless `ffmpeg -c copy` remux on clean stop |
| File handling | Write to `X.mp4.part`, `os.replace()` to `X.mp4` only on clean stop |
| Shutdown | `SIGINT` → wait → `SIGTERM` → `SIGKILL` escalation |
| Monitoring | Encoder watchdog reports early exits with the last log lines |

Reproduce the proof yourself (kill a live MKV recording, then remux):

```bash
gst-launch-1.0 videotestsrc is-live=true ! videoconvert ! openh264enc \
  ! h264parse ! matroskamux ! filesink location=proof.mkv.part &
sleep 4; kill -9 $!
ffprobe -v error -show_entries stream=codec_name proof.mkv.part
ffmpeg -y -v error -i proof.mkv.part -c copy proof.mp4
ffprobe -v error -show_entries stream=codec_name,duration proof.mp4
```

## Architecture

```
src/castmane/
├── app.py               # Qt main window (Record/Stop, timer, status)
├── config.py            # Output dir, fps, bitrate, fragment settings
├── recorder.py          # Crash-safe core: FfmpegX11Recorder + finalize_part()
├── backends/__init__.py # create_backend(): portal on Wayland, ffmpeg on X11
└── backends/portal.py   # PortalRecorder: ScreenCast D-Bus + gst-launch pipe
                           (MKV record, MP4 remux on stop)
```

Portal signatures are discovered from the broker at runtime
(`session_handle` type, `Start` argument order), so the client keeps working
across `xdg-desktop-portal` versions.

## Roadmap

- [x] Full-screen recording (Wayland + X11)
- [x] Crash-safe output pipeline
- [x] Audio capture (mic by default; system sound via `audio_source` monitor device)
- [ ] Window / region selection
- [ ] Pause / resume, configurable quality presets

### Audio

Tick **Record audio (mic)** in the window, or in code:

```python
from castmane.config import AppConfig
cfg = AppConfig(audio_enabled=True)  # default mic
# system sound instead:
# cfg = AppConfig(audio_enabled=True,
#     audio_source="alsa_output.pci-0000_00_1f.3.analog-stereo.monitor")
```

List devices with `pactl list short sources`. Audio is encoded as AAC
(`avenc_aac` on Wayland, `aac` on X11) into the same crash-safe file, so a
`kill -9` recording and its MP4 remux both keep the audio track.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
