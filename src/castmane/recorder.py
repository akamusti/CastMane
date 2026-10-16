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


def final_name_for_part(tmp: Path) -> Path:
    """Strip the trailing `.part` suffix: `take.mp4.part` -> `take.mp4`."""
    name = tmp.name
    if name.endswith(".part"):
        return tmp.with_name(name[: -len(".part")])
    return tmp.with_suffix("")


def find_stale_parts(output_dir: Path) -> list[Path]:
    """List leftover `.part` files from interrupted recordings.

    Never raises: an unreadable output dir means "nothing to recover".
    """
    try:
        target = Path(output_dir)
        if not target.is_dir():
            return []
        return sorted(p for p in target.glob("*.part") if p.is_file())
    except OSError:
        return []


def recover_part(tmp: Path) -> Path | None:
    """Promote one leftover `.part` via the crash-safe atomic rename.

    Empty files are not promoted (same rule as `finalize_part`).
    """
    return finalize_part(Path(tmp), final_name_for_part(Path(tmp)))


def format_file_size(nbytes: int) -> str:
    """Human size for the recent-recordings list: `800 KB`, `12.4 MB`."""
    try:
        kb = max(0, int(nbytes)) / 1024
    except (TypeError, ValueError):
        return "0 KB"
    if kb < 1024:
        return f"{kb:.0f} KB"
    return f"{kb / 1024:.1f} MB"


def list_recent_recordings(output_dir: Path, limit: int = 10) -> list[Path]:
    """Newest finished recordings first. Never raises; `.part`
    staging files are not recordings yet and are skipped."""
    try:
        target = Path(output_dir)
        if not target.is_dir():
            return []
        files = [
            p for p in (*target.glob("*.mp4"), *target.glob("*.mkv"))
            if p.is_file() and not p.name.endswith(".part")
        ]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:max(1, limit)]
    except OSError:
        return []


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
        from .audio import (
            effective_gains,
            normalize_audio_mode,
            resolve_desktop_source,
            resolve_mic_source,
        )
        from .config import normalize_format

        display = os.environ.get("DISPLAY", ":0")
        cmd = ["ffmpeg", "-y"]
        if self.cfg.window_id > 0:
            # Single window: X11 window id (e.g. from `xwininfo`).
            cmd += ["-window_id", str(self.cfg.window_id)]
        cmd += ["-f", "x11grab"]
        # Mouse cursor overlay (ffmpeg x11grab flag).
        cmd += ["-draw_mouse", "1" if self.cfg.show_cursor else "0"]
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
        # Camera picture-in-picture (OBS-style): a v4l2 input burned into
        # the bottom-right corner via overlay. Preview-only mode adds no
        # input here (the Studio preview shows the camera separately).
        from .camera import resolve_camera_device

        cam_dev = ""
        if getattr(self.cfg, "camera_enabled", False) and getattr(
            self.cfg, "camera_embed", True
        ):
            cam_dev = resolve_camera_device(
                getattr(self.cfg, "camera_device", "auto"))
        n_video_inputs = 1 + (1 if cam_dev else 0)
        ai = n_video_inputs  # first audio input index (shifts with camera)
        if cam_dev:
            cmd += ["-f", "v4l2", "-video_size", "320x240", "-i", cam_dev]
        if self.cfg.audio_enabled:
            # Audio mode selects the PulseAudio input(s):
            # "mic" -> default source, "desktop" -> .monitor device,
            # "both" -> two inputs mixed with amix.
            # NOTE: input indices shift by +1 when the camera input above
            # occupies slot 1 (`ai` already accounts for this).
            mode = normalize_audio_mode(self.cfg.audio_mode)
            if mode == "desktop":
                src = resolve_desktop_source(self.cfg.audio_desktop_source)
                cmd += ["-f", "pulse", "-i", src if src else "default"]
            elif mode == "both":
                mic = resolve_mic_source(self.cfg.audio_source)
                desk = resolve_desktop_source(self.cfg.audio_desktop_source)
                cmd += ["-f", "pulse", "-i", mic]
                cmd += ["-f", "pulse", "-i", desk if desk else "default"]
            else:
                src = resolve_mic_source(self.cfg.audio_source)
                cmd += ["-f", "pulse", "-i", src]
        cmd += [
            "-c:v", self.cfg.video_codec,
            "-pix_fmt", "yuv420p",
        ]
        # Filter stage. Without a camera the historic layout is kept
        # verbatim (single-source gain via `-filter:a`, no forced maps);
        # with a camera everything composes in one `-filter_complex`
        # (overlay + optional audio mix/gain) with explicit maps.
        if not cam_dev:
            if self.cfg.audio_enabled:
                cmd += ["-c:a", "aac", "-b:a", f"{self.cfg.audio_bitrate_kbps}k"]
                mode = normalize_audio_mode(self.cfg.audio_mode)
                mic_gain, desk_gain = effective_gains(self.cfg)
                if mode == "both":
                    # Mix mic (1:a) + desktop (2:a) down to one AAC track.
                    # Per-source gain keeps mic/desktop balanced (OBS-style mixer).
                    parts = []
                    if mic_gain != 1.0:
                        parts.append(f"[1:a]volume={mic_gain}[a0]")
                    else:
                        parts.append("[1:a]anull[a0]")
                    if desk_gain != 1.0:
                        parts.append(f"[2:a]volume={desk_gain}[a1]")
                    else:
                        parts.append("[2:a]anull[a1]")
                    parts.append(
                        "[a0][a1]amix=inputs=2:duration=longest:"
                        "dropout_transition=0[aout]"
                    )
                    filt = ";".join(parts)
                    cmd += ["-filter_complex", filt, "-map", "0:v", "-map", "[aout]"]
                # Software gain: no filter added at 1.0.
                elif mode == "desktop":
                    if desk_gain != 1.0:
                        cmd += ["-filter:a", f"volume={desk_gain}"]
                elif mic_gain != 1.0:
                    cmd += ["-filter:a", f"volume={mic_gain}"]
        else:
            filters: list[str] = [
                "[1:v]scale=320:240,format=yuv420p[cam];"
                "[0:v][cam]overlay=W-w-10:H-h-10,format=yuv420p[vout]"
            ]
            a_out: str | None = None
            if self.cfg.audio_enabled:
                cmd += ["-c:a", "aac", "-b:a", f"{self.cfg.audio_bitrate_kbps}k"]
                mode = normalize_audio_mode(self.cfg.audio_mode)
                mic_gain, desk_gain = effective_gains(self.cfg)
                if mode == "both":
                    parts = []
                    if mic_gain != 1.0:
                        parts.append(f"[{ai}:a]volume={mic_gain}[a0]")
                    else:
                        parts.append(f"[{ai}:a]anull[a0]")
                    if desk_gain != 1.0:
                        parts.append(f"[{ai + 1}:a]volume={desk_gain}[a1]")
                    else:
                        parts.append(f"[{ai + 1}:a]anull[a1]")
                    parts.append(
                        "[a0][a1]amix=inputs=2:duration=longest:"
                        "dropout_transition=0[aout]"
                    )
                    filters.append(";".join(parts))
                    a_out = "[aout]"
                elif mode == "desktop":
                    if desk_gain != 1.0:
                        filters.append(f"[{ai}:a]volume={desk_gain}[aout]")
                        a_out = "[aout]"
                elif mic_gain != 1.0:
                    filters.append(f"[{ai}:a]volume={mic_gain}[aout]")
                    a_out = "[aout]"
            cmd += ["-filter_complex", ";".join(filters)]
            cmd += ["-map", "[vout]"]
            if self.cfg.audio_enabled:
                cmd += ["-map", a_out if a_out else f"{ai}:a"]
        if normalize_format(self.cfg.output_format) == "mkv":
            # Matroska needs no movflags: it is streamable by design,
            # so a killed recording stays playable as-is.
            cmd += [str(tmp)]
        else:
            cmd += [
                "-movflags", self.cfg.movflags,
                str(tmp),
            ]
        return cmd

    def start(self) -> Path:
        if self.state.active:
            raise RuntimeError("recording already active")
        final = self.cfg.next_output_path()
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
