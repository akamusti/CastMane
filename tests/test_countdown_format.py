"""Regression: countdown timer renders HH:MM:SS for all choices (issue #2)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from castmane.app import MainWindow
from castmane.config import COUNTDOWN_CHOICES, AppConfig


def _window(countdown_s: int):
    _ = QApplication.instance() or QApplication([])
    os.environ["CASTMANE_NO_RECOVERY"] = "1"
    cfg = AppConfig(countdown_s=countdown_s)
    return MainWindow(cfg)


def test_countdown_formats_all_choices():
    assert 10 in COUNTDOWN_CHOICES  # the value that used to render "0:00:010"
    for n in COUNTDOWN_CHOICES:
        if n == 0:
            continue
        assert MainWindow._fmt_elapsed(n) == f"00:00:{n:02d}"


def test_toggle_shows_correct_countdown_label():
    w = _window(10)
    w.cfg.countdown_s = 10
    w.toggle()  # starts countdown, does not start recording
    try:
        assert w.timer_lbl.text() == "00:00:10"
        assert w._countdown_timer.isActive()
        w._countdown_tick()  # 10 -> 9
        assert w.timer_lbl.text() == "00:00:09"
    finally:
        w._countdown_timer.stop()
