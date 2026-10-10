"""Crash-safe recording core.

Design note (a cure for OBS-style crashes):
- ffmpeg/GStreamer writes with `-movflags frag_keyframe+empty_moov`:
  the moov atom is written piecewise, not once at the end, so the file
  stays playable even if the process is killed.
- Recording goes to an `.mp4.part` file; on successful stop it is moved
  to the final name with atomic `os.replace()`.
- Watchdog: if the encoder process dies unexpectedly, the last ~5s of log
  is kept and the UI shows "saved: X.mp4.part".
"""
from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig


def finalize_part(tmp: Path, final: Path) -> Path | None:
    """Crash-safe finish: atomically rename `.part` to final if healthy.

    On kill/crash the `.part` file stays in place and remains playable
    thanks to fragmented MP4."""
    if tmp.exists() and tmp.stat().st_size > 0:
        os.replace(tmp, final)
        return final
    return None


@dataclass
class RecordingState:
    active: bool = False
    final_path: Path | None = None
    tmp_path: Path | None = None
    mkv_path: Path | None = None  # portal backend intermediate (MKV)
    started_at: float = 0.0
    last_error: str = ""
    paused: bool = False  # frozen via SIGSTOP
    pause_started: float = 0.0
    paused_total: float = 0.0  # total paused time


class FfmpegX11Recorder:
    """X11 fallback backend. Does not work on Wayland (gives black screen),
    but is ideal for testing the crash-safe core logic."""

    name = "ffmpeg (X11)"

    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.state = RecordingState()
        self._proc: subprocess.Popen[bytes] | None = None
        self._watchdog: threading.Thread | None = None
        self._stop_requested = threading.Event()

    def build_cmd(self, tmp: Path) -> list[str]:
        display = os.environ.get("DISPLAY", ":0")
        cmd = ["ffmpeg", "-y"]
        if self.cfg.window_id > 0:
            # Single window: X11 window id (e.g. from `xwininfo`).
            cmd += ["-window_id", str(self.cfg.window_id)]
        cmd += ["-f", "x11grab"]
        if self.cfg.region_w > 0 and self.cfg.region_h > 0:
            # Fixed region: WxH + top-left corner.
            cmd += [
                "-video_size", f"{self.cfg.region_w}x{self.cfg.region_h}",
                "-grab_x", str(self.cfg.region_x),
                "-grab_y", str(self.cfg.region_y),
                "-show_region", "1",
            ]
        elif self.cfg.capture_mode == "ask" and self.cfg.window_id <= 0:
            # Interactive: the user draws the frame with the mouse.
            cmd += ["-select_region", "1", "-show_region", "1"]
        cmd += [
            "-framerate", str(self.cfg.fps),
            "-i", display,
        ]
        if self.cfg.audio_enabled:
            # Via PulseAudio compatibility (provided by PipeWire):
            # "auto"/"default"/"mic" -> default source, else the given device.
            src = self.cfg.audio_source
            if src in ("", "auto", "default", "mic"):
                src = "default"
            cmd += ["-f", "pulse", "-i", src]
        cmd += [
            "-c:v", self.cfg.video_codec,
            "-pix_fmt", "yuv420p",
        ]
        if self.cfg.audio_enabled:
            cmd += ["-c:a", "aac", "-b:a", f"{self.cfg.audio_bitrate_kbps}k"]
            # Software gain: no filter added at 1.0.
            if self.cfg.audio_gain != 1.0:
                cmd += ["-filter:a", f"volume={self.cfg.audio_gain}"]
        cmd += [
            "-movflags", self.cfg.movflags,
            str(tmp),
        ]
        return cmd

    def start(self) -> Path:
        if self.state.active:
            raise RuntimeError("recording already active")
        final = self.cfg.next_output_path(".mp4")
        tmp = self.cfg.tmp_path_for(final)
        cmd = self.build_cmd(tmp)
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        self.state = RecordingState(
            active=True, final_path=final, tmp_path=tmp,
            started_at=time.time(),
        )
        self._stop_requested.clear()
        self._watchdog = threading.Thread(
            target=self._watch, daemon=True
        )
        self._watchdog.start()
        return final

    def _watch(self) -> None:
        assert self._proc is not None
        out, _ = self._proc.communicate()
        if self._stop_requested.is_set():
            return
        # unexpected death -> crash-safe: the .part file is still there
        tail = (out or b"")[-2000:].decode(errors="replace")
        self.state.last_error = f"encoder exited early (rc={self._proc.returncode}): {tail[-300:]}"
        self.state.active = False

    def stop(self) -> Path | None:
        if not self.state.active or self._proc is None:
            return None
        self._stop_requested.set()
        if self.state.paused:
            # A stopped process ignores signals; resume first.
            self.resume()
        # graceful SIGINT first (ffmpeg writes the trailer), then SIGTERM
        self._proc.send_signal(signal.SIGINT)
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self.state.active = False
        assert self.state.tmp_path and self.state.final_path
        done = finalize_part(self.state.tmp_path, self.state.final_path)
        if done is None:
            self.state.last_error = "output file was not created"
        return done

    @property
    def elapsed(self) -> float:
        if not self.state.started_at:
            return 0.0
        end = self.state.pause_started if self.state.paused else time.time()
        return end - self.state.started_at - self.state.paused_total

    def pause(self) -> None:
        """Freeze the encoder process (SIGSTOP). The clock freezes too: paused
        time is excluded from `elapsed` and shows up as a jump in the video."""
        if not self.state.active or self._proc is None:
            raise RuntimeError("no active recording to pause")
        if self.state.paused:
            return
        self._proc.send_signal(signal.SIGSTOP)
        self.state.paused = True
        self.state.pause_started = time.time()

    def resume(self) -> None:
        if not self.state.paused or self._proc is None:
            raise RuntimeError("no paused recording to resume")
        self._proc.send_signal(signal.SIGCONT)
        self.state.paused_total += time.time() - self.state.pause_started
        self.state.paused = False
        self.state.pause_started = 0.0


@dataclass
class PortalRecorderConfig:
    """Wayland backend target pipeline (phase-2, not wired up yet):

    gst-launch-1.0 pipewiresrc path=<portal-node-id> ! videoconvert !
        openh264enc bitrate=8000 ! h264parse ! \
        mp4mux fragment-duration=1000 ! filesink location=X.mp4.part

    Portal flow: org.freedesktop.portal.Desktop::CreateSession +
    SelectSources(screencast) + Start -> PipeWire node id + fd.
    This file only documents the target; the implementation lives in
    `backends/portal.py` (python-dbus-next + Gst).
    """
    fragment_ms: int = 1000
