"""Mixer (per-source gain), replay buffer helpers, shortcut normalization."""
from pathlib import Path

from castmane.audio import effective_gains
from castmane.config import (
    AppConfig,
    clamp_gain,
    normalize_replay_seconds,
    normalize_shortcut,
)


def test_clamp_gain_bounds():
    assert clamp_gain(2.0) == 2.0
    assert clamp_gain(99) == 5.0
    assert clamp_gain(-1) == 0.0
    assert clamp_gain("bogus") == 1.0


def test_effective_gains_prefers_per_source():
    cfg = AppConfig(audio_gain=1.0, mic_gain=2.0, desktop_gain=0.5)
    assert effective_gains(cfg) == (2.0, 0.5)


def test_effective_gains_legacy_fallback():
    cfg = AppConfig(audio_gain=2.0)
    # Direct constructor: new channels stay default, effective_gains falls back.
    assert effective_gains(cfg) == (2.0, 2.0)
    # from_dict carries legacy master to both channels for old files.
    back = AppConfig.from_dict({"audio_gain": 2.0})
    assert back.mic_gain == 2.0 and back.desktop_gain == 2.0


def _x11_cmd(**kw):
    from castmane.recorder import FfmpegX11Recorder

    kw.setdefault("audio_enabled", True)
    return FfmpegX11Recorder(AppConfig(**kw)).build_cmd(Path("/tmp/o.mp4.part"))


def test_x11_per_source_gain_both():
    cmd = _x11_cmd(audio_mode="both", mic_gain=2.0, desktop_gain=0.5,
                   audio_desktop_source="s.monitor")
    filt = cmd[cmd.index("-filter_complex") + 1]
    assert "volume=2.0" in filt and "volume=0.5" in filt


def test_x11_single_gain_uses_own_channel():
    cmd = _x11_cmd(audio_mode="mic", mic_gain=2.0, desktop_gain=0.5)
    assert "-filter:a" in cmd
    assert cmd[cmd.index("-filter:a") + 1] == "volume=2.0"
    cmd2 = _x11_cmd(audio_mode="desktop", mic_gain=2.0, desktop_gain=0.5,
                    audio_desktop_source="s.monitor")
    assert cmd2[cmd2.index("-filter:a") + 1] == "volume=0.5"


def test_portal_per_branch_gain():
    from castmane.backends.portal import PortalRecorder

    rec = PortalRecorder(AppConfig(audio_enabled=True, audio_mode="both",
                                   mic_gain=2.0, desktop_gain=0.5,
                                   audio_desktop_source="s.monitor"))
    cmd = rec.build_cmd(1, 9, Path("/tmp/o.mkv.part"))
    assert cmd.count("pulsesrc") == 2
    assert "volume=2.0" in cmd and "volume=0.5" in cmd


def test_replay_helpers():
    from castmane import replay as r

    assert r.segment_wrap_count(60) == 8
    assert r.segment_wrap_count(10) == 3
    segs = [Path(f"/v/.replay/replay_{i:03d}.mp4") for i in range(10)]
    picked = r.select_segments_for_save(segs, 25)
    assert picked == segs[-3:]
    cmd, text = r.build_concat_cmd(picked, Path("/v/out.mp4"))
    assert cmd[:3] == ["ffmpeg", "-y", "-f"]
    assert text.count("file '") == 3


def test_normalize_shortcut_and_replay():
    assert normalize_shortcut("  Ctrl+R  ", "R") == "Ctrl+R"
    assert normalize_shortcut("", "R") == "R"
    assert normalize_replay_seconds(5) == 10
    assert normalize_replay_seconds(10_000) == 600


def test_config_roundtrip_new_fields(tmp_path):
    p = tmp_path / "s.json"
    cfg = AppConfig(mic_gain=1.5, desktop_gain=2.5, replay_enabled=True,
                    replay_seconds=90, shortcut_replay="Ctrl+T")
    cfg.save(p)
    back = AppConfig.load(p)
    assert (back.mic_gain, back.desktop_gain) == (1.5, 2.5)
    assert back.replay_enabled is True and back.replay_seconds == 90
    assert back.shortcut_replay == "Ctrl+T"


def test_i18n_new_keys_match():
    from castmane.i18n import STRINGS

    assert set(STRINGS["en"]) == set(STRINGS["tr"])
    for key in ("label_mic_gain", "label_desktop_gain", "label_replay",
                "replay_save", "label_shortcuts", "shortcut_record"):
        assert STRINGS["en"][key] and STRINGS["tr"][key]
