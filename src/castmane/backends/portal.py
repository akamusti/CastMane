"""Wayland backend: xdg-desktop-portal ScreenCast + gst-launch (pipewiresrc).

Neden bu mimari?
- Sistem ffmpeg'inde pipewire demuxer yok, ama GStreamer'da `pipewiresrc` var.
- Portal diyafonu (D-Bus) saf Python (`dbus-next`) ile yapiliyor,
  video hatti `gst-launch-1.0` alt prosesi: PyGObject'e gerek yok.
- Crash-safe: `matroskamux` ile MKV kaydi (PTS'siz ilk kareyi tolere
  eder; mp4mux'un "Buffer has no PTS" hatasi yasanmaz) + `.part`
  dosyasi + atomic rename. Duzgun stop'ta `ffmpeg -c copy` ile hizli
  MP4 remux; remux yarida kalirsa saglam MKV elde kalir.

Portal akisi: CreateSession -> SelectSources(monitor/window) -> Start
(kullanici secim diyafonu) -> OpenPipeWireRemote -> (node_id, fd).
Oturum, kayit boyunca acik tutulur (arka plan thread + asyncio loop);
kapaninca PipeWire stream'i de olur. capture_mode "window" ise portal
sadece pencere listeler, "ask" ise monitor+pencere secimini
kullaniciya birakir.
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

# Sabit kisim: oturum kapatma + istek cevabi. ScreenCast imzasi
# portal surumune gore degistigi icin (o-sirasi, parametre sirasi)
# calisma aninda broker'dan okunur (_discover_proxy).
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
    """Broker'in ScreenCast imzalarini okuyup minimal proxy XML uretir.

    Donus: (xml, sig). sig ornegin
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
        raise RuntimeError("ScreenCast arayuzu bulunamadi")
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
        raise RuntimeError("ScreenCast imzalari okunamadi")
    parts.append("</interface>")
    parts.append(STATIC_IFACES)
    parts.append("</node>")
    return "".join(parts), sig

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
        # Kayit MKV'ya yapilir (mp4mux PTS'siz ilk karede olur),
        # stop'ta MP4'e remux edilir. Ara dosya: X.mkv.part
        tmp_mkv = final.with_suffix(".mkv.part")
        mkv_final = final.with_suffix(".mkv")

        self._result = {}
        self._stop_event.clear()
        self._session_thread = threading.Thread(
            target=self._session_main, daemon=True
        )
        self._session_thread.start()
        node, fd = self._wait_for_stream()
        self._pw_fd = fd

        cmd = self.build_cmd(node, fd, tmp_mkv)
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
            active=True, final_path=final, tmp_path=tmp_mkv,
            mkv_path=mkv_final, started_at=time.time(),
        )
        return final

    def stop(self) -> Path | None:
        if not self.state.active or self._proc is None:
            return None
        # Once nazik SIGINT (muxer trailer yazsin), olmazsa sert kapat.
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
            self.state.last_error = "cikti dosyasi olusmadi"
            return None
        # Hizli kayipsiz remux: MKV -> MP4. Basarisiz olursa saglam
        # MKV'yi teslim et (kullanicinin goruntusu kaybolmasin).
        if self._remux(mkv, self.state.final_path):
            try:
                mkv.unlink()
            except OSError:
                pass
            return self.state.final_path
        self.state.last_error = "MP4 remux basarisiz, MKV teslim edildi"
        return mkv

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

    def build_cmd(self, node: int, fd: int, tmp: Path) -> list[str]:
        # fd numarasi pass_fds ile cocuk proseste aynen korunur.
        # gst-launch her argv ogesini ayri token sayar: oge ve ozellikler
        # AYRI liste ogeleri olmali ("pipewiresrc fd=.. path=.." tek
        # ogede birlesirse "hatali boru hatti: soz dizim hatasi" verir).
        # Ses aciksa matroskamux'a ikinci dal baglanir (adlandirilmis mux):
        # video ... ! mux. + audio pulsesrc ... ! mux.
        # AAC secildi: MKV'da da MP4 remux'ta da kayipsiz `-c copy` ile tasinir.
        cmd = [
            "gst-launch-1.0",
            # do-timestamp: PipeWire tamponlarinda PTS olmaz, mp4mux ister;
            # boru hatti saatine gore damgala ("Buffer has no PTS" cozumu).
            "pipewiresrc", f"fd={fd}", f"path={node}", "do-timestamp=true",
            "!", "videoconvert",
            "!", "queue",
            "!", "openh264enc", f"bitrate={self.cfg.video_bitrate_kbps * 1000}",
            "!", "h264parse",
            # mp4mux PTS'siz ilk karede "Buffer has no PTS" diye olur;
            # matroskamux tolere eder, MP4 stop'ta remux ile uretilir.
            "!", "queue",
            "!",
        ]
        if self.cfg.audio_enabled:
            cmd += ["matroskamux", "name=mux", "!", "filesink", f"location={tmp}"]
            audio_src = self.cfg.audio_source
            audio_branch: list[str] = ["pulsesrc"]
            if audio_src not in ("", "auto", "default", "mic"):
                audio_branch.append(f"device={audio_src}")
            cmd += audio_branch + [
                "!", "audioconvert",
                "!", "audioresample",
                "!", "queue",
                "!", "avenc_aac", f"bitrate={self.cfg.audio_bitrate_kbps * 1000}",
                "!", "aacparse",
                "!", "mux.",
            ]
        else:
            cmd += ["matroskamux", "!", "filesink", f"location={tmp}"]
        return cmd

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
            xml, sig = await _discover_proxy(bus)
            proxy = bus.get_proxy_object(BUS, OBJ, xml)
            sc = proxy.get_interface("org.freedesktop.portal.ScreenCast")

            req = await _resolve_call(sc, "call_create_session")(
                {"session_handle_token": Variant("s", _new_token())}
            )
            code, results = await self._await_response(bus, xml, req, 30)
            if code != 0:
                raise RuntimeError("portal oturumu reddedildi")
            session = results["session_handle"].value

            req = await _resolve_call(sc, "call_select_sources")(
                # Somut tiplere (s/o) duz deger verilir; Variant sadece
                # a{sv} gibi variant tasiyan alanlarin icinde kullanilir.
                session,
                {
                    # 1=monitor (tam ekran), 2=pencere, 3=ikisini sor.
                    "types": Variant("u", self.cfg.source_types()),
                    "multiple": Variant("b", False),
                    "handle_token": Variant("s", _new_token()),
                },
            )
            code, _ = await self._await_response(bus, xml, req, 30)
            if code != 0:
                raise RuntimeError("kaynak secimi reddedildi")

            start_vals = {
                "session_handle": session,
                "parent_window": "",
                "options": {"handle_token": Variant("s", _new_token())},
            }
            start_args = [start_vals[n] for n, _t in sig["Start"]]
            req = await _resolve_call(sc, "call_start")(*start_args)
            code, results = await self._await_response(bus, xml, req, self.dialog_timeout)
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
                sess_proxy = bus.get_proxy_object(BUS, session, xml)
                await sess_proxy.get_interface(
                    "org.freedesktop.portal.Session"
                ).call_close()
            except Exception:  # noqa: BLE001, S110 - kapanis en iyi efor
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
