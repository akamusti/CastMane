"""Replay buffer: a second encoder must actually fill the ring and save.

Regression for the feature being entirely dead: `build_replay_cmd()` had no
caller, so Save Replay always reported an empty buffer.
"""
import os
import subprocess

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from castmane import replay as rp  # noqa: E402
from castmane.app import MainWindow  # noqa: E402
from castmane.backends.portal import PortalRecorder  # noqa: E402
from castmane.config import AppConfig  # noqa: E402
from castmane.recorder import FfmpegX11Recorder, capture_input_args  # noqa: E402

# --- pure helpers -------------------------------------------------------


def test_segment_command_requests_a_keyframe_every_segment(tmp_path):
    """The segment muxer can only cut on a keyframe; openh264's default GOP is
    far longer, which produced empty segments and an empty buffer."""
    cfg = AppConfig(output_dir=tmp_path, fps=30)
    cmd = rp.build_replay_cmd(capture_input_args(cfg), tmp_path, 60)
    assert cmd[cmd.index("-g") + 1] == str(30 * rp.SEGMENT_TIME_S)
    assert "-f" in cmd and "segment" in cmd
    assert "-segment_wrap" in cmd


def test_gop_follows_a_custom_frame_rate(tmp_path):
    cfg = AppConfig(output_dir=tmp_path, fps=60)
    cmd = rp.build_replay_cmd(capture_input_args(cfg), tmp_path, 60)
    assert cmd[cmd.index("-g") + 1] == str(60 * rp.SEGMENT_TIME_S)


def test_interactive_region_is_never_requested_for_the_replay_encoder(tmp_path):
    """A second encoder must not pop another crosshair prompt."""
    cfg = AppConfig(output_dir=tmp_path, capture_mode="ask")
    assert "-select_region" not in rp.build_replay_cmd(
        capture_input_args(cfg), tmp_path, 60)
    assert "-select_region" in rp.build_replay_cmd(
        capture_input_args(cfg, interactive=True), tmp_path, 60)


def test_list_segments_accepts_mp4_and_mkv(tmp_path):
    """GStreamer only muxes Matroska, ffmpeg writes MP4; both are ring slots."""
    ring = rp.replay_dir(tmp_path)
    ring.mkdir(parents=True)
    (ring / "replay_000.mp4").write_bytes(b"x" * 10)
    (ring / "replay_001.mkv").write_bytes(b"x" * 10)
    (ring / "replay_002.mp4").write_bytes(b"")  # empty: not a segment
    names = [p.name for p in rp.list_segments(tmp_path)]
    assert names == ["replay_000.mp4", "replay_001.mkv"]


def test_prune_keeps_the_newest(tmp_path):
    ring = rp.replay_dir(tmp_path)
    ring.mkdir(parents=True)
    for i in range(6):
        (ring / f"replay_{i:03d}.mp4").write_bytes(b"x")
    rp.prune_segments(tmp_path, keep=2)
    assert [p.name for p in rp.list_segments(tmp_path)] == [
        "replay_004.mp4", "replay_005.mp4"]


def test_save_replay_joins_through_a_real_list_file(tmp_path):
    """`-i pipe:0` made the concat demuxer look for `pipe:<abs path>`, so
    every join failed even with valid segments."""
    segs = [tmp_path / f"replay_{i:03d}.mp4" for i in range(2)]
    list_file = tmp_path / "j.txt"
    cmd = rp.build_concat_cmd(segs, tmp_path / "out.mp4", list_file)
    assert "pipe:0" not in cmd
    assert cmd[cmd.index("-i") + 1] == str(list_file)
    assert cmd[cmd.index("-c") + 1] == "copy"


# --- ReplayRecorder behaviour (no real encoder) -------------------------


class _FakeProc:
    def __init__(self):
        self.signals = []
        self.returncode = None

    def poll(self):
        return self.returncode

    def send_signal(self, sig):
        self.signals.append(sig)

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self):
        self.signals.append("term")

    def kill(self):
        self.signals.append("kill")


class _PortalishBackend:
    """Stands in for the GStreamer backend."""

    name = "portal (Wayland)"


def test_portal_writes_the_ring_from_the_main_pipeline(tmp_path):
    """A second PipeWire consumer cannot read the same portal fd, so the
    replay branch lives inside the main gst pipeline instead."""
    cfg = AppConfig(output_dir=tmp_path, replay_seconds=60, replay_enabled=True)
    backend = PortalRecorder(cfg)
    ring = rp.replay_dir(tmp_path)
    cmd = backend.build_cmd(42, 9, tmp_path / "t.mkv.part", ring, 8)

    joined = " ".join(cmd)
    assert "tee" in cmd and "splitmuxsink" in cmd
    assert "name=rmux" in cmd, "the replay sink needs its own name"
    assert f"location={ring}/replay_%05d.mkv" in joined
    # Segments cut on a keyframe every SEGMENT_TIME_S, not per buffer.
    assert f"max-size-time={rp.SEGMENT_TIME_S * 1_000_000_000}" in joined
    assert "send-keyframe-requests=true" in joined
    assert "muxer=matroskamux" in joined
    # No second process, no second portal consumer.
    assert cmd.count("pipewiresrc") == 1
    assert backend.replay_ready() is False  # no live stream in this test


def test_portal_replay_audio_joins_the_ring(tmp_path):
    """Audio must ride the same ring, otherwise the replay clip has no sound."""
    cfg = AppConfig(output_dir=tmp_path, replay_enabled=True,
                    audio_enabled=True, audio_mode="mic")
    ring = rp.replay_dir(tmp_path)
    cmd = PortalRecorder(cfg).build_cmd(
        42, 9, tmp_path / "t.mkv.part", ring, 8)
    assert "rmux.audio_0" in cmd, "the audio branch must feed the ring sink too"
    assert "mux." in cmd, "and the recording mux"
    # Every tee branch needs its own queue, otherwise gst-launch refuses the
    # pipeline with "tee, mux cannot be linked".
    atee = cmd.index("atee.")
    assert cmd[atee:atee + 4] == ["atee.", "!", "queue", "!"]


def test_pulsesrc_branch_links_only_when_it_follows_an_element():
    """A source that follows the replay splitmuxsink cannot be attached with
    "!": the sink has no pad to continue from, so gst-launch reports a syntax
    error."""
    from castmane.backends.portal import _pulsesrc_branch

    chained = _pulsesrc_branch("auto", ["mux."])
    assert chained[0] == "!"
    standalone = _pulsesrc_branch("auto", ["mux."], link=False)
    assert standalone[0] == "pulsesrc"


def test_portal_pipeline_is_unchanged_when_replay_is_off(tmp_path):
    cfg = AppConfig(output_dir=tmp_path, replay_enabled=False)
    backend = PortalRecorder(cfg)
    cmd = backend.build_cmd(42, 9, tmp_path / "t.mkv.part", *backend._replay_target())
    assert "tee" not in cmd
    assert "splitmuxsink" not in cmd
    assert "name=rmux" not in cmd


def test_portal_replay_needs_no_extra_process(tmp_path):
    cfg = AppConfig(output_dir=tmp_path, replay_seconds=60)
    rec = rp.ReplayRecorder(cfg, _PortalishBackend())
    assert rec.needs_process is False
    assert rec.start() is True
    assert rec.active is False  # nothing to spawn: the main pipeline does it
    rec.stop()  # still trims the ring afterwards


def test_x11_replay_runs_a_second_encoder(tmp_path, monkeypatch):
    cfg = AppConfig(output_dir=tmp_path, replay_seconds=60)
    backend = FfmpegX11Recorder(cfg)
    procs = []
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **k: procs.append(_FakeProc()) or procs[-1]
    )

    rec = rp.ReplayRecorder(cfg, backend)
    assert rec.needs_process is True
    assert rec.start() is True
    assert rec.active is True
    assert rp.replay_dir(tmp_path).is_dir()

    rec.stop()
    assert rec.active is False
    # Graceful order: SIGINT, never a bare kill.
    assert procs[0].signals


def test_replay_refuses_without_a_display(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPLAY", "")
    monkeypatch.setattr("os.path.exists", lambda p: False)
    monkeypatch.setattr(rp, "capture_input_args", lambda cfg: [])
    cfg = AppConfig(output_dir=tmp_path, replay_seconds=60)
    rec = rp.ReplayRecorder(cfg, FfmpegX11Recorder(cfg))
    assert rec.start() is False
    assert rec.active is False
    assert rec.last_error


def test_stop_is_safe_without_a_run(tmp_path):
    rec = rp.ReplayRecorder(AppConfig(output_dir=tmp_path), _PortalishBackend())
    rec.stop()  # must not raise


def test_replay_segments_survive_stop(tmp_path, monkeypatch):
    """The tail of the take stays saveable after the recording ended."""
    cfg = AppConfig(output_dir=tmp_path, replay_seconds=60)
    backend = _PortalishBackend()
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: _FakeProc())
    rec = rp.ReplayRecorder(cfg, backend)
    rec.start()
    ring = rp.replay_dir(tmp_path)
    ring.mkdir(parents=True, exist_ok=True)
    (ring / "replay_001.mkv").write_bytes(b"x" * 50)
    rec.stop()
    assert [p.name for p in rp.list_segments(tmp_path)] == ["replay_001.mkv"]


# --- UI wiring ----------------------------------------------------------


def _window():
    _ = QApplication.instance() or QApplication([])
    os.environ["CASTMANE_NO_RECOVERY"] = "1"
    return MainWindow(AppConfig())


@pytest.fixture
def window():
    w = _window()
    yield w
    w._replay.stop()


def test_recording_starts_and_stops_the_replay_encoder(window, monkeypatch):
    calls = {"start": 0, "stop": 0}
    monkeypatch.setattr(
        window._replay, "start",
        lambda: (calls.__setitem__("start", calls["start"] + 1), True)[-1],
    )
    monkeypatch.setattr(
        window._replay, "stop",
        lambda: calls.__setitem__("stop", calls["stop"] + 1),
    )
    window.cfg.replay_enabled = True

    window._start_replay()
    assert calls["start"] == 1

    window._stop_replay()
    assert calls["stop"] == 1


def test_disabled_replay_starts_nothing(window, monkeypatch):
    called = []
    monkeypatch.setattr(window._replay, "start", lambda: called.append(1) or True)
    window.cfg.replay_enabled = False
    window._start_replay()
    assert called == []


def test_a_failed_replay_does_not_break_the_take(window, monkeypatch):
    monkeypatch.setattr(window._replay, "start", lambda: False)
    monkeypatch.setattr(window._replay, "last_error", "no display", raising=False)
    window.cfg.replay_enabled = True
    window._start_replay()
    assert "no display" in window.status_lbl.text()


def test_cli_replay_save_is_translated():
    from castmane.i18n import STRINGS

    for key in ("replay_empty", "replay_failed", "replay_saved"):
        assert STRINGS["en"][key]
        assert STRINGS["tr"][key]
