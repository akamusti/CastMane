"""UI translations. English is the default; Turkish is opt-in at runtime."""
from __future__ import annotations

SUPPORTED_LANGUAGES = ("en", "tr")
DEFAULT_LANGUAGE = "en"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "subtitle": "Crash-safe screen recorder",
        "status_ready": "Ready [{backend}]. Output: ~/Videos/CastMane",
        "status_x11": (
            "X11 detected: ffmpeg backend active. "
            "The portal backend kicks in on a Wayland session."
        ),
        "rec_start": "● Start Recording",
        "rec_stop": "■ Stop",
        "section_capture": "RECORDING SETTINGS",
        "label_source": "Source:",
        "label_quality": "Quality:",
        "label_language": "Language:",
        "mode_fullscreen": "Fullscreen",
        "mode_window": "Window",
        "mode_ask": "Ask / Select region",
        "quality_draft": "Draft (light)",
        "quality_balanced": "Balanced",
        "quality_high": "High",
        "section_audio": "AUDIO",
        "audio_check": "Record audio (mic)",
        "label_gain": "Gain:",
        "section_region": "REGION",
        "label_region": "Region (X11):",
        "region_hint": "Empty/0 values mean fullscreen",
        "outcome": "Files are saved with timestamps into ~/Videos/CastMane",
        "pause": "⏸ Pause",
        "resume": "▶ Resume",
        "quit": "Quit",
        "recording_to": "Recording -> {name}",
        "paused_status": "Paused — timer stopped",
        "saved": "Saved: {out}",
        "error_prefix": "Error: {err}",
        "start_failed": "Could not start: {err}",
        "deps_missing": "ffmpeg/gst-launch not found!",
        "pause_error": "Pause error: {err}",
    },
    "tr": {
        "subtitle": "Crash-safe ekran kaydedici",
        "status_ready": "Hazır [{backend}]. Çıktı: ~/Videos/CastMane",
        "status_x11": (
            "X11 algılandı: ffmpeg backend aktif. "
            "Wayland oturumunda portal backend devreye girer."
        ),
        "rec_start": "● Kayda Başla",
        "rec_stop": "■ Durdur",
        "section_capture": "KAYIT AYARLARI",
        "label_source": "Kaynak:",
        "label_quality": "Kalite:",
        "label_language": "Dil:",
        "mode_fullscreen": "Tam Ekran",
        "mode_window": "Pencere",
        "mode_ask": "Sor / Bölge Seç",
        "quality_draft": "Taslak (hafif)",
        "quality_balanced": "Dengeli",
        "quality_high": "Yüksek",
        "section_audio": "SES",
        "audio_check": "Sesli kaydet (mikrofon)",
        "label_gain": "Ses kazancı:",
        "section_region": "BÖLGE",
        "label_region": "Bölge (X11):",
        "region_hint": "Boş/0 değerler tam ekran demektir",
        "outcome": "Dosyalar ~/Videos/CastMane içine zaman damgasıyla kaydedilir",
        "pause": "⏸ Duraklat",
        "resume": "▶ Sürdür",
        "quit": "Çıkış",
        "recording_to": "Kaydediliyor -> {name}",
        "paused_status": "Duraklatıldı — süre işlemiyor",
        "saved": "Kurtarıldı: {out}",
        "error_prefix": "Hata: {err}",
        "start_failed": "Başlatılamadı: {err}",
        "deps_missing": "ffmpeg/gst-launch bulunamadı!",
        "pause_error": "Duraklatma hatası: {err}",
    },
}


def get(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Return the translated string, falling back to English."""
    table = STRINGS.get(lang, STRINGS[DEFAULT_LANGUAGE])
    return table.get(key, STRINGS[DEFAULT_LANGUAGE].get(key, key))


def normalize(lang: str) -> str:
    """Clamp any input to a supported language code."""
    lang = (lang or "").strip().lower()
    if lang in STRINGS:
        return lang
    # Accept common variants like "tr-TR", "en_US".
    short = lang.replace("_", "-").split("-")[0]
    return short if short in STRINGS else DEFAULT_LANGUAGE
