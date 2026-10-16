"""Camera device discovery and resolution (OBS-style sources).

Qt (`QMediaDevices`) is the primary source when available; `/dev/video*`
glob is the fallback so headless/offscreen environments and plain
ffmpeg/GStreamer pipelines still resolve a device path.

- `list_cameras()` -> list of (device_path, description).
- `resolve_camera_device(value)` -> concrete `/dev/videoN` path or "".
- `normalize_camera_device(value)` -> "auto" or a `/dev/videoN` path.
"""
from __future__ import annotations

import glob
import re

CAMERA_AUTO_ALIASES = ("", "auto", "default", "cam")
_VIDEO_RE = re.compile(r"^/dev/video\d+$")


def _qt_cameras() -> list[tuple[str, str]]:
    """Query Qt for cameras. Never raises; [] when unavailable."""
    try:
        from PySide6.QtMultimedia import QMediaDevices
    except Exception:
        return []
    try:
        found: list[tuple[str, str]] = []
        for dev in QMediaDevices.videoInputs():
            desc = dev.description() or "Camera"
            # QCameraDevice.id() is a backend token, not a v4l2 path;
            # keep it as description hint only.
            found.append(("", f"{desc}"))
        return found
    except Exception:
        return []


def _v4l2_devices() -> list[str]:
    try:
        return sorted(glob.glob("/dev/video*"))
    except OSError:
        return []


def list_cameras() -> list[tuple[str, str]]:
    """Return [(device_path, label)]. Empty when no camera is present.

    Labels come from Qt descriptions when available, otherwise the
    device path itself. Never raises.
    """
    qt = _qt_cameras()
    v4l2 = _v4l2_devices()
    if not v4l2:
        return []
    if qt and len(qt) == len(v4l2):
        return [(path, desc or path) for path, (_, desc) in zip(v4l2, qt)]
    if qt and len(qt) == 1 and len(v4l2) >= 1:
        # One Qt camera, several /dev nodes (e.g. video0 + metadata video1):
        # label the first node, leave the rest bare.
        out = [(v4l2[0], qt[0][1] or v4l2[0])]
        out += [(p, p) for p in v4l2[1:]]
        return out
    return [(p, p) for p in v4l2]


def normalize_camera_device(value: str) -> str:
    """Clamp to "auto" or a `/dev/videoN` path. Never raises."""
    text = (value or "").strip()
    if not text or text.strip().lower() in CAMERA_AUTO_ALIASES:
        return "auto"
    if _VIDEO_RE.match(text):
        return text
    return "auto"


def resolve_camera_device(value: str) -> str:
    """Map "auto" to the first `/dev/video*` node, "" when none exists."""
    if (value or "").strip().lower() in CAMERA_AUTO_ALIASES or not (value or "").strip():
        devs = _v4l2_devices()
        return devs[0] if devs else ""
    text = value.strip()
    if _VIDEO_RE.match(text):
        return text
    return ""
