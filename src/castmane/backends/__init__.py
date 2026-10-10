"""Backend secimi: Wayland -> portal+GStreamer, X11 -> ffmpeg."""
from __future__ import annotations

import os

from ..config import AppConfig


def session_is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY")) or (
        os.environ.get("XDG_SESSION_TYPE") == "wayland"
    )


def create_backend(cfg: AppConfig):
    """Ortam degiskenine gore dogru kayit motorunu dondurur."""
    if session_is_wayland():
        from .portal import PortalRecorder

        return PortalRecorder(cfg)
    from ..recorder import FfmpegX11Recorder

    return FfmpegX11Recorder(cfg)
