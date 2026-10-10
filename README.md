# CastMane

OBS crash'lerine inat: **crash-safe ekran kaydedici**. GPL-3.0-or-later.

## Neden?

OBS kayit sirasinda crash verirse `.mp4` dosyan bozulur (moov atomu yazilamadi).
CastMane iki kural uygular:

1. **Fragmented MP4** (`frag_keyframe+empty_moov`): dosya parca parca oynatilabilir yazilir.
2. **`.part` + atomic rename**: kayit `X.mp4.part` dosyasina yapilir, saglikli stop'ta `X.mp4` olur. Kill yese bile `.part` izlenebilir kalir.

## Durum (v0.2)

- [x] Qt ana pencere (Rec/Stop, sure) — `src/castmane/app.py`
- [x] Crash-safe cekirdek + X11 fallback (`ffmpeg x11grab`) — `src/castmane/recorder.py`
- [x] Wayland portal + GStreamer backend (`pipewiresrc ! openh264enc ! mp4mux`) — `src/castmane/backends/portal.py`
- [ ] Ses (Pulse/PipeWire) — faz-2
- [ ] Pencere/bolge secimi — faz-3

Kanıt: `kill -9` ile oldurulen kayit bile oynatilabilir kalir
(`mp4mux fragment-duration=1000` + `.part` + atomic rename).

Ortam notu (Fedora 44 KDE Wayland): sistemdeki ffmpeg'te `pipewire` demuxer yok,
o yuzden Wayland kaydi GStreamer `pipewiresrc` uzerinden yapiliyor.
Kayda basinca sistemin ekran secim diyafonu acilir, ekrani secmen gerekir.

## Calistirma

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# Fedora'da Qt/GStreamer system baglari gerekiyorsa:
# sudo dnf install python3-PySide6 gstreamer1-plugins-bad-free gstreamer1-plugins-ugly-free
python3 -m castmane
```

Kayitlar: `~/Videos/CastMane/castmane_*.mp4`
