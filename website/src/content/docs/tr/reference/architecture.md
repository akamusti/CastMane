---
title: Mimari
description: CastMane nasıl bir araya geliyor.
---

```
src/castmane/
|-- app.py               # Qt ana pencere (Kayıt/Durdur, süre, durum)
|__ config.py            # Çıktı dizini, fps, bit hızı, parça ayarları
+-- recorder.py          # Crash-safe çekirdek: FfmpegX11Recorder + finalize_part()
+-- backends/__init__.py # create_backend(): Wayland'da portal, X11'de ffmpeg
`-- backends/portal.py   # PortalRecorder: ScreenCast D-Bus + gst-launch hattı
                           (MKV kayıt, duruşta MP4 remux)
```

Portal imzaları çalışma anında broker'dan okunur (`session_handle` tipi,
`Start` parametre sırası), böylece istemci farklı `xdg-desktop-portal`
sürümlerinde çalışmaya devam eder.

## Yol haritası

- [x] Tam ekran kaydı (Wayland + X11)
- [x] Crash-safe çıktı hattı
- [x] Ses kaydı (varsayılan mikrofon; `audio_source` monitor cihazıyla sistem sesi)
- [x] Pencere / bölge seçimi
- [x] Duraklat / devam et, yapılandırılabilir kalite ön ayarları
- [x] Tek dosyalık AppImage dağıtımı
