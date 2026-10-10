---
title: Installation
description: Install CastMane via AppImage, build it yourself, or run from source.
---

## Option 1 — AppImage (recommended)

Download the AppImage from the
[Releases page](https://github.com/akamusti/CastMane/releases), then:

```bash
chmod +x CastMane-*.AppImage
./CastMane-*.AppImage
```

That's it — no Python, venv, or pip setup. The AppImage bundles Python, Qt,
and all PyPI dependencies.

### Host tools you still need

Install these on your system (everything else is bundled):

```bash
# Fedora / KDE (tested on Fedora 44, KDE Plasma, Wayland)
sudo dnf install ffmpeg gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugin-openh264

# Ubuntu / Debian
sudo apt install ffmpeg gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly
```

| Component       | Wayland backend                                                  | X11 backend              |
| --------------- | ---------------------------------------------------------------- | ------------------------ |
| OS              | Linux, Python ≥ 3.10                                             | Linux, Python ≥ 3.10     |
| Video pipeline  | `gst-launch-1.0` with `pipewiresrc`, `openh264enc`, `matroskamux` | `ffmpeg` with `x11grab`  |
| System service  | `xdg-desktop-portal` with a ScreenCast backend (KDE/GNOME)       | —                        |
| Audio (optional)| Pulse/PipeWire source (`pactl list short sources`)               | Pulse source             |

Missing something? The app shows a friendly popup telling you exactly what
to install.

## Option 2 — Build the AppImage yourself

```bash
./packaging/build-appimage.sh
./dist/CastMane-*.AppImage
```

## Option 3 — From source (developers)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python3 -m castmane
```

No system Python packages or compiler toolchain required: the Wayland backend
drives the portal over D-Bus (`dbus-next`) and runs GStreamer as a
subprocess, so `PyGObject` is not needed.
