"""Crash-safe kayit cekirdegi.

Tasarim notu (OBS crash'lerine care):
- ffmpeg/GStreamer'a `-movflags frag_keyframe+empty_moov` ile yazdirilir:
  moov atomu basa degil parca parca yazilir, process kill yese bile
  dosya oynatilabilir kalir.
- Kayit `.mp4.part` dosyasina yapilir, stop basarili olursa atomic
  `os.replace()` ile finale tasinir.
- Watchdog: encoder process'i beklenmedik biterse son 5 sn'lik log
  saklanir, UI "kurtarildi: X.mp4.part" gosterir.
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
    """Crash-safe bitis: `.part` saglikliysa atomic rename ile finale tasinir.

    Kill/crash durumunda `.part` dosyasi yerinde kalir ve fragmented
    MP4 sayesinde oynatilabilir olur."""
    if tmp.exists() and tmp.stat().st_size > 0:
        os.replace(tmp, final)
        return final
    return None


@dataclass
class RecordingState:
    active: bool = False
    final_path: Path | None = None
    tmp_path: Path | None = None
    mkv_path: Path | None = None  # portal backend ara urunu (MKV)
    started_at: float = 0.0
    last_error: str = ""


class FfmpegX11Recorder:
    """X11 fallback backend. Wayland'da calismaz (siyah ekran verir),
    ama cekirdek crash-safe mantigini test etmek icin birebir."""

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
            # Tek pencere: X11 pencere kimligi (örn. `xwininfo` ciktisi).
            cmd += ["-window_id", str(self.cfg.window_id)]
        cmd += ["-f", "x11grab"]
        if self.cfg.region_w > 0 and self.cfg.region_h > 0:
            # Sabit bolge: WxH + sol-ust kose.
            cmd += [
                "-video_size", f"{self.cfg.region_w}x{self.cfg.region_h}",
                "-grab_x", str(self.cfg.region_x),
                "-grab_y", str(self.cfg.region_y),
                "-show_region", "1",
            ]
        elif self.cfg.capture_mode == "ask" and self.cfg.window_id <= 0:
            # Etkilesimli: kullanici fareyle cerceveyi cizer.
            cmd += ["-select_region", "1", "-show_region", "1"]
        cmd += [
            "-framerate", str(self.cfg.fps),
            "-i", display,
        ]
        if self.cfg.audio_enabled:
            # PulseAudio uyumlulugu uzerinden (PipeWire saglar):
            # "auto"/"default"/"mic" -> varsayilan kaynak, yoksa verilen cihaz.
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
        cmd += [
            "-movflags", self.cfg.movflags,
            str(tmp),
        ]
        return cmd

    def start(self) -> Path:
        if self.state.active:
            raise RuntimeError("zaten kayit aktif")
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
        # beklenmedik olum -> crash-safe: .part dosyasi duruyor
        tail = (out or b"")[-2000:].decode(errors="replace")
        self.state.last_error = f"encoder erken bitti (rc={self._proc.returncode}): {tail[-300:]}"
        self.state.active = False

    def stop(self) -> Path | None:
        if not self.state.active or self._proc is None:
            return None
        self._stop_requested.set()
        # once graceful SIGINT (ffmpeg trailer yazar), olmazsa SIGTERM
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
            self.state.last_error = "cikti dosyasi olusmadi"
        return done

    @property
    def elapsed(self) -> float:
        if not self.state.started_at:
            return 0.0
        return time.time() - self.state.started_at


@dataclass
class PortalRecorderConfig:
    """Wayland backend hedef pipeline (faz-2, henuz baglanmadi):

    gst-launch-1.0 pipewiresrc path=<portal-node-id> ! videoconvert !
        openh264enc bitrate=8000 ! h264parse ! \
        mp4mux fragment-duration=1000 ! filesink location=X.mp4.part

    Portal akisi: org.freedesktop.portal.Desktop::CreateSession +
    SelectSources(screencast) + Start -> PipeWire node id + fd.
    Bu dosya sadece hedefi belgeliyor; implementasyon `backends/portal.py`
    icinde olacak (python-dbus-next + Gst).
    """
    fragment_ms: int = 1000
