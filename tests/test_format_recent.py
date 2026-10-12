"""Output format, custom quality preset, recent-recordings list."""
import time

from castmane.config import AppConfig, normalize_format
from castmane.i18n import STRINGS
from castmane.recorder import list_recent_recordings


def test_format_strings_translated():
    for key in (
        "quality_custom", "quality_custom_hint", "label_fps",
        "label_bitrate", "label_format", "format_hint",
        "label_recent", "recent_empty", "recent_open", "recent_refresh",
    ):
        assert STRINGS["en"].get(key), f"{key} missing in en"
        assert STRINGS["tr"].get(key), f"{key} missing in tr"


def test_normalize_format():
    assert normalize_format("mkv") == "mkv"
    assert normalize_format(" MKV ") == "mkv"
    assert normalize_format("avi") == "mp4"
    assert normalize_format("") == "mp4"


def test_next_output_path_uses_format(tmp_path):
    cfg = AppConfig(output_dir=tmp_path, output_format="mkv")
    assert cfg.next_output_path().suffix == ".mkv"
    assert AppConfig(output_dir=tmp_path).next_output_path().suffix == ".mp4"


def test_custom_preset_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    cfg = AppConfig(fps=48, video_bitrate_kbps=12000)
    cfg.apply_quality_preset("custom")
    cfg.save(path)
    back = AppConfig.load(path)
    assert back.quality_preset == "custom"
    assert back.fps == 48
    assert back.video_bitrate_kbps == 12000


def test_named_preset_overrides_stored_fps(tmp_path):
    path = tmp_path / "settings.json"
    cfg = AppConfig()
    cfg.apply_quality_preset("high")
    cfg.save(path)
    back = AppConfig.load(path)
    assert (back.fps, back.video_bitrate_kbps) == (60, 16000)


def test_list_recent_recordings(tmp_path):
    assert list_recent_recordings(tmp_path / "missing") == []
    old = tmp_path / "a.mp4"
    new = tmp_path / "b.mkv"
    old.write_bytes(b"x" * 100)
    time.sleep(0.02)
    new.write_bytes(b"y" * 100)
    (tmp_path / "junk.mp4.part").write_bytes(b"z" * 100)
    (tmp_path / "note.txt").write_text("hi")
    found = list_recent_recordings(tmp_path)
    assert [p.name for p in found] == ["b.mkv", "a.mp4"]
    assert list_recent_recordings(tmp_path, limit=1) == [new]


def test_build_cmd_mkv_has_no_movflags(tmp_path):
    from castmane.recorder import FfmpegX11Recorder

    rec = FfmpegX11Recorder(AppConfig(output_dir=tmp_path, output_format="mkv"))
    cmd = rec.build_cmd(tmp_path / "take.mkv.part")
    assert "-movflags" not in cmd
    assert str(tmp_path / "take.mkv.part") in cmd
    rec_mp4 = FfmpegX11Recorder(AppConfig(output_dir=tmp_path))
    assert "-movflags" in rec_mp4.build_cmd(tmp_path / "take.mp4.part")


def test_open_button_works_without_explicit_selection(tmp_path, monkeypatch):
    """Regression: Aç/Open did nothing when no row was selected."""
    import os

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QApplication

    from castmane.app import MainWindow
    from castmane.config import AppConfig

    (tmp_path / "take.mp4").write_bytes(b"x" * 100)
    app = QApplication.instance() or QApplication([])
    assert app is not None
    opened: list = []
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda url: opened.append(url) or True
    )
    w = MainWindow(AppConfig(output_dir=tmp_path))
    w._refresh_recent()
    w.recent_list.clearSelection()
    w.recent_list.setCurrentRow(-1)
    w._open_selected_recording()  # must fall back to the newest file
    assert opened and opened[0].toLocalFile().endswith("take.mp4")
    w.close()


def test_open_missing_file_shows_error(tmp_path, monkeypatch):
    """A deleted recording reports failure instead of dying silently."""
    import os

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QApplication

    from castmane.app import MainWindow
    from castmane.config import AppConfig

    gone = tmp_path / "gone.mp4"
    gone.write_bytes(b"x")
    app = QApplication.instance() or QApplication([])
    assert app is not None
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: True)
    w = MainWindow(AppConfig(output_dir=tmp_path))
    w._refresh_recent()
    gone.unlink()
    w._open_selected_recording()
    assert "gone.mp4" in w.status_lbl.text()
    w.close()


def test_format_file_size():
    from castmane.recorder import format_file_size

    assert format_file_size(100) == "0 KB"
    assert format_file_size(1024 * 800) == "800 KB"
    assert format_file_size(int(12.4 * 1024 * 1024)) == "12.4 MB"
