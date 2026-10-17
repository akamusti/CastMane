"""Stop/finalize must not block the Qt UI thread.

Regression for the window freeze while the encoder shut down and the
crash-safe MKV->MP4 remux ran inline on the UI thread.
"""
import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from castmane.app import MainWindow  # noqa: E402
from castmane.config import AppConfig  # noqa: E402


def _window():
    _ = QApplication.instance() or QApplication([])
    os.environ["CASTMANE_NO_RECOVERY"] = "1"
    return MainWindow(AppConfig())


class _SlowRecorder:
    """Recorder whose stop() blocks for `delay`, like a real remux does."""

    def __init__(self, delay=0.6):
        self.delay = delay
        self.state = type("S", (), {"active": True, "paused": False,
                                    "last_error": "", "tmp_path": None})()
        self.stop_calls = 0
        self.stopped_in_thread = None

    def stop(self):
        self.stop_calls += 1
        self.stopped_in_thread = threading.current_thread().name
        time.sleep(self.delay)
        self.state.active = False
        self.state.last_error = ""
        return None

    @property
    def elapsed(self):
        return 0.0

    def start(self):
        raise RuntimeError("not used")

    def pause(self):
        raise RuntimeError("not used")

    def resume(self):
        raise RuntimeError("not used")


def _drain(w, timeout=10.0):
    """Run the Qt event loop until the background worker is applied."""
    deadline = time.time() + timeout
    while w._bg_thread is not None and time.time() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    QApplication.processEvents()
    assert w._bg_thread is None, "background finalize never completed"


@pytest.fixture
def window(monkeypatch):
    w = _window()
    yield w
    w._bg_thread = None


def test_stop_returns_immediately_and_finalizes_in_background(window, monkeypatch):
    w = window
    rec = _SlowRecorder()
    monkeypatch.setattr(w, "rec", rec)

    start = time.time()
    w._stop_recording()
    elapsed = time.time() - start

    # The call must hand the work off instead of blocking on it.
    assert elapsed < rec.delay / 2, f"_stop_recording blocked for {elapsed:.2f}s"
    assert rec.stop_calls == 1
    assert w._bg_thread is not None
    assert w.status_lbl.text() == w.t("finalizing")
    # Controls stay locked while finalizing.
    assert w.record_btn.isEnabled() is False
    assert w.replay_btn.isEnabled() is False

    _drain(w)
    assert w.record_btn.isEnabled() is True
    assert w.record_btn.text() == w.t("rec_start")


def test_stop_runs_off_the_ui_thread(window, monkeypatch):
    w = window
    rec = _SlowRecorder(delay=0.4)
    monkeypatch.setattr(w, "rec", rec)

    w._stop_recording()
    ui_thread = threading.current_thread().name
    _drain(w)

    assert rec.stopped_in_thread is not None
    assert rec.stopped_in_thread != ui_thread


def test_toggle_is_ignored_while_finalizing(window, monkeypatch):
    """A second press during finalize must not start a competing recording."""
    w = window
    rec = _SlowRecorder(delay=0.5)
    monkeypatch.setattr(w, "rec", rec)
    w._stop_recording()
    assert w._bg_thread is not None

    w.toggle()
    assert rec.stop_calls == 1
    w.toggle_pause()  # must not raise

    _drain(w)


def test_stopped_result_is_applied_by_tick(window, monkeypatch):
    w = window
    rec = _SlowRecorder(delay=0.2)
    monkeypatch.setattr(w, "rec", rec)
    w._stop_recording()
    _drain(w)

    # Error path: recorder returned None with no last_error.
    assert w._bg_kind == ""
    assert w.pause_btn.isEnabled() is False
    assert w.record_btn.isEnabled() is True


def test_saved_path_is_reported_after_finalize(window, monkeypatch, tmp_path):
    w = window
    out = tmp_path / "take.mp4"
    rec = _SlowRecorder(delay=0.2)
    rec.stop = lambda: (time.sleep(0.2), setattr(rec.state, "active", False), out)[-1]
    monkeypatch.setattr(w, "rec", rec)

    w._stop_recording()
    _drain(w)

    assert w.status_lbl.text() == w.t("saved").format(out=out)
    assert w.record_btn.text() == w.t("rec_start")


def test_finalizing_string_is_translated():
    from castmane.i18n import STRINGS

    assert STRINGS["en"]["finalizing"]
    assert STRINGS["tr"]["finalizing"]
