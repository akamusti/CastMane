"""Camera device discovery and resolution (OBS-style sources).

Qt (`QMediaDevices`) is the primary source when available; `/dev/video*`
glob is the fallback so headless/offscreen environments and plain
ffmpeg/GStreamer pipelines still resolve a device path.

- `list_cameras()` -> list of (device_path, description).
- `resolve_camera_device(value)` -> concrete `/dev/videoN` path or "".
- `normalize_camera_device(value)` -> "auto" or a `/dev/videoN` path.

Placement (OBS-style PiP) is stored in normalised space, so the preview
and the recorded file agree at any resolution:

- `camera_pos_x` / `camera_pos_y` -> 0..1 of the free space (0 = flush
  with the left/top edge, 1 = flush with the right/bottom edge).
- `camera_scale` -> camera width as a fraction of the frame width.
"""
from __future__ import annotations

import glob
import re

CAMERA_AUTO_ALIASES = ("", "auto", "default", "cam")
_VIDEO_RE = re.compile(r"^/dev/video\d+$")

#: PiP placement bounds. 45 % keeps a corner overlay from covering the
#: whole screen; 10 % is still readable on a 4K capture.
CAMERA_SCALE_MIN = 0.10
CAMERA_SCALE_MAX = 0.45
CAMERA_SCALE_DEFAULT = 0.22
CAMERA_POS_DEFAULT_X = 0.72
CAMERA_POS_DEFAULT_Y = 0.66


def clamp_camera_position(value: float) -> float:
    """Clamp a normalised PiP position to 0..1; garbage -> 0.0."""
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def clamp_camera_scale(value: float) -> float:
    """Clamp a PiP width fraction; garbage -> the default size."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return CAMERA_SCALE_DEFAULT
    return max(CAMERA_SCALE_MIN, min(CAMERA_SCALE_MAX, number))


def camera_overlay_rect(
    pos_x: float,
    pos_y: float,
    scale: float,
    frame_w: int,
    frame_h: int,
    cam_w: int = 0,
    cam_h: int = 0,
    cam_aspect: float = 0.0,
) -> tuple[int, int, int, int]:
    """Pixel `(x, y, w, h)` of the camera PiP for a known frame size.

    Used by the portal compositor, which needs absolute coordinates.
    Aspect follows `cam_aspect` when given, else `cam_w`/`cam_h`, else
    4:3. All values are clamped inside the frame and rounded to even
    numbers for the yuv420 encoders.
    """
    try:
        width = max(2, int(frame_w))
        height = max(2, int(frame_h))
    except (TypeError, ValueError):
        width, height = 1920, 1080
    if width <= 0 or height <= 0:
        width, height = 1920, 1080
    aspect = 4 / 3
    try:
        if cam_aspect and float(cam_aspect) > 0:
            aspect = float(cam_aspect)
        elif cam_w and cam_h:
            aspect = float(cam_w) / float(cam_h)
    except (TypeError, ValueError, ZeroDivisionError):
        aspect = 4 / 3
    if aspect <= 0:
        aspect = 4 / 3
    width_f = clamp_camera_position(pos_x)
    height_f = clamp_camera_position(pos_y)
    cam_px_w = max(2, int(round(width * clamp_camera_scale(scale))))
    cam_px_h = max(2, int(round(cam_px_w / aspect)))
    # Never let an extreme scale/aspect overflow the frame.
    cam_px_w = min(cam_px_w, width)
    cam_px_h = min(cam_px_h, height)
    cam_px_w -= cam_px_w % 2
    cam_px_h -= cam_px_h % 2
    slack_x = max(0, width - cam_px_w)
    slack_y = max(0, height - cam_px_h)
    x = int(round(slack_x * width_f))
    y = int(round(slack_y * height_f))
    x -= x % 2
    y -= y % 2
    return x, y, cam_px_w, cam_px_h


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
