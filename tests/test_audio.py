"""Audio source selection: mic / desktop / both, on both backends."""
from pathlib import Path

from castmane.audio import (
    detect_monitor_source,
    normalize_audio_mode,
    resolve_desktop_source,
    resolve_mic_source,
)
from castmane.config import AppConfig


def test_normalize_audio_mode():
    assert normalize_audio_mode("mic") == "mic"
    assert normalize_audio_mode("desktop") == "desktop"
    assert normalize_audio_mode("both") == "both"
    assert normalize_audio_mode("bogus") == "mic"
    assert normalize_audio_mode("") == "mic"


def test_config_clamps_audio_mode():
    assert AppConfig(audio_mode="both").audio_mode == "both"
    assert AppConfig(audio_mode="nonsense").audio_mode == "mic"


def test_resolve_mic_source():
    for alias in ("", "auto", "default", "mic", " MIC "):
        assert resolve_mic_source(alias) == "default"
    assert resolve_mic_source("alsa_input.usb-mic") == "alsa_input.usb-mic"


def test_detect_monitor_source():
    sources = [
        "alsa_output.pci.stereo.analog-stereo.monitor",
        "alsa_input.pci.mic.analog-stereo",
    ]
    assert (
        detect_monitor_source(sources)
        == "alsa_output.pci.stereo.analog-stereo.monitor"
    )
    assert detect_monitor_source(["alsa_input.pci.mic"]) == ""
    assert detect_monitor_source([]) == ""


def _x11_cmd(**kw):
    kw.setdefault("audio_enabled", True)
    rec = __import__("castmane.recorder", fromlist=["FfmpegX11Recorder"]).FfmpegX11Recorder(
        AppConfig(**kw)
    )
    return rec.build_cmd(Path("/tmp/out.mp4.part"))


def test_x11_mic_single_input():
    cmd = _x11_cmd(audio_mode="mic")
    # x11grab + one pulse input + the explicit output muxer for `.part`
    assert cmd.count("-f") == 3
    assert "default" in cmd
    assert "-filter_complex" not in cmd


def test_x11_desktop_single_input():
    cmd = _x11_cmd(audio_mode="desktop", audio_desktop_source="mysink.monitor")
    pulse_inputs = [c for i, c in enumerate(cmd) if cmd[i - 1] == "-i" and cmd[i - 2] == "pulse"]
    assert pulse_inputs == ["mysink.monitor"]
    assert "-filter_complex" not in cmd


def test_x11_both_mixes_two_inputs():
    cmd = _x11_cmd(audio_mode="both", audio_desktop_source="mysink.monitor")
    assert "-filter_complex" in cmd
    filt = cmd[cmd.index("-filter_complex") + 1]
    assert "amix=inputs=2" in filt
    assert "[aout]" in filt
    assert "-map" in cmd


def test_x11_gain_kept_in_both_mode():
    cmd = _x11_cmd(audio_mode="both", audio_gain=2.0)
    filt = cmd[cmd.index("-filter_complex") + 1]
    assert "volume=2.0" in filt


def _portal_cmd(**kw):
    from castmane.backends.portal import PortalRecorder

    kw.setdefault("audio_enabled", True)
    rec = PortalRecorder(AppConfig(**kw))
    return rec.build_cmd(42, 9, Path("/tmp/out.mkv.part"))


def test_portal_mic_single_branch():
    cmd = _portal_cmd(audio_mode="mic")
    assert cmd.count("pulsesrc") == 1
    assert "audiomixer" not in cmd
    assert "avenc_aac" in cmd


def test_portal_desktop_uses_monitor_device():
    cmd = _portal_cmd(audio_mode="desktop", audio_desktop_source="mysink.monitor")
    assert cmd.count("pulsesrc") == 1
    assert "device=mysink.monitor" in cmd
    assert "audiomixer" not in cmd


def test_portal_both_has_two_branches_and_mixer():
    cmd = _portal_cmd(audio_mode="both", audio_desktop_source="mysink.monitor")
    assert cmd.count("pulsesrc") == 2
    assert "audiomixer" in cmd
    assert cmd.count("mix.") == 2  # both branches feed the mixer
    assert "device=mysink.monitor" in cmd
    # single shared encoder downstream of the mixer
    assert cmd.count("avenc_aac") == 1


def test_portal_audio_off_unchanged():
    from castmane.backends.portal import PortalRecorder

    rec = PortalRecorder(AppConfig(audio_enabled=False))
    cmd = rec.build_cmd(42, 9, Path("/tmp/out.mkv.part"))
    assert "pulsesrc" not in cmd
    assert "audiomixer" not in cmd


def test_resolve_desktop_auto_without_pactl(monkeypatch):
    import castmane.audio as a

    monkeypatch.setattr(a, "list_pulse_sources", lambda: [])
    assert resolve_desktop_source("auto") == ""
    assert resolve_desktop_source("explicit.monitor") == "explicit.monitor"
