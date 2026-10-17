"""Wayland backend: xdg-desktop-portal ScreenCast + gst-launch (pipewiresrc).

Why this architecture?
- The system ffmpeg has no pipewire demuxer, but GStreamer has `pipewiresrc`.
- The portal dialog (D-Bus) is done in pure Python (`dbus-next`),
  the video pipeline is a `gst-launch-1.0` subprocess: no PyGObject needed.
- Crash-safe: MKV recording via `matroskamux` (tolerates the first frame
  without PTS; mp4mux would fail with "Buffer has no PTS") + `.part`
  file + atomic rename. On clean stop a fast `ffmpeg -c copy` MP4 remux;
  if the remux is interrupted, the healthy MKV is kept.

Portal flow: CreateSession -> SelectSources(monitor/window) -> Start
(user selection dialog) -> OpenPipeWireRemote -> (node_id, fd).
The session stays open for the whole recording (background thread +
asyncio loop); when it closes, the PipeWire stream dies too. With
capture_mode "window" the portal lists only windows, with "ask" it lets
the user pick monitor+window.
"""
from __future__ import annotations

import asyncio
import itertools
import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path

from dbus_next import BusType, Message, Variant
from dbus_next.aio import MessageBus

from ..config import AppConfig
from ..recorder import RecordingState, finalize_part

BUS = "org.freedesktop.portal.Desktop"
OBJ = "/org/freedesktop/portal/desktop"

# Fixed part: session teardown + request response. ScreenCast signatures
# differ across portal versions (arg order, parameter order), so they are
# read from the broker at runtime (_discover_proxy).
STATIC_IFACES = """<interface name="org.freedesktop.portal.Session">
    <method name="Close">
    </method>
  </interface>
  <interface name="org.freedesktop.portal.Request">
    <signal name="Response">
      <arg name="response" type="u" direction="out"/>
      <arg name="results" type="a{sv}" direction="out"/>
    </signal>
  </interface>"""


async def _discover_proxy(bus: MessageBus) -> tuple[str, dict]:
    """Read the broker's ScreenCast signatures and build a minimal proxy XML.

    Returns: (xml, sig). sig e.g.
    {"SelectSources": [("session_handle", "o"), ("options", "a{sv}")],
     "Start": [("session_handle", "o"), ("parent_window", "s"), ...]}
    """
    reply = await bus.call(
        Message(
            destination=BUS,
            path=OBJ,
            interface="org.freedesktop.DBus.Introspectable",
            member="Introspect",
        )
    )
    all_xml: str = reply.body[0]
    start = all_xml.find('<interface name="org.freedesktop.portal.ScreenCast"')
    if start < 0:
        raise RuntimeError("ScreenCast interface not found")
    block = all_xml[start : all_xml.find("</interface>", start)]
    parts = ["<node>", '<interface name="org.freedesktop.portal.ScreenCast">']
    sig: dict = {}
    for m in re.finditer(r'<method name="(\w+)">(.*?)</method>', block, re.S):
        name, body = m.group(1), m.group(2)
        if name not in (
            "CreateSession",
            "SelectSources",
            "Start",
            "OpenPipeWireRemote",
        ):
            continue
        parts.append(f'<method name="{name}">')
        in_order = []
        for tag in re.findall(r"<arg\s+([^/]*)/>", body):
            t = re.search(r'type="([^"]+)"', tag)
            n = re.search(r'name="([^"]+)"', tag)
            d = re.search(r'direction="([^"]+)"', tag)
            if not (t and n and d):
                continue
            parts.append(
                f'<arg name="{n.group(1)}" type="{t.group(1)}" direction="{d.group(1)}"/>'
            )
            if d.group(1) == "in":
                in_order.append((n.group(1), t.group(1)))
        parts.append("</method>")
        sig[name] = in_order
    if "SelectSources" not in sig or "Start" not in sig:
        raise RuntimeError("could not read ScreenCast signatures")
    parts.append("</interface>")
    parts.append(STATIC_IFACES)
    parts.append("</node>")
    return "".join(parts), sig

_counter = itertools.count()


def _new_token(prefix: str = "castmane") -> str:
    # The portal rejects repeated tokens on the same connection.
    return f"{prefix}{int(time.time())}_{os.getpid()}_{next(_counter)}"


def _resolve_call(iface, *candidates):
    for name in candidates:
        meth = getattr(iface, name, None)
        if meth is not None:
            return meth
    avail = sorted(x for x in dir(iface) if x.startswith("call_"))
    raise RuntimeError(f"portal method not found {candidates}, available: {avail}")


def _pulsesrc_branch(
    device: str, sink: str | list[str], gain: float = 1.0, bitrate: int = 0,
    link: bool = True,
) -> list[str]:
    """One `pulsesrc ... ! <sink>` capture branch.

    `device` "" or "default" means "PulseAudio default" (no device property).
    Software gain: monitor (system sound) input is usually much quieter than
    mic input; compensate with volume >1.0 (nothing added at 1.0, pipeline
    unchanged). When `sink` is the recording mux the branch carries its own AAC
    encoder (single-source mode, needs `bitrate`); otherwise it feeds the
    shared mixer downstream. `sink` is a list so the replay branch can fork it.

    `link=True` prefixes the branch with "!" so it chains onto the previous
    element. Pass False when the branch has to open its own pipeline branch:
    a source that follows the replay `splitmuxsink` may not be attached with
    "!", because a sink has no output pad to continue from (gst-launch then
    fails with "erroneous pipeline: syntax error").
    """
    branch: list[str] = (["!"] if link else []) + ["pulsesrc"]
    if device and device != "default":
        branch.append(f"device={device}")
    branch += ["!", "audioconvert", "!", "audioresample"]
    if gain != 1.0:
        branch += ["!", "volume", f"volume={gain}"]
    branch += ["!", "queue", "!"]
    if isinstance(sink, str):
        sink = [sink]
    if sink == ["mux."]:
        branch += ["avenc_aac", f"bitrate={bitrate}", "!", "aacparse", "!"]
    branch += sink
    return branch


class PortalRecorder:
    """Wayland screen recording. Same interface as FfmpegX11Recorder:
    start() -> final path, stop() -> finished file or None."""

    name = "portal (Wayland)"

    def __init__(self, cfg: AppConfig, dialog_timeout: float = 180.0) -> None:
        self.cfg = cfg
        self.dialog_timeout = dialog_timeout
        self.state = RecordingState()
        self._proc: subprocess.Popen[bytes] | None = None
        self._stop_event = threading.Event()
        self._result: dict = {}
        self._session_thread: threading.Thread | None = None
        self._pw_fd = -1
        # PipeWire node/fd of the live session, kept so the replay encoder can
        # attach to the very same stream (no second permission dialog).
        self._stream_node = -1
        self._stream_fd = -1

    @property
    def elapsed(self) -> float:
        if not self.state.started_at:
            return 0.0
        end = self.state.pause_started if self.state.paused else time.time()
        return end - self.state.started_at - self.state.paused_total

    def pause(self) -> None:
        """Freeze the gst-launch pipeline (SIGSTOP). On resume, stale frames
        queued in PipeWire may show up as a short catch-up burst;
        recording integrity (.part + remux) is unaffected."""
        if not self.state.active or self._proc is None:
            raise RuntimeError("no active recording to pause")
        if self.state.paused:
            return
        self._proc.send_signal(signal.SIGSTOP)
        self.state.paused = True
        self.state.pause_started = time.time()

    def resume(self) -> None:
        if not self.state.paused or self._proc is None:
            raise RuntimeError("no paused recording to resume")
        self._proc.send_signal(signal.SIGCONT)
        self.state.paused_total += time.time() - self.state.pause_started
        self.state.paused = False
        self.state.pause_started = 0.0

    def _replay_target(self) -> tuple[Path | None, int]:
        """Replay ring location for the main pipeline, empty when the buffer
        is off. The ring lives next to the recordings and is pruned after
        every take (see replay.ReplayRecorder.stop)."""
        if not getattr(self.cfg, "replay_enabled", False):
            return None, 0
        from ..replay import replay_dir, segment_wrap_count

        return replay_dir(self.cfg.output_dir), segment_wrap_count(
            self.cfg.replay_seconds
        )

    # -- public API --

    def start(self) -> Path:
        if self.state.active:
            raise RuntimeError("recording already active")
        final = self.cfg.next_output_path()
        # Recording goes to MKV (mp4mux dies on the first frame without PTS),
        # remuxed to MP4 on stop when the target is MP4. Intermediate: X.mkv.part
        tmp_mkv = final.with_suffix(".mkv.part")
        mkv_final = final.with_suffix(".mkv")
        replay_dir_path, replay_files = self._replay_target()
        if replay_dir_path is not None:
            replay_dir_path.mkdir(parents=True, exist_ok=True)

        self._result = {}
        self._stop_event.clear()
        self._session_thread = threading.Thread(
            target=self._session_main, daemon=True
        )
        self._session_thread.start()
        node, fd = self._wait_for_stream()
        self._pw_fd = fd
        self._stream_node, self._stream_fd = node, fd

        cmd = self.build_cmd(node, fd, tmp_mkv, *self._replay_target())
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            pass_fds=(fd,),
        )
        # Quick death check: report immediately if the pipeline
        # does not survive 3 seconds.
        death = self._early_death(timeout=3.0)
        if death is not None:
            self._stop_event.set()
            raise RuntimeError(f"GStreamer pipeline failed to start: {death}")

        self.state = RecordingState(
            active=True, final_path=final, tmp_path=tmp_mkv,
            mkv_path=mkv_final, started_at=time.time(),
        )
        return final

    def stop(self) -> Path | None:
        if not self.state.active or self._proc is None:
            return None
        if self.state.paused:
            # A stopped process ignores signals; resume first.
            self.resume()
        # Gentle SIGINT first (so the muxer writes the trailer), then hard kill.
        self._proc.send_signal(signal.SIGINT)
        try:
            self._proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self.state.active = False
        self._stop_event.set()
        if self._session_thread is not None:
            self._session_thread.join(timeout=10)
        if self._pw_fd >= 0:
            try:
                os.close(self._pw_fd)
            except OSError:
                pass
            self._pw_fd = -1
        assert self.state.tmp_path and self.state.final_path and self.state.mkv_path
        mkv = finalize_part(self.state.tmp_path, self.state.mkv_path)
        if mkv is None:
            self.state.last_error = "output file was not created"
            return None
        if self.state.final_path.suffix == ".mkv":
            # MKV target: the staging file already is the final
            # container, no remux needed.
            return mkv
        # Fast lossless remux: MKV -> MP4. If it fails, hand over the
        # healthy MKV (never lose the user's footage).
        if self._remux(mkv, self.state.final_path):
            try:
                mkv.unlink()
            except OSError:
                pass
            return self.state.final_path
        self.state.last_error = "MP4 remux failed, MKV handed over instead"
        return mkv

    def build_replay_cmd(self, segment: Path) -> list[str]:
        """Replay encoder: a second `gst-launch` reading the same PipeWire
        stream as the main recording, writing one Matroska segment.

        GStreamer has no segment muxer, so the replay buffer rotates by
        restarting this pipeline (see `replay.ReplayRecorder.rotate`), which
        is why it targets a single file instead of a `-f segment` pattern.
        """
        return [
            "gst-launch-1.0",
            "pipewiresrc", f"fd={self._stream_fd}", f"path={self._stream_node}",
            "do-timestamp=true",
            "!", "videoconvert",
            "!", "queue",
            "!", "openh264enc",
            f"bitrate={self.cfg.video_bitrate_kbps * 1000}",
            "!", "h264parse",
            "!", "queue",
            "!", "matroskamux",
            "!", "filesink", f"location={segment}",
        ]

    def replay_ready(self) -> bool:
        """True once a portal stream exists for the replay encoder to share."""
        return self._stream_node >= 0 and self._stream_fd >= 0

    def _remux(self, mkv: Path, mp4: Path) -> bool:
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(mkv),
                 "-c", "copy", str(mp4)],
                capture_output=True, timeout=180,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        return (
            r.returncode == 0 and mp4.exists() and mp4.stat().st_size > 0
        )

    # -- komut --

    def build_cmd(self, node: int, fd: int, tmp: Path,
                  replay_dir: Path | None = None,
                  replay_files: int = 0) -> list[str]:
        from ..audio import (
            effective_gains,
            normalize_audio_mode,
            resolve_desktop_source,
            resolve_mic_source,
        )

        # The fd number is preserved as-is in the child via pass_fds.
        # gst-launch treats each argv item as a separate token: elements and
        # properties must be SEPARATE list items (merging them into one item
        # like "pipewiresrc fd=.. path=.." gives "erroneous pipeline:
        # syntax error").
        # With audio on, a second branch feeds the named mux:
        # video ... ! mux. + audio pulsesrc ... ! mux.
        # AAC is picked so it travels losslessly with `-c copy`
        # both in MKV and in the MP4 remux.
        # Camera picture-in-picture (OBS-style): v4l2src is composited
        # over the screen share via `compositor` (top-left corner, fixed
        # offset: the portal stream size is unknown at build time, so a
        # bottom-right anchor cannot be computed here). Preview-only mode
        # adds no branch (the Studio preview shows the camera separately).
        from ..camera import resolve_camera_device

        cam_dev = ""
        if getattr(self.cfg, "camera_enabled", False) and getattr(
            self.cfg, "camera_embed", True
        ):
            cam_dev = resolve_camera_device(
                getattr(self.cfg, "camera_device", "auto"))
        cmd = [
            "gst-launch-1.0",
            # do-timestamp: PipeWire buffers carry no PTS but mp4mux wants
            # one; stamp from the pipeline clock ("Buffer has no PTS" fix).
            "pipewiresrc", f"fd={fd}", f"path={node}", "do-timestamp=true",
            "!", "videoconvert",
            "!", "queue",
        ]
        if cam_dev:
            # Screen feeds compositor pad sink_0 (background); the camera
            # branch below takes sink_1 (foreground PiP).
            cmd += ["!", "comp."]
            cmd += [
                "v4l2src", f"device={cam_dev}",
                "!", "videoconvert",
                "!", "videoscale",
                "!", "video/x-raw,width=320,height=240",
                "!", "queue",
                "!", "comp.",
                "compositor", "name=comp",
                "comp.sink_1::xpos=16", "comp.sink_1::ypos=16",
                "comp.sink_1::zorder=10",
                "!", "videoconvert",
                "!", "queue",
                "!", "openh264enc",
                f"bitrate={self.cfg.video_bitrate_kbps * 1000}",
            ]
        else:
            cmd += [
                "!", "openh264enc",
                f"bitrate={self.cfg.video_bitrate_kbps * 1000}",
            ]
        cmd += [
            "!", "h264parse",
            # mp4mux dies on the first frame without PTS ("Buffer has no
            # PTS"); matroskamux tolerates it, MP4 is produced via remux
            # on stop.
            "!", "queue",
            "!",
        ]
        # Replay buffer: the encoded stream is teed to a second sink that
        # writes the rolling ring. No extra encoder, no second PipeWire
        # consumer, and the ring is bounded by `prune_segments`.
        has_replay = replay_dir is not None and replay_files > 0
        cmd += self._mux_tail(tmp, replay_dir, replay_files)
        audio_sink: list[str] = ["mux."]
        if has_replay:
            # Audio rides the same ring. splitmuxsink names its pad templates
            # `audio_%u`, so the pad is audio_0. Every tee branch needs its own
            # queue: without one, gst-launch fails with
            # "atee, mux'a bağlanamadı" (tee, mux cannot be linked).
            audio_sink = [
                "tee", "name=atee",
                "atee.", "!", "queue", "!", "mux.",
                "atee.", "!", "queue", "!", "rmux.audio_0",
            ]
        if self.cfg.audio_enabled:
            mode = normalize_audio_mode(self.cfg.audio_mode)
            mic_gain, desk_gain = effective_gains(self.cfg)
            if mode == "both":
                # Two capture branches (mic + desktop monitor) mixed down to
                # one track: ... ! mix. + ... ! mix. + mix. ! encoder ! mux.
                # Per-source gain lives in each pulsesrc branch (OBS-style).
                cmd += ["audiomixer", "name=mix", "!"]
                cmd += [
                    "audioconvert",
                    "!", "audioresample",
                    "!", "queue",
                    "!", "avenc_aac", f"bitrate={self.cfg.audio_bitrate_kbps * 1000}",
                    "!", "aacparse",
                    "!",
                ] + audio_sink
                cmd += _pulsesrc_branch(
                    resolve_mic_source(self.cfg.audio_source), "mix.",
                    gain=mic_gain, link=not has_replay,
                )
                cmd += _pulsesrc_branch(
                    resolve_desktop_source(self.cfg.audio_desktop_source),
                    "mix.", gain=desk_gain, link=not has_replay,
                )
            else:
                if mode == "desktop":
                    src = resolve_desktop_source(self.cfg.audio_desktop_source)
                    gain = desk_gain
                else:
                    src = resolve_mic_source(self.cfg.audio_source)
                    gain = mic_gain
                cmd += _pulsesrc_branch(
                    src, audio_sink, gain=gain,
                    bitrate=self.cfg.audio_bitrate_kbps * 1000,
                    link=not has_replay,
                )
        return cmd

    def _mux_tail(
        self, tmp: Path, replay_dir: Path | None, replay_files: int
    ) -> list[str]:
        """Sink side of the pipeline: the recording file, and the replay ring
        when the buffer is enabled.

        The ring uses `splitmuxsink`, which cuts on keyframes every
        `max-size-time` (it also asks the encoder for a keyframe at the split
        point) and numbers the files itself. `multifilesink` is unusable here:
        on this GStreamer build it opens a new file per *buffer*, not per
        segment.

        The ring size is bounded by the caller, since `splitmuxsink` has no
        file limit: `replay.ReplayRecorder` prunes after every take.
        """
        if replay_dir is None or replay_files <= 0:
            return ["matroskamux", "name=mux", "!", "filesink", f"location={tmp}"]
        from ..replay import SEGMENT_TIME_S

        ns = SEGMENT_TIME_S * 1_000_000_000
        return [
            "tee", "name=vtee",
            "vtee.", "!", "queue", "!", "matroskamux", "name=mux",
            "!", "filesink", f"location={tmp}",
            "vtee.", "!", "queue", "!",
            "splitmuxsink", "name=rmux", "muxer=matroskamux",
            f"max-size-time={ns}", "max-size-bytes=0",
            "send-keyframe-requests=true",
            f"location={replay_dir}/replay_%05d.mkv",
        ]

    # -- internals --

    def _wait_for_stream(self) -> tuple[int, int]:
        deadline = time.time() + self.dialog_timeout
        while time.time() < deadline:
            if "error" in self._result:
                raise RuntimeError(self._result["error"])
            if "node" in self._result and "fd" in self._result:
                return int(self._result["node"]), int(self._result["fd"])
            thread_alive = self._session_thread is not None and self._session_thread.is_alive()
            if not thread_alive:
                raise RuntimeError(
                    self._result.get("error", "portal session ended early")
                )
            time.sleep(0.2)
        self._stop_event.set()
        raise RuntimeError(
            "screen selection timed out: the share dialog was not answered"
        )

    def _early_death(self, timeout: float) -> str | None:
        assert self._proc is not None
        end = time.time() + timeout
        while time.time() < end:
            if self._proc.poll() is not None:
                out, _ = self._proc.communicate()
                tail = (out or b"")[-2000:].decode(errors="replace")
                return f"(rc={self._proc.returncode}): {tail[-300:]}"
            time.sleep(0.2)
        return None

    def _session_main(self) -> None:
        try:
            asyncio.run(self._hold_session())
        except Exception as e:  # noqa: BLE001 - don't lose thread errors
            self._result.setdefault("error", f"portal error: {e}")

    async def _hold_session(self) -> None:
        bus = await MessageBus(bus_type=BusType.SESSION, negotiate_unix_fd=True).connect()
        try:
            xml, sig = await _discover_proxy(bus)
            proxy = bus.get_proxy_object(BUS, OBJ, xml)
            sc = proxy.get_interface("org.freedesktop.portal.ScreenCast")

            req = await _resolve_call(sc, "call_create_session")(
                {"session_handle_token": Variant("s", _new_token())}
            )
            code, results = await self._await_response(bus, xml, req, 30)
            if code != 0:
                raise RuntimeError("portal session was rejected")
            session = results["session_handle"].value

            req = await _resolve_call(sc, "call_select_sources")(
                # Concrete types (s/o) take plain values; Variant is only
                # used inside a{sv}-style variant-carrying fields.
                session,
                {
                    # 1=monitor (fullscreen), 2=window, 3=ask both.
                    "types": Variant("u", self.cfg.source_types()),
                    "multiple": Variant("b", False),
                    # Portal cursor mode: 2=embedded (visible), 1=hidden.
                    "cursor_mode": Variant(
                        "u", 2 if getattr(self.cfg, "show_cursor", True) else 1
                    ),
                    "handle_token": Variant("s", _new_token()),
                },
            )
            code, _ = await self._await_response(bus, xml, req, 30)
            if code != 0:
                raise RuntimeError("source selection was rejected")

            start_vals = {
                "session_handle": session,
                "parent_window": "",
                "options": {"handle_token": Variant("s", _new_token())},
            }
            start_args = [start_vals[n] for n, _t in sig["Start"]]
            req = await _resolve_call(sc, "call_start")(*start_args)
            code, results = await self._await_response(bus, xml, req, self.dialog_timeout)
            if code == 1:
                raise RuntimeError("user cancelled screen sharing")
            if code != 0:
                raise RuntimeError(f"portal Start failed (code={code})")
            streams = results["streams"].value
            if not streams:
                raise RuntimeError("portal returned no streams")
            node = int(streams[0][0])

            fd = await _resolve_call(
                sc, "call_open_pipe_wire_remote", "call_open_pipewire_remote"
            )(session, {})
            # dbus-next translates the fd index into a real fd (replace_idx_with_fds).
            self._result["node"] = node
            self._result["fd"] = int(fd)

            # Keep the session alive until the recording ends.
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._stop_event.wait)

            try:
                sess_proxy = bus.get_proxy_object(BUS, session, xml)
                await sess_proxy.get_interface(
                    "org.freedesktop.portal.Session"
                ).call_close()
            except Exception:  # noqa: BLE001, S110 - best effort on teardown
                pass
        finally:
            bus.disconnect()

    async def _await_response(self, bus: MessageBus, xml: str, req_path: str, timeout: float):
        proxy = bus.get_proxy_object(BUS, req_path, xml)
        rq = proxy.get_interface("org.freedesktop.portal.Request")
        fut = asyncio.get_running_loop().create_future()

        def on_resp(response, results):
            if not fut.done():
                fut.set_result((response, results))

        rq.on_response(on_resp)
        return await asyncio.wait_for(fut, timeout)
