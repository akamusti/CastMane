"""Output settings, countdown/auto-stop, and cursor capture."""
from pathlib import Path

from castmane.config import (
    AppConfig,
    normalize_auto_stop,
    normalize_countdown,
    sanitize_prefix,
)
from castmane.i18n import STRINGS, SUPPORTED_LANGUAGES
from castmane.recorder import FfmpegX11Recorder


def test_sanitize_prefix():
    assert sanitize_prefix("castmane") == "castmane"
    assert sanitize_prefix("my video!") == "my_video"
    assert sanitize_prefix("  ") == "castmane"
    assert sanitize_prefix("") == "castmane"
    assert len(sanitize_prefix("a" * 100)) <= 32


def test_normalize_countdown():
    assert normalize_countdown(0) == 0
    assert normalize_countdown(3) == 3
    assert normalize_countdown(5) == 5
    assert normalize_countdown(10) == 10
    assert normalize_countdown(7) == 0
    assert normalize_countdown("bogus") == 0


def test_normalize_auto_stop():
    assert normalize_auto_stop(0) == 0
    assert normalize_auto_stop(30) == 30
    assert normalize_auto_stop(999) == 180
    assert normalize_auto_stop(-5) == 0


def test_next_output_path_uses_prefix(tmp_path):
    cfg = AppConfig(output_dir=tmp_path, filename_prefix="demo!")
    out = cfg.next_output_path(".mp4")
    assert out.parent == tmp_path
    assert out.name.startswith("demo_")
    assert out.suffix == ".mp4"


def test_output_dir_free_mb(tmp_path):
    cfg = AppConfig(output_dir=tmp_path)
    free = cfg.output_dir_free_mb()
    assert free is None or free > 0


def test_config_roundtrip_new_fields(tmp_path):
    path = tmp_path / "settings.json"
    cfg = AppConfig(
        filename_prefix="my-show", show_cursor=False,
        countdown_s=5, auto_stop_min=15,
    )
    cfg.save(path)
    back = AppConfig.load(path)
    assert back.filename_prefix == "my-show"
    assert back.show_cursor is False
    assert back.countdown_s == 5
    assert back.auto_stop_min == 15


def test_x11_cursor_flag(tmp_path):
    cfg = AppConfig(output_dir=tmp_path, show_cursor=True)
    cmd = FfmpegX11Recorder(cfg).build_cmd(tmp_path / "x.mp4.part")
    assert "-draw_mouse" in cmd
    assert cmd[cmd.index("-draw_mouse") + 1] == "1"
    cfg.show_cursor = False
    cmd = FfmpegX11Recorder(cfg).build_cmd(tmp_path / "x.mp4.part")
    assert cmd[cmd.index("-draw_mouse") + 1] == "0"


def test_new_strings_translated():
    for key in (
        "tab_output", "label_cursor", "cursor_hint", "label_countdown",
        "countdown_hint", "countdown_off", "countdown_status",
        "label_autostop", "autostop_hint", "autostop_minutes",
        "label_output_folder", "output_browse", "output_hint",
        "label_prefix", "prefix_hint", "disk_free", "disk_low",
        "disk_unknown", "invalid_output",
    ):
        for lang in SUPPORTED_LANGUAGES:
            assert STRINGS[lang].get(key), f"{key} missing in {lang}"


def test_old_prefix_style_still_loads(tmp_path):
    # Settings files written before this feature have no new keys.
    path = tmp_path / "old.json"
    path.write_text('{"output_dir": "/tmp", "language": "tr"}', encoding="utf-8")
    cfg = AppConfig.load(path)
    assert cfg.filename_prefix == "castmane"
    assert cfg.show_cursor is True
    assert cfg.countdown_s == 0
    assert cfg.auto_stop_min == 0
    assert Path(cfg.output_dir) == Path("/tmp")
