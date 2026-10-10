---
title: Kurulum
description: CastMane'i AppImage ile kurun, kendiniz derleyin ya da kaynaktan çalıştırın.
---

## Seçenek 1 — AppImage (önerilen)

[Sürümler sayfasından](https://github.com/akamusti/CastMane/releases)
AppImage'i indirin, sonra:

```bash
chmod +x CastMane-*.AppImage
./CastMane-*.AppImage
```

Hepsi bu — Python, venv ya da pip kurulumu gerekmez. AppImage Python, Qt ve
tüm PyPI bağımlılıklarını içinde getirir.

### Hâlâ gereken host araçları

Bunları sisteminize kurun (geri kalan her şey pakete dahil):

```bash
# Fedora / KDE (Fedora 44, KDE Plasma, Wayland'de test edildi)
sudo dnf install ffmpeg gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugin-openh264

# Ubuntu / Debian
sudo apt install ffmpeg gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly
```

| Bileşen         | Wayland backend'i                                                | X11 backend'i            |
| --------------- | ---------------------------------------------------------------- | ------------------------ |
| İşletim sistemi | Linux, Python ≥ 3.10                                             | Linux, Python ≥ 3.10     |
| Video hattı     | `pipewiresrc`, `openh264enc`, `matroskamux` içeren `gst-launch-1.0` | `x11grab` içeren `ffmpeg` |
| Sistem servisi  | ScreenCast destekli `xdg-desktop-portal` (KDE/GNOME sağlar)      | —                        |
| Ses (isteğe bağlı) | Pulse/PipeWire kaynağı (`pactl list short sources`)            | Pulse kaynağı            |

Bir şey mi eksik? Uygulama neyi kurmanız gerektiğini söyleyen anlaşılır bir
pencere gösterir.

## Seçenek 2 — AppImage'i kendiniz derleyin

```bash
./packaging/build-appimage.sh
./dist/CastMane-*.AppImage
```

## Seçenek 3 — Kaynaktan (geliştiriciler)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python3 -m castmane
```

Sistem Python paketi ya da derleyici gerekmez: Wayland backend'i portalı
D-Bus üzerinden (`dbus-next`) sürer ve GStreamer'ı alt proses olarak
çalıştırır, bu yüzden `PyGObject` gerekmez.
