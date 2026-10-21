"""OBS-style studio: camera discovery, PiP placement, sources panel."""
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from castmane.camera import (
    camera_overlay_rect,
    clamp_camera_position,
    clamp_camera_scale,
    list_cameras,
    normalize_camera_device,
    resolve_camera_device,
)
from castmane.config import AppConfig
from castmane.i18n import STRINGS, SUPPORTED_LANGUAGES
from castmane.preview import camera_rect_for, fit_aspect, position_from_rect


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
                    camera_device="/dev/video0",
                    camera_pos_x=0.25, camera_pos_y=0.75,
                    camera_scale=0.33)
    cfg.save(p)
    back = AppConfig.load(p)
    assert back.camera_enabled is True
    assert back.camera_embed is False
    assert back.camera_device == "/dev/video0"
    assert back.camera_pos_x == 0.25
    assert back.camera_pos_y == 0.75
    assert back.camera_scale == 0.33
    # Old settings files default to camera off and a bottom-right PiP.
    old = AppConfig.from_dict({})
    assert old.camera_enabled is False
    assert old.camera_pos_x == 0.72
    assert old.camera_scale == 0.22


def test_camera_placement_clamps():
    assert clamp_camera_position(-3) == 0.0
    assert clamp_camera_position(9) == 1.0
    assert clamp_camera_position("bogus") == 0.0
    assert clamp_camera_scale(0) == 0.10
    assert clamp_camera_scale(9) == 0.45
    assert clamp_camera_scale("bogus") == 0.22


def test_camera_overlay_rect_corners():
    x, y, w, h = camera_overlay_rect(0.0, 0.0, 0.25, 1920, 1080)
    assert (x, y) == (0, 0)
    assert (w, h) == (480, 360)  # 4:3, even
    br_x, br_y, _, _ = camera_overlay_rect(1.0, 1.0, 0.25, 1920, 1080)
    assert (br_x, br_y) == (1920 - w, 1080 - h)


def test_camera_overlay_rect_uses_camera_aspect():
    _, _, w, h = camera_overlay_rect(0.5, 0.5, 0.20, 1000, 500,
                                     cam_w=160, cam_h=90)
    assert (w, h) == (200, 112)  # 16:9 camera, even height for yuv420
    _, _, w2, h2 = camera_overlay_rect(0.5, 0.5, 0.25, 1920, 1080,
                                       cam_aspect=16 / 9)
    assert (w2, h2) == (480, 270)


def test_preview_geometry_helpers_roundtrip():
    content = fit_aspect(QRectF(0, 0, 800, 800), 16 / 9)
    rect = camera_rect_for(content, 0.3, 0.7, 0.2)
    px, py = position_from_rect(content, rect)
    assert abs(px - 0.3) < 1e-9
    assert abs(py - 0.7) < 1e-9
    assert content.width() == 800
    assert rect.width() == content.width() * 0.2


def _x11_cmd(**kw):
    from castmane.recorder import FfmpegX11Recorder

    return FfmpegX11Recorder(AppConfig(**kw)).build_cmd(Path("/tmp/o.mp4.part"))


def test_x11_camera_embed_adds_overlay():
    cmd = _x11_cmd(camera_enabled=True, camera_embed=True,
                   camera_device="/dev/video0",
                   camera_pos_x=0.25, camera_pos_y=0.5,
                   camera_scale=0.30)
    assert "-f" in cmd and "v4l2" in cmd
    assert "/dev/video0" in cmd
    filt = cmd[cmd.index("-filter_complex") + 1]
    assert "scale2ref=w=main_w*0.3000:h=-2" in filt
    assert "overlay=x=(W-w)*0.2500:y=(H-h)*0.5000" in filt
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
    from castmane.backends.portal import PortalRecorder

    cfg = AppConfig(camera_enabled=True, camera_embed=True,
                    camera_device="/dev/video0",
                    camera_pos_x=1.0, camera_pos_y=1.0, camera_scale=0.20,
                    screen_w=1920, screen_h=1080)
    cmd = PortalRecorder(cfg).build_cmd(42, 9, Path("/tmp/o.mkv.part"))
    assert "v4l2src" in cmd
    assert "device=/dev/video0" in cmd
    assert "compositor" in cmd
    x, y, w, h = camera_overlay_rect(1.0, 1.0, 0.20, 1920, 1080)
    assert f"comp.sink_1::xpos={x}" in cmd
    assert f"comp.sink_1::ypos={y}" in cmd
    assert f"video/x-raw,width={w},height={h}" in cmd


def test_portal_no_camera_unchanged():
    cmd = _portal_cmd()
    assert "v4l2src" not in cmd
    assert "compositor" not in cmd


def test_studio_i18n_keys_match():
    assert set(STRINGS["en"]) == set(STRINGS["tr"])
    for key in ("tab_studio", "studio_preview", "sources_title",
                "source_camera", "card_camera", "card_controls",
                "label_camera_device", "label_camera_embed",
                "preview_live", "preview_idle", "preview_drag_hint",
                "stage_empty", "label_camera_size",
                "camera_pos_tl", "camera_pos_tr",
                "camera_pos_bl", "camera_pos_br"):
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
    assert w.record_btn.text() == w.t("rec_start")


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
    assert w.camera_size_slider.isEnabled() is False
    assert w.camera_pos_btns[0].isEnabled() is False
    assert w.preview_stage.is_interactive() is False
    w._set_inputs_enabled(True)
    assert w.sources_list.isEnabled() is True
    assert w.camera_combo.isEnabled() is True
    assert w.camera_size_slider.isEnabled() is True
    assert w.preview_stage.is_interactive() is True


def test_studio_preview_uses_new_stage():
    w = _window()
    assert w.preview_stage.camera_visible() is False
    assert w.camera_size_slider.value() == round(w.cfg.camera_scale * 100)
    assert w.camera_size_value.text().endswith("%")
    w.camera_sw.setChecked(True)
    assert w.preview_stage.camera_visible() is True


def _mouse(widget, kind, pos):
    buttons = Qt.LeftButton if kind != QEvent.MouseButtonRelease else Qt.NoButton
    global_pos = widget.mapToGlobal(QPoint(int(pos.x()), int(pos.y())))
    return QMouseEvent(
        kind,
        QPointF(pos),
        QPointF(global_pos),
        Qt.LeftButton,
        buttons,
        Qt.NoModifier,
    )


def test_stage_drag_moves_camera_and_emits_geometry():
    _ = QApplication.instance() or QApplication([])
    from castmane.preview import PreviewStage

    stage = PreviewStage()
    stage.resize(640, 360)
    stage.set_camera_visible(True)
    stage.set_position(0.4, 0.4)
    stage.set_scale(0.20)
    emitted = []
    stage.geometry_changed.connect(lambda *args: emitted.append(args))

    rect = stage.camera_rect()
    start = rect.center()
    stage.mousePressEvent(_mouse(stage, QEvent.MouseButtonPress, start))
    stage.mouseMoveEvent(
        _mouse(stage, QEvent.MouseMove, start + QPointF(40, 30))
    )
    stage.mouseReleaseEvent(
        _mouse(stage, QEvent.MouseButtonRelease, start + QPointF(40, 30))
    )

    geo = stage.geometry()
    assert geo.pos_x > 0.4 and geo.pos_y > 0.4
    assert emitted and emitted[-1][2] == geo.scale


def test_stage_corner_and_wheel_clamp():
    _ = QApplication.instance() or QApplication([])
    from castmane.preview import PreviewStage

    stage = PreviewStage()
    stage.resize(640, 360)
    stage.set_camera_visible(True)
    stage.set_corner("br")
    rect = stage.camera_rect()
    content = stage.content_rect()
    assert abs(rect.right() - content.right()) < 0.01
    assert abs(rect.bottom() - content.bottom()) < 0.01

    stage.set_scale(99)
    assert stage.geometry().scale == 0.45
    stage.set_scale(-1)
    assert stage.geometry().scale == 0.10
    stage.reset_camera()
    assert stage.geometry().scale == 0.22
