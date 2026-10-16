"""OBS-style studio: camera discovery, PiP embed commands, sources panel."""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from castmane.camera import (
    list_cameras,
    normalize_camera_device,
    resolve_camera_device,
)
from castmane.config import AppConfig
from castmane.i18n import STRINGS, SUPPORTED_LANGUAGES


def test_camera_helpers_never_raise():
    assert isinstance(list_cameras(), list)
    assert normalize_camera_device("auto") == "auto"
    assert normalize_camera_device("") == "auto"
    assert normalize_camera_device("bogus") == "auto"
    assert normalize_camera_device("/dev/video0") == "/dev/video0"
    resolved = resolve_camera_device("auto")
    assert isinstance(resolved, str)
    assert resolve_camera_device("/dev/video3") == "/dev/video3"


def test_config_camera_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    cfg = AppConfig(camera_enabled=True, camera_embed=False,
                    camera_device="/dev/video0")
    cfg.save(p)
    back = AppConfig.load(p)
    assert back.camera_enabled is True
    assert back.camera_embed is False
    assert back.camera_device == "/dev/video0"
    # Old settings files default to camera off.
    assert AppConfig.from_dict({}).camera_enabled is False


def _x11_cmd(**kw):
    from castmane.recorder import FfmpegX11Recorder

    return FfmpegX11Recorder(AppConfig(**kw)).build_cmd(Path("/tmp/o.mp4.part"))


def test_x11_camera_embed_adds_overlay():
    cmd = _x11_cmd(camera_enabled=True, camera_embed=True,
                   camera_device="/dev/video0")
    assert "-f" in cmd and "v4l2" in cmd
    assert "/dev/video0" in cmd
    filt = cmd[cmd.index("-filter_complex") + 1]
    assert "overlay=W-w-10:H-h-10" in filt
    assert "-map" in cmd


def test_x11_camera_preview_only_adds_no_input():
    cmd = _x11_cmd(camera_enabled=True, camera_embed=False,
                   camera_device="/dev/video0")
    assert "v4l2" not in cmd
    assert "-filter_complex" not in cmd


def test_x11_camera_off_adds_nothing():
    cmd = _x11_cmd()
    assert "v4l2" not in cmd
    assert "overlay" not in " ".join(cmd)


def test_x11_camera_with_audio_both_composes():
    cmd = _x11_cmd(camera_enabled=True, camera_embed=True,
                   camera_device="/dev/video0",
                   audio_enabled=True, audio_mode="both",
                   audio_desktop_source="s.monitor")
    filt = cmd[cmd.index("-filter_complex") + 1]
    assert "overlay=" in filt and "amix=inputs=2" in filt
    # Camera occupies input 1, so audio moves to 2:a / 3:a.
    assert "[2:a]" in filt and "[3:a]" in filt


def _portal_cmd(**kw):
    from castmane.backends.portal import PortalRecorder

    return PortalRecorder(AppConfig(**kw)).build_cmd(
        42, 9, Path("/tmp/o.mkv.part"))


def test_portal_camera_adds_compositor_branch():
    cmd = _portal_cmd(camera_enabled=True, camera_embed=True,
                      camera_device="/dev/video0")
    assert "v4l2src" in cmd
    assert "device=/dev/video0" in cmd
    assert "compositor" in cmd
    assert "comp.sink_1::xpos=16" in cmd


def test_portal_no_camera_unchanged():
    cmd = _portal_cmd()
    assert "v4l2src" not in cmd
    assert "compositor" not in cmd


def test_studio_i18n_keys_match():
    assert set(STRINGS["en"]) == set(STRINGS["tr"])
    for key in ("tab_studio", "studio_preview", "sources_title",
                "source_camera", "card_camera", "card_controls",
                "label_camera_device", "label_camera_embed",
                "preview_live", "preview_idle"):
        for lang in SUPPORTED_LANGUAGES:
            assert STRINGS[lang].get(key), f"{key} missing in {lang}"


def _window(**kw):
    _ = QApplication.instance() or QApplication([])
    os.environ["CASTMANE_NO_RECOVERY"] = "1"
    return MainWindow(AppConfig(**kw))


from castmane.app import MainWindow  # noqa: E402


def test_studio_page_layout():
    w = _window()
    assert w.pages.count() == 6
    assert [b.text() for b in w.tab_buttons][0] == w.t("tab_studio")
    assert w.sources_list.count() == 4
    keys = [w.sources_list.item(r).data(Qt.UserRole)
            for r in range(w.sources_list.count())]
    assert keys == ["display", "camera", "mic", "desktop"]
    assert w.preview_badge.text() == w.t("pill_ready")
    assert w.studio_record_btn.text() == w.t("rec_start")


def test_sources_camera_toggle_updates_config():
    w = _window()
    cam_item = w._source_item("camera")
    assert cam_item is not None
    cam_item.setCheckState(Qt.Checked)
    assert w.cfg.camera_enabled is True
    assert w.camera_sw.isChecked() is True
    cam_item.setCheckState(Qt.Unchecked)
    assert w.cfg.camera_enabled is False


def test_sources_audio_toggles_update_mode():
    w = _window()
    mic = w._source_item("mic")
    desk = w._source_item("desktop")
    mic.setCheckState(Qt.Checked)
    desk.setCheckState(Qt.Checked)
    assert w.cfg.audio_enabled is True and w.cfg.audio_mode == "both"
    mic.setCheckState(Qt.Unchecked)
    desk.setCheckState(Qt.Unchecked)
    assert w.cfg.audio_enabled is False


def test_studio_inputs_locked_while_recording():
    w = _window()
    w._set_inputs_enabled(False)
    assert w.sources_list.isEnabled() is False
    assert w.camera_sw.isEnabled() is False
    assert w.camera_combo.isEnabled() is False
    assert w.camera_embed_sw.isEnabled() is False
    w._set_inputs_enabled(True)
    assert w.sources_list.isEnabled() is True
    assert w.camera_combo.isEnabled() is True
