"""User settings + default output path."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .audio import normalize_audio_mode
from .i18n import DEFAULT_LANGUAGE, normalize


@dataclass
class AppConfig:
    output_dir: Path = Path.home() / "Videos" / "CastMane"
    # UI language: "en" (default) or "tr". Switchable at runtime,
    # e.g. AppConfig(language="tr").
    language: str = DEFAULT_LANGUAGE
    fps: int = 30
    # Crash-safe: ffmpeg/GStreamer writes fragmented MP4,
    # so the file stays playable even if the process dies.
    movflags: str = "frag_keyframe+empty_moov+default_base_moof"
    video_codec: str = "libopenh264"  # ffmpeg side; GStreamer side: openh264enc
    video_bitrate_kbps: int = 8000  # portal/GStreamer pipeline
    fragment_ms: int = 1000  # mp4mux fragment-duration: file survives a crash
    audio_enabled: bool = False  # when True, mic/system sound is recorded too
    # What to record: "mic" (microphone via the default source), "desktop"
    # (system sound via a .monitor device), or "both" (mixed together).
    audio_mode: str = "mic"
    # Pulse/PipeWire source name: "auto"/"default"/"mic" -> default source
    # (usually the mic). For system sound pass a monitor device, e.g.:
    # "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor".
    # List with `pactl list short sources`.
    audio_source: str = "auto"
    # Desktop-audio source: "auto" -> first `.monitor` source found via
    # `pactl list short sources` ("" when none is found). Set an explicit
    # `.monitor` device name when auto-detection picks the wrong sink.
    audio_desktop_source: str = "auto"
    audio_bitrate_kbps: int = 128  # AAC audio bitrate
    # Software audio gain (multiplier): 1.0 = 100% (no change).
    # Monitor sources (system sound) are much quieter than mic input,
    # so raise it, e.g. 2.0 (~+6 dB) or 3.0 (~+9.5 dB). Stay at or
    # below 5.0 (clipping/distortion risk).
    audio_gain: float = 1.0
    # Quality preset: "draft" (light/fast), "balanced" (default),
    # "high" (heavy). fps affects X11 capture, bitrate affects both backends.
    quality_preset: str = "balanced"

    def __post_init__(self) -> None:
        self.language = normalize(self.language)
        self.audio_mode = normalize_audio_mode(self.audio_mode)

    def apply_quality_preset(self, name: str) -> None:
        presets = {
            "draft": {"fps": 24, "video_bitrate_kbps": 4000},
            "balanced": {"fps": 30, "video_bitrate_kbps": 8000},
            "high": {"fps": 60, "video_bitrate_kbps": 16000},
        }
        if name not in presets:
            raise ValueError(f"unknown quality preset: {name}")
        self.quality_preset = name
        self.fps = presets[name]["fps"]
        self.video_bitrate_kbps = presets[name]["video_bitrate_kbps"]
    # Source selection: "fullscreen" (monitor), "window" (window),
    # "ask" (ask the user each time).
    # Wayland: translated to the portal SelectSources `types` bitmask
    # (1=monitor, 2=window, 3=both; opens the system dialog).
    # X11: "window" needs window_id, "ask" opens mouse region selection
    # (ffmpeg -select_region).
    capture_mode: str = "fullscreen"
    region_x: int = 0  # X11 fixed region top-left corner (0 = fullscreen)
    region_y: int = 0
    region_w: int = 0  # 0 = fullscreen width
    region_h: int = 0
    window_id: int = 0  # X11: non-zero value captures a single window

    def source_types(self) -> int:
        """Portal SelectSources `types` bitmask."""
        if self.capture_mode == "window":
            return 2
        if self.capture_mode == "ask":
            return 3  # 1 | 2: monitor or window
        return 1  # fullscreen default

    def next_output_path(self, suffix: str = ".mp4") -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return self.output_dir / f"castmane_{stamp}{suffix}"

    def tmp_path_for(self, final: Path) -> Path:
        """Same-folder .part file: a leftover part signals an interrupted
        recording; on clean stop it is atomically renamed to the final."""
        return final.with_suffix(final.suffix + ".part")
