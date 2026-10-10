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
    audio_enabled: bool = False  # True ise mikrofon/sistem sesi de kaydedilir
    # Pulse/PipeWire kaynak adi: "auto"/"default"/"mic" -> varsayilan kaynak
    # (genelde mikrofon). Sistem sesi icin monitor cihazi yazilir, örn:
    # "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor".
    # `pactl list short sources` ile listelenir.
    audio_source: str = "auto"
    audio_bitrate_kbps: int = 128  # AAC ses bitrate'i
    # Yazilimsal ses kazanci (carpan): 1.0 = %100 (degisiklik yok).
    # Monitor kaynagi (sistem sesi) mikrofona gore cılız gelirse
    # yukseltin, örn. 2.0 (~+6 dB) veya 3.0 (~+9.5 dB). 5.0'yi
    # gecmeyin (kırpılma/distorsiyon riski).
    audio_gain: float = 1.0
    # Kalite on ayari: "draft" (hafif/hizli), "balanced" (varsayilan),
    # "high" (yogun). fps X11 yakalamayi, bitrate iki backend'i de etkiler.
    quality_preset: str = "balanced"

    def apply_quality_preset(self, name: str) -> None:
        presets = {
            "draft": {"fps": 24, "video_bitrate_kbps": 4000},
            "balanced": {"fps": 30, "video_bitrate_kbps": 8000},
            "high": {"fps": 60, "video_bitrate_kbps": 16000},
        }
        if name not in presets:
            raise ValueError(f"bilinmeyen kalite on ayari: {name}")
        self.quality_preset = name
        self.fps = presets[name]["fps"]
        self.video_bitrate_kbps = presets[name]["video_bitrate_kbps"]
    # Kaynak secimi: "fullscreen" (monitor), "window" (pencere),
    # "ask" (kullanicidan secmesi istenir).
    # Wayland: portal SelectSources `types` bitmask'ine cevrilir
    # (1=monitor, 2=window, 3=ikisi; sistem diyafonu acar).
    # X11: "window" window_id gerektirir, "ask" fareyle bolge
    # secimini acar (ffmpeg -select_region).
    capture_mode: str = "fullscreen"
    region_x: int = 0  # X11 sabit bolge sol-ust kose (0 = tam ekran)
    region_y: int = 0
    region_w: int = 0  # 0 = tam ekran genisligi
    region_h: int = 0
    window_id: int = 0  # X11: 0 disi deger tek pencere yakalar

    def source_types(self) -> int:
        """Portal SelectSources `types` bitmask'i."""
        if self.capture_mode == "window":
            return 2
        if self.capture_mode == "ask":
            return 3  # 1 | 2: monitor veya pencere
        return 1  # fullscreen varsayilan

    def next_output_path(self, suffix: str = ".mp4") -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return self.output_dir / f"castmane_{stamp}{suffix}"

    def tmp_path_for(self, final: Path) -> Path:
        """Ayni klasorde .part dosyasi: crash'te yarim dosya belli olur,
        basarili bitiste atomic rename ile finale tasinir."""
        return final.with_suffix(final.suffix + ".part")
