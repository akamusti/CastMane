# CastMane

**Linux için crash-safe ekran kaydedici (Wayland öncelikli).**

[🇬🇧 Click for English](README.md)

OBS güçlüdür — ama kayıt sırasında crash verirse tüm `.mp4` dosyası çoğu zaman
çöp olur. CastMane tek bir ilke üzerine kurulu: **crash, görüntüyü götürmemeli.**

## Neden CastMane?

Klasik kaydediciler MP4 kapsayıcısını (`moov` atomu) ancak kayıt düzgün
biterse yazar. Process crash yerse ya da kill edilirse dosya oynatılamaz.
CastMane bunun yerine:

1. **Parçalı (fragmented) MP4** yazar (`frag_keyframe+empty_moov`,
   `mp4mux fragment-duration`) — dosyanın her parçası tek başına oynatılabilir.
2. Kaydı **`.part` dosyasına** yapar, düzgün stop sonrası **atomik rename** ile
   finale taşır. Yarım kalan `.part` dosyası yine izlenebilir.
3. Encoder'ı **nazikçe durdurur** (önce `SIGINT`, trailer yazılsın diye) ve
   encoder process'ini izler; beklenmedik ölüm sessizce geçiştirilmez, raporlanır.

> Kanıtlandı: `kill -9` ile öldürülen kayıt tamamen oynatılabilir kalıyor
> (`h264`, `ffprobe` ile doğrulandı). Detay için [Crash-güvenliği](#crash-güvenliği).

## Özellikler

- 🖥️ **Wayland**'da tam ekran kayıt: `xdg-desktop-portal` ScreenCast +
  GStreamer (`pipewiresrc → openh264enc → mp4mux`) — OBS yok, eklenti yok
- 🖥️ **X11 yedeği**: `ffmpeg` (`x11grab`), otomatik seçilir
- 🛡️ Crash-safe çıktı hattı (parçalı MP4, `.part` staging, atomik rename,
  encoder izcisi)
- 🪶 Sade Qt arayüzü: Kayıt / Durdur, süre, durum satırı
- 📁 `~/Videos/CastMane` altında zaman damgalı dosyalar
  (`castmane_YYYY-AA-GG_SS-DD-SS.mp4`)

## Gereksinimler

- Linux, Python ≥ 3.10 (**Fedora 44, KDE Plasma, Wayland**'de geliştirildi ve test edildi)
- `ffmpeg` — X11 backend için
- `pipewiresrc`, `openh264enc` ve `mp4mux` öğeleriyle `gst-launch-1.0` —
  Wayland backend için (Fedora KDE'de hazır gelir;
  `gst-inspect-1.0 pipewiresrc` ile kontrol edin)
- ScreenCast destekli çalışan bir `xdg-desktop-portal` (KDE/GNOME sağlar)

## Kurulum

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python3 -m castmane
```

Sistem Python paketi ya da derleyici gerekmez: Wayland backend portalla
D-Bus üzerinden (`dbus-next`) konuşur ve GStreamer'ı alt proses olarak
çalıştırır, bu yüzden `PyGObject` gerekmez.

## Kullanım

1. Uygulamayı başlatın. Durum satırı aktif backend'i gösterir, örn.
   `Hazir [portal (Wayland)]`.
2. **Kayda Basla**'ya tıklayın. Wayland'da sistemin ekran paylaşım diyafonu
   açılır — ekranı seçip onaylayın (180 saniye süreniz var).
3. **Durdur**'a basın. Bitmiş dosya `~/Videos/CastMane` altındadır.

Kayıt yarıda kesilirse (crash, elektrik kesintisi, `kill -9`) aynı klasördeki
`*.mp4.part` dosyasına bakın — aynen oynatılır. Yeniden adlandırmanız yeterli.

## Crash-güvenliği

| Katman | Mekanizma |
|---|---|
| Kapsayıcı | Parçalı MP4: `moov` sonda bir kez değil, aralara serpiştirilerek yazılır |
| Dosya taşıma | `X.mp4.part` dosyasına yaz, düzgün stop'ta `os.replace()` ile `X.mp4` yap |
| Kapatma | `SIGINT` → bekle → `SIGTERM` → `SIGKILL` kademesi |
| İzleme | Encoder izcisi erken ölümleri son log satırlarıyla raporlar |

Kanıtı kendiniz tekrarlayın:

```bash
gst-launch-1.0 videotestsrc is-live=true ! videoconvert ! openh264enc \
  ! h264parse ! mp4mux fragment-duration=1000 \
  ! filesink location=kanit.mp4.part &
sleep 4; kill -9 $!
ffprobe -v error -show_entries stream=codec_name,width,height kanit.mp4.part
```

## Mimari

```
src/castmane/
├── app.py               # Qt ana pencere (Kayıt/Durdur, süre, durum)
├── config.py            # Çıktı dizini, fps, bitrate, parça ayarları
├── recorder.py          # Crash-safe çekirdek: FfmpegX11Recorder + finalize_part()
├── backends/__init__.py # create_backend(): Wayland'da portal, X11'de ffmpeg
└── backends/portal.py   # PortalRecorder: ScreenCast D-Bus + gst-launch hattı
```

Portal imzaları çalışma anında broker'dan okunur (`session_handle` tipi,
`Start` parametre sırası), böylece istemci farklı `xdg-desktop-portal`
sürümlerinde çalışmaya devam eder.

## Yol haritası

- [x] Tam ekran kaydı (Wayland + X11)
- [x] Crash-safe çıktı hattı
- [ ] Ses kaydı (mikrofon / sistem sesi)
- [ ] Pencere / bölge seçimi
- [ ] Duraklat / devam et, kalite ön ayarları

## Lisans

GPL-3.0-or-later. Bkz. [LICENSE](LICENSE).
