"""UI translations. English is the default; Turkish is opt-in at runtime."""
from __future__ import annotations

SUPPORTED_LANGUAGES = ("en", "tr")
DEFAULT_LANGUAGE = "en"

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "subtitle": "Crash-safe screen recorder",
        "status_ready": "Ready — {backend}",
        "status_x11": "X11 detected: ffmpeg backend active. "
        "The portal backend kicks in on a Wayland session.",
        "rec_start": "Start Recording",
        "rec_stop": "Stop Recording",
        "pill_ready": "READY",
        "pill_recording": "REC",
        "pill_paused": "PAUSED",
        "tab_capture": "Capture",
        "tab_audio": "Audio",
        "tab_region": "Region",
        "label_source": "Source",
        "label_quality": "Quality",
        "mode_fullscreen": "Fullscreen",
        "mode_window": "Window",
        "mode_ask": "Ask",
        "mode_fullscreen_hint": "Capture the whole monitor.",
        "mode_window_hint": "Capture a single window.",
        "mode_ask_hint": "Let the portal ask each time.",
        "quality_draft": "Draft",
        "quality_balanced": "Balanced",
        "quality_high": "High",
        "quality_draft_hint": "24 fps · 4 Mbps — light on CPU.",
        "quality_balanced_hint": "30 fps · 8 Mbps — the default.",
        "quality_high_hint": "60 fps · 16 Mbps — needs a fast CPU.",
        "audio_check": "Record audio",
        "audio_mode": "Audio source",
        "audio_mode_mic": "Mic",
        "audio_mode_desktop": "Desktop",
        "audio_mode_both": "Both",
        "audio_mode_mic_hint": "Record the microphone via the default source.",
        "audio_mode_desktop_hint": "Record system sound via a .monitor device.",
        "audio_mode_both_hint": "Mix microphone and system sound into one track.",
        "audio_hint": "Mic uses the PulseAudio default source. Desktop uses the "
        "auto-detected .monitor device — or paste one explicitly "
        "(`pactl list short sources`).",
        "label_source_name": "Microphone source",
        "label_desktop_source": "Desktop source",
        "label_gain": "Gain",
        "gain_value": "{pct}%",
        "label_region": "Capture region",
        "region_hint": "Used on X11 only. Leave every field at 0 for "
        "fullscreen capture.",
        "label_output": "Output folder",
        "outcome": "Timestamped files land in ~/Videos/CastMane",
        "pause": "Pause",
        "resume": "Resume",
        "backend_line": "Backend: {name}",
        "open_folder": "Open output folder",
        "recording_to": "Recording → {name}",
        "paused_status": "Paused — timer stopped",
        "saved": "Saved: {out}",
        "error_prefix": "Error: {err}",
        "start_failed": "Could not start: {err}",
        "deps_missing": "ffmpeg/gst-launch not found!",
        "pause_error": "Pause error: {err}",
    },
    "tr": {
        "subtitle": "Çökmeye dayanıklı ekran kaydedici",
        "status_ready": "Hazır — {backend}",
        "status_x11": "X11 algılandı: ffmpeg backend aktif. "
        "Wayland oturumunda portal backend devreye girer.",
        "rec_start": "Kayda Başla",
        "rec_stop": "Kaydı Durdur",
        "pill_ready": "HAZIR",
        "pill_recording": "KAYIT",
        "pill_paused": "DURAKLATILDI",
        "tab_capture": "Kayıt",
        "tab_audio": "Ses",
        "tab_region": "Bölge",
        "label_source": "Kaynak",
        "label_quality": "Kalite",
        "mode_fullscreen": "Tam Ekran",
        "mode_window": "Pencere",
        "mode_ask": "Sor",
        "mode_fullscreen_hint": "Tüm ekranı yakalar.",
        "mode_window_hint": "Tek bir pencereyi yakalar.",
        "mode_ask_hint": "Her seferinde portal sorar.",
        "quality_draft": "Taslak",
        "quality_balanced": "Dengeli",
        "quality_high": "Yüksek",
        "quality_draft_hint": "24 fps · 4 Mbps — CPU dostu.",
        "quality_balanced_hint": "30 fps · 8 Mbps — varsayılan.",
        "quality_high_hint": "60 fps · 16 Mbps — hızlı CPU ister.",
        "audio_check": "Sesi kaydet",
        "audio_mode": "Ses kaynağı",
        "audio_mode_mic": "Mikrofon",
        "audio_mode_desktop": "Masaüstü",
        "audio_mode_both": "İkisi",
        "audio_mode_mic_hint": "Mikrofonu varsayılan kaynaktan kaydet.",
        "audio_mode_desktop_hint": "Sistem sesini bir .monitor cihazından kaydet.",
        "audio_mode_both_hint": "Mikrofon ve sistem sesini tek parçada birleştir.",
        "audio_hint": "Mikrofon PulseAudio varsayılan kaynağını kullanır. Masaüstü "
        "otomatik bulunan .monitor cihazını kullanır — ya da açıkça yapıştır "
        "(`pactl list short sources`).",
        "label_source_name": "Mikrofon kaynağı",
        "label_desktop_source": "Masaüstü kaynağı",
        "label_gain": "Kazanç",
        "gain_value": "%{pct}",
        "label_region": "Yakalama bölgesi",
        "region_hint": "Yalnızca X11'de kullanılır. Tam ekran için "
        "tüm alanları 0 bırak.",
        "label_output": "Çıktı klasörü",
        "outcome": "Zaman damgalı dosyalar ~/Videos/CastMane içine düşer",
        "pause": "Duraklat",
        "resume": "Sürdür",
        "backend_line": "Backend: {name}",
        "open_folder": "Çıktı klasörünü aç",
        "recording_to": "Kaydediliyor → {name}",
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
