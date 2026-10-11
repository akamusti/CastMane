"""User settings + default output path."""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .audio import normalize_audio_mode
from .i18n import DEFAULT_LANGUAGE, normalize
from .theme import DEFAULT_THEME, normalize_theme

#: Where UI preferences are remembered between runs.
SETTINGS_PATH = Path.home() / ".config" / "castmane" / "settings.json"

#: Countdown choices offered in the UI (seconds). 0 = off.
COUNTDOWN_CHOICES = (0, 3, 5, 10)

#: Auto-stop limit (minutes). 0 = off, max 3 hours.
AUTO_STOP_MAX_MIN = 180

#: Abort recording start below this free space so we never write a
#: truncated file without telling the user first.
MIN_FREE_MB = 100


def sanitize_prefix(value: str) -> str:
    """Clamp a filename prefix to `[A-Za-z0-9_-]`, max 32 chars."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip())
    cleaned = cleaned.strip("_") or "castmane"
    return cleaned[:32]


def normalize_countdown(value: int) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return 0
    return ivalue if ivalue in COUNTDOWN_CHOICES else 0


def normalize_auto_stop(value: int) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(AUTO_STOP_MAX_MIN, ivalue))


@dataclass
class AppConfig:
    output_dir: Path = Path.home() / "Videos" / "CastMane"
    # UI language: "en" (default) or "tr". Switchable at runtime,
    # e.g. AppConfig(language="tr").
    language: str = DEFAULT_LANGUAGE
    # UI theme: "light" (warm paper, default), "dark", "ocean" (cool
    # light blue), "midnight" (dark navy), "forest" (dark moss),
    # "dracula" or "nord". Switchable at runtime from the Settings page,
    # e.g. AppConfig(theme="nord").
    theme: str = DEFAULT_THEME
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
    # Output naming: sanitized via sanitize_prefix() ("my video!" -> "my_video").
    filename_prefix: str = "castmane"
    # Mouse cursor in the footage (X11 draw_mouse + portal cursor_mode).
    show_cursor: bool = True
    # Countdown before recording starts (seconds, 0 = off).
    countdown_s: int = 0
    # Auto-stop after N minutes (0 = off, max 180).
    auto_stop_min: int = 0

    def __post_init__(self) -> None:
        self.language = normalize(self.language)
        self.theme = normalize_theme(self.theme)
        self.audio_mode = normalize_audio_mode(self.audio_mode)
        self.filename_prefix = sanitize_prefix(self.filename_prefix)
        self.countdown_s = normalize_countdown(self.countdown_s)
        self.auto_stop_min = normalize_auto_stop(self.auto_stop_min)

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
        return self.output_dir / f"{sanitize_prefix(self.filename_prefix)}_{stamp}{suffix}"

    def output_dir_free_mb(self) -> float | None:
        """Free space in the output folder (MiB), None when unknown."""
        try:
            target = self.output_dir
            target.mkdir(parents=True, exist_ok=True)
            return shutil.disk_usage(target).free / (1024 * 1024)
        except OSError:
            return None

    def tmp_path_for(self, final: Path) -> Path:
        """Same-folder .part file: a leftover part signals an interrupted
        recording; on clean stop it is atomically renamed to the final."""
        return final.with_suffix(final.suffix + ".part")

    # --- Persistence (Settings page choices survive restarts) ---

    def to_dict(self) -> dict:
        return {
            "output_dir": str(self.output_dir),
            "filename_prefix": self.filename_prefix,
            "show_cursor": self.show_cursor,
            "countdown_s": self.countdown_s,
            "auto_stop_min": self.auto_stop_min,
            "language": self.language,
            "theme": self.theme,
            "quality_preset": self.quality_preset,
            "capture_mode": self.capture_mode,
            "region_x": self.region_x,
            "region_y": self.region_y,
            "region_w": self.region_w,
            "region_h": self.region_h,
            "audio_enabled": self.audio_enabled,
            "audio_mode": self.audio_mode,
            "audio_source": self.audio_source,
            "audio_desktop_source": self.audio_desktop_source,
            "audio_gain": self.audio_gain,
        }

    def save(self, path: Path | None = None) -> None:
        """Write preferences to disk. Never raises: a settings write
        must not break recording or shutdown."""
        target = Path(path) if path is not None else SETTINGS_PATH
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        except OSError:
            pass

    @classmethod
    def from_dict(cls, data: dict) -> AppConfig:
        """Build a config from stored values; unknown/missing keys fall
        back to defaults so old or hand-edited files never crash."""
        if not isinstance(data, dict):
            return cls()
        try:
            cfg = cls(
                output_dir=Path(data.get("output_dir", Path.home() / "Videos" / "CastMane")),
                filename_prefix=sanitize_prefix(data.get("filename_prefix", "castmane")),
                show_cursor=bool(data.get("show_cursor", True)),
                countdown_s=normalize_countdown(data.get("countdown_s", 0)),
                auto_stop_min=normalize_auto_stop(data.get("auto_stop_min", 0)),
                language=data.get("language", DEFAULT_LANGUAGE),
                theme=data.get("theme", DEFAULT_THEME),
                capture_mode=data.get("capture_mode", "fullscreen"),
                region_x=int(data.get("region_x", 0)),
                region_y=int(data.get("region_y", 0)),
                region_w=int(data.get("region_w", 0)),
                region_h=int(data.get("region_h", 0)),
                audio_enabled=bool(data.get("audio_enabled", False)),
                audio_mode=data.get("audio_mode", "mic"),
                audio_source=data.get("audio_source", "auto"),
                audio_desktop_source=data.get("audio_desktop_source", "auto"),
                audio_gain=float(data.get("audio_gain", 1.0)),
            )
            # Re-apply the stored preset so fps/bitrate match the preset
            # instead of the dataclass defaults.
            try:
                cfg.apply_quality_preset(data.get("quality_preset", "balanced"))
            except ValueError:
                pass
            return cfg
        except (TypeError, ValueError):
            return cls()

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        """Read stored preferences; a missing or corrupt file means
        defaults, never an error."""
        target = Path(path) if path is not None else SETTINGS_PATH
        try:
            return cls.from_dict(json.loads(target.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return cls()
