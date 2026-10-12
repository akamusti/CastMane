"""Tray icon: symbolic white, transparent background (Discord-style)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")


def test_tray_icon_is_white_on_transparent():
    from PySide6.QtWidgets import QApplication

    from castmane.icons import tray_icon, tray_pixmap

    app = QApplication.instance() or QApplication([])
    assert app is not None
    pix = tray_pixmap(64, "#FFFFFF")
    assert not pix.isNull()
    img = pix.toImage()
    white = 0
    nonwhite = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 10:
                continue
            if c.red() > 240 and c.green() > 240 and c.blue() > 240:
                white += 1
            else:
                nonwhite += 1
    assert white > 500, "tray pixmap should have visible white glyph"
    assert nonwhite == 0, "tray pixmap must be pure white on transparent"
    assert not tray_icon().isNull()
