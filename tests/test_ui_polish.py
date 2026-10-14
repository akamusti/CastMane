"""UI polish: distinct disk label, low-disk highlight, flexible transport."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QSizePolicy

from castmane.app import MainWindow
from castmane.config import AppConfig
from castmane.i18n import STRINGS, SUPPORTED_LANGUAGES


def _window():
    app = QApplication.instance() or QApplication([])
    os.environ["CASTMANE_NO_RECOVERY"] = "1"
    return MainWindow(AppConfig())


def test_i18n_keys_still_in_sync():
    assert set(STRINGS["en"]) == set(STRINGS["tr"])
    for lang in SUPPORTED_LANGUAGES:
        assert STRINGS[lang]["label_disk"]


def test_disk_label_is_distinct_from_output_folder():
    w = _window()
    assert w.lbl_disk.text() == w.t("label_disk")
    assert w.lbl_disk.text() != w.lbl_output_folder.text()


def test_low_disk_sets_error_property():
    w = _window()
    w.cfg.output_dir_free_mb = lambda: 12.0
    w._refresh_disk_label()
    assert w.disk_value.property("error") is True
    w.cfg.output_dir_free_mb = lambda: 5000.0
    w._refresh_disk_label()
    assert w.disk_value.property("error") is False


def test_transport_buttons_can_grow_for_long_labels():
    w = _window()
    assert w.pause_btn.minimumWidth() >= 118
    assert w.replay_btn.minimumWidth() >= 132
    assert w.pause_btn.sizePolicy().horizontalPolicy() != QSizePolicy.Fixed
    assert w.replay_btn.sizePolicy().horizontalPolicy() != QSizePolicy.Fixed
