"""Settings page backing: themes, translations, config persistence."""
from castmane import theme as theme_mod
from castmane.config import AppConfig
from castmane.i18n import STRINGS, SUPPORTED_LANGUAGES


def test_normalize_theme():
    for name in theme_mod.SUPPORTED_THEMES:
        assert theme_mod.normalize_theme(name) == name
        assert theme_mod.normalize_theme(f"  {name.upper()}  ") == name
    assert theme_mod.normalize_theme("bogus") == theme_mod.DEFAULT_THEME
    assert theme_mod.normalize_theme("") == theme_mod.DEFAULT_THEME


def test_themes_share_key_sets():
    themes = {name: theme_mod.get_theme(name) for name in theme_mod.SUPPORTED_THEMES}
    first = next(iter(themes.values()))
    for name, table in themes.items():
        assert set(table) == set(first), name
    # Every colour the stylesheet/paint code needs must exist.
    for key in (
        "CANVAS", "SURFACE", "SURFACE_SUNKEN", "HAIRLINE", "HAIRLINE_STRONG",
        "TEXT_MAIN", "TEXT_SOFT", "TEXT_MUTED", "TEXT_FAINT",
        "INK", "INK_HOVER", "INK_PRESSED", "PRIMARY_TEXT",
        "BTN_BG", "BTN_BORDER", "BTN_HOVER", "BTN_PRESSED",
        "BTN_DISABLED_BG", "BTN_DISABLED_TEXT",
        "REC", "REC_HOVER", "REC_PRESSED",
        "READY", "PAUSED",
        "SWITCH_KNOB_OFF", "SWITCH_KNOB_ON",
    ):
        for name, table in themes.items():
            assert table[key].startswith("#"), f"{name}:{key}"


def test_get_theme_returns_copies():
    theme_mod.get_theme("dark")["CANVAS"] = "mutated"
    assert theme_mod.get_theme("dark")["CANVAS"] != "mutated"


def test_config_clamps_theme():
    assert AppConfig(theme="dark").theme == "dark"
    assert AppConfig(theme="nonsense").theme == theme_mod.DEFAULT_THEME


def test_config_save_load_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    cfg = AppConfig(language="tr", theme="dark", audio_enabled=True,
                    audio_gain=2.5, region_w=1280)
    cfg.apply_quality_preset("high")
    cfg.save(path)
    back = AppConfig.load(path)
    assert back.language == "tr"
    assert back.theme == "dark"
    assert back.audio_enabled is True
    assert back.audio_gain == 2.5
    assert back.region_w == 1280
    assert back.quality_preset == "high"
    assert back.fps == 30 + 30  # high preset re-applied, not defaults
    assert back.video_bitrate_kbps == 16000


def test_config_load_missing_or_corrupt(tmp_path):
    assert AppConfig.load(tmp_path / "nope.json").theme == theme_mod.DEFAULT_THEME
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert AppConfig.load(bad).language == "en"


def test_settings_strings_translated():
    theme_keys = ["label_theme", "theme_hint"] + [
        f"theme_{name}" for name in theme_mod.SUPPORTED_THEMES
    ]
    for key in (
        "tab_settings", "label_language", "language_hint",
        *theme_keys,
    ):
        for lang in SUPPORTED_LANGUAGES:
            assert STRINGS[lang].get(key), f"{key} missing in {lang}"
