"""Wayland backend: xdg-desktop-portal ScreenCast + gst-launch (pipewiresrc).

Neden bu mimari?
- Sistem ffmpeg'inde pipewire demuxer yok, ama GStreamer'da `pipewiresrc` var.
- Portal diyafonu (D-Bus) saf Python (`dbus-next`) ile yapiliyor,
  video hatti `gst-launch-1.0` alt prosesi: PyGObject'e gerek yok.
- Crash-safe: `mp4mux fragment-duration` ile parcali MP4 + `.part`
  dosyasi + atomic rename (`recorder.finalize_part`).

Portal akisi: CreateSession -> SelectSources(monitor) -> Start
(kullanici secim diyafonu) -> OpenPipeWireRemote -> (node_id, fd).
Oturum, kayit boyunca acik tutulur (arka plan thread + asyncio loop);
kapaninca PipeWire stream'i de olur.
"""
from __future__ import annotations

import asyncio
import itertools
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from dbus_next import BusType, Variant
from dbus_next.aio import MessageBus

from ..config import AppConfig
from ..recorder import RecordingState, finalize_part

BUS = "org.freedesktop.portal.Desktop"
OBJ = "/org/freedesktop/portal/desktop"

# Butun portal nesnesini introspect etmek dbus-next'i bozuyor
# (bazi arayuzlerde gecerli olmayan uyeler var), o yuzden sadece
# ihtiyacimiz olan 3 arayuzu tasiyan minimal XML kullaniyoruz.
XML = """<node>
  <interface name="org.freedesktop.portal.ScreenCast">
    <method name="CreateSession">
      <arg name="options" type="a{sv}" direction="in"/>
      <arg name="request" type="o" direction="out"/>
    </method>
    <method name="SelectSources">
      <arg name="session_handle" type="s" direction="in"/>
      <arg name="options" type="a{sv}" direction="in"/>
      <arg name="request" type="o" direction="out"/>
    </method>
    <method name="Start">
      <arg name="parent_window" type="s" direction="in"/>
      <arg name="session_handle" type="s" direction="in"/>
      <arg name="options" type="a{sv}" direction="in"/>
      <arg name="request" type="o" direction="out"/>
    </method>
    <method name="OpenPipeWireRemote">
      <arg name="session_handle" type="s" direction="in"/>
      <arg name="options" type="a{sv}" direction="in"/>
      <arg name="fd" type="h" direction="out"/>
    </method>
  </interface>
  <interface name="org.freedesktop.portal.Session">
    <method name="Close">
    </method>
  </interface>
  <interface name="org.freedesktop.portal.Request">
    <signal name="Response">
      <arg name="response" type="u" direction="out"/>
      <arg name="results" type="a{sv}" direction="out"/>
    </signal>
  </interface>
</node>"""

_counter = itertools.count()


def _new_token(prefix: str = "castmane") -> str:
    # Portal ayni baglantida tekrar eden token'lari reddeder.
    return f"{prefix}{int(time.time())}_{os.getpid()}_{next(_counter)}"


def _resolve_call(iface, *candidates):
    for name in candidates:
        meth = getattr(iface, name, None)
        if meth is not None:
            return meth
    avail = sorted(x for x in dir(iface) if x.startswith("call_"))
    raise RuntimeError(f"portal metodu bulunamadi {candidates}, mevcut: {avail}")


class PortalRecorder:
    """Wayland ekran kaydi. Arayuz FfmpegX11Recorder ile ayni:
    start() -> final yol, stop() -> bitmis dosya ya da None."""

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

    @property
    def elapsed(self) -> float:
        if not self.state.started_at:
            return 0.0
        return time.time() - self.state.started_at

    # -- public API --

    def start(self) -> Path:
        if self.state.active:
            raise RuntimeError("zaten kayit aktif")
        final = self.cfg.next_output_path(".mp4")
        tmp = self.cfg.tmp_path_for(final)

        self._result = {}
        self._stop_event.clear()
        self._session_thread = threading.Thread(
            target=self._session_main, daemon=True
        )
        self._session_thread.start()
        node, fd = self._wait_for_stream()
        self._pw_fd = fd

        cmd = self.build_cmd(node, fd, tmp)
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            pass_fds=(fd,),
        )
        # Hizli olum kontrolu: boru hatti 3 sn yasamazsa hemen bildir.
        death = self._early_death(timeout=3.0)
        if death is not None:
            self._stop_event.set()
            raise RuntimeError(f"GStreamer hatti kurulamadi: {death}")

        self.state = RecordingState(
            active=True, final_path=final, tmp_path=tmp,
            started_at=time.time(),
        )
        return final

    def stop(self) -> Path | None:
        if not self.state.active or self._proc is None:
            return None
        # Once nazik SIGINT (mp4 trailer yazilir), olmazsa sert kapat.
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
        assert self.state.tmp_path and self.state.final_path
        done = finalize_part(self.state.tmp_path, self.state.final_path)
        if done is None:
            self.state.last_error = "cikti dosyasi olusmadi"
        return done

    # -- komut --

    def build_cmd(self, node: int, fd: int, tmp: Path) -> list[str]:
        # fd numarasi pass_fds ile cocuk proseste aynen korunur.
        return [
            "gst-launch-1.0",
            f"pipewiresrc fd={fd} path={node}",
            "!", "videoconvert",
            "!", "queue",
            "!", "openh264enc", f"bitrate={self.cfg.video_bitrate_kbps * 1000}",
            "!", "h264parse",
            "!", "mp4mux", f"fragment-duration={self.cfg.fragment_ms}",
            "!", "filesink", f"location={tmp}",
        ]

    # -- ic mekanizma --

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
                    self._result.get("error", "portal oturumu erken bitti")
                )
            time.sleep(0.2)
        self._stop_event.set()
        raise RuntimeError(
            "ekran secimi zaman asimina ugradi: paylasim diyafonu cevaplanmadi"
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
        except Exception as e:  # noqa: BLE001 - thread disi hata kaybolmasin
            self._result.setdefault("error", f"portal hatasi: {e}")

    async def _hold_session(self) -> None:
        bus = await MessageBus(bus_type=BusType.SESSION, negotiate_unix_fd=True).connect()
        try:
            proxy = bus.get_proxy_object(BUS, OBJ, XML)
            sc = proxy.get_interface("org.freedesktop.portal.ScreenCast")

            req = await _resolve_call(sc, "call_create_session")(
                {"session_handle_token": Variant("s", _new_token())}
            )
            code, results = await self._await_response(bus, req, 30)
            if code != 0:
                raise RuntimeError("portal oturumu reddedildi")
            session = results["session_handle"].value

            req = await _resolve_call(sc, "call_select_sources")(
                session,
                {
                    "types": Variant("u", 1),  # 1 = monitor (tam ekran)
                    "multiple": Variant("b", False),
                    "handle_token": Variant("s", _new_token()),
                },
            )
            code, _ = await self._await_response(bus, req, 30)
            if code != 0:
                raise RuntimeError("kaynak secimi reddedildi")

            req = await _resolve_call(sc, "call_start")(
                "", session, {"handle_token": Variant("s", _new_token())}
            )
            code, results = await self._await_response(bus, req, self.dialog_timeout)
            if code == 1:
                raise RuntimeError("kullanici ekran paylasimini iptal etti")
            if code != 0:
                raise RuntimeError(f"portal Start basarisiz (kod={code})")
            streams = results["streams"].value
            if not streams:
                raise RuntimeError("portal hicbir stream dondurmedi")
            node = int(streams[0][0])

            fd = await _resolve_call(
                sc, "call_open_pipe_wire_remote", "call_open_pipewire_remote"
            )(session, {})
            # dbus-next fd indeksini gercek fd'ye cevirir (replace_idx_with_fds).
            self._result["node"] = node
            self._result["fd"] = int(fd)

            # Kayit bitene kadar oturumu canli tut.
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._stop_event.wait)

            try:
                sess_proxy = bus.get_proxy_object(BUS, session, XML)
                await sess_proxy.get_interface(
                    "org.freedesktop.portal.Session"
                ).call_close()
            except Exception:  # noqa: BLE001, S110 - kapanis en iyi efor
                pass
        finally:
            bus.disconnect()

    async def _await_response(self, bus: MessageBus, req_path: str, timeout: float):
        proxy = bus.get_proxy_object(BUS, req_path, XML)
        rq = proxy.get_interface("org.freedesktop.portal.Request")
        fut = asyncio.get_running_loop().create_future()

        def on_resp(response, results):
            if not fut.done():
                fut.set_result((response, results))

        rq.on_response(on_resp)
        return await asyncio.wait_for(fut, timeout)
