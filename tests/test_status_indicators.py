"""Status indicators: tray/notification strings + pause-aware auto-stop."""
from castmane.i18n import STRINGS, SUPPORTED_LANGUAGES


def test_status_indicator_strings_translated():
    for key in (
        "tray_show", "tray_hide", "tray_record", "tray_stop",
        "tray_open_folder", "tray_quit", "tray_ready", "tray_recording",
        "tray_paused", "notify_started", "notify_stopped",
        "notify_autostop", "notify_disk_stopped", "notify_minimized",
    ):
        for lang in SUPPORTED_LANGUAGES:
            assert STRINGS[lang].get(key), f"{key} missing in {lang}"
    assert set(STRINGS["en"]) == set(STRINGS["tr"])


def test_fmt_elapsed():
    from castmane.app import MainWindow

    assert MainWindow._fmt_elapsed(0) == "00:00:00"
    assert MainWindow._fmt_elapsed(61) == "00:01:01"
    assert MainWindow._fmt_elapsed(3661) == "01:01:01"
