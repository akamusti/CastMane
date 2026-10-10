"""Kullanici ayari + varsayilan cikti yolu."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class AppConfig:
    output_dir: Path = Path.home() / "Videos" / "CastMane"
    fps: int = 30
    # Crash-safe: ffmpeg/GStreamer'a fragmented MP4 yazdiriyoruz,
    # process olse bile dosya oynatilabilir kaliyor.
    movflags: str = "frag_keyframe+empty_moov+default_base_moof"
    video_codec: str = "libopenh264"  # ffmpeg yuzu; GStreamer yuzu: openh264enc
    video_bitrate_kbps: int = 8000  # portal/GStreamer hatti
    fragment_ms: int = 1000  # mp4mux fragment-duration: crash'te dosya yasar
    audio_enabled: bool = False  # MVP: sessiz tam-ekran. Ses faz-2.

    def next_output_path(self, suffix: str = ".mp4") -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return self.output_dir / f"castmane_{stamp}{suffix}"

    def tmp_path_for(self, final: Path) -> Path:
        """Ayni klasorde .part dosyasi: crash'te yarim dosya belli olur,
        basarili bitiste atomic rename ile finale tasinir."""
        return final.with_suffix(final.suffix + ".part")
