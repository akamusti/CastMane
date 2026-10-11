"""Audio source resolution: microphone, desktop (system sound), or both.

Why this module exists: PulseAudio/PipeWire exposes the microphone as the
default source and desktop audio as a `.monitor` source of the current sink.
Recording "the screen's sound" therefore needs a *different* device than the
mic, and recording both needs *two* inputs mixed together. This module keeps
that device logic in one place so both backends (ffmpeg/X11 and
GStreamer/portal) share it.

- Mic source: ``AppConfig.audio_source`` ("auto"/"default"/"mic" -> "default").
- Desktop source: ``AppConfig.audio_desktop_source`` ("auto" -> the first
  `.monitor` source reported by `pactl`, "" when none is found).
"""
from __future__ import annotations

import shutil
import subprocess

MIC_ALIASES = ("", "auto", "default", "mic")
DESKTOP_ALIASES = ("", "auto")


def normalize_audio_mode(mode: str) -> str:
    """Clamp any input to "mic", "desktop" or "both" (fallback: "mic")."""
    m = (mode or "").strip().lower()
    return m if m in ("mic", "desktop", "both") else "mic"


def list_pulse_sources() -> list[str]:
    """Return PulseAudio source names via `pactl list short sources`.

    Returns [] when pactl is missing or fails (e.g. bare PipeWire without
    the pulse-compat CLI). Never raises.
    """
    if shutil.which("pactl") is None:
        return []
    try:
        r = subprocess.run(
            ["pactl", "list", "short", "sources"],
            capture_output=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    names: list[str] = []
    for line in r.stdout.decode(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            names.append(parts[1])
    return names


def detect_monitor_source(sources: list[str] | None = None) -> str:
    """Pick the desktop-audio (`.monitor`) source, or "" when there is none.

    `sources` is injectable for tests; when None it is read from pactl.
    """
    if sources is None:
        sources = list_pulse_sources()
    for name in sources:
        if name.endswith(".monitor"):
            return name
    return ""


def resolve_mic_source(value: str) -> str:
    """Map mic aliases to the PulseAudio "default" device."""
    if (value or "").strip().lower() in MIC_ALIASES:
        return "default"
    return value.strip()


def resolve_desktop_source(value: str) -> str:
    """Map "auto" to the detected `.monitor` device ("" when not found)."""
    if (value or "").strip().lower() in DESKTOP_ALIASES:
        return detect_monitor_source()
    return value.strip()
