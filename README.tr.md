# CastMane

**Linux için crash-safe ekran kaydedici (Wayland öncelikli).**

[🇬🇧 Click for English](README.md)

OBS güçlüdür — ama kayıt sırasında crash verirse tüm `.mp4` dosyası çoğu zaman
çöp olur. CastMane tek bir ilke üzerine kurulu: **crash, görüntüyü götürmemeli.**

## Neden CastMane?

Klasik kaydediciler MP4 kapsayıcısını (`moov` atomu) ancak kayıt düzgün
biterse yazar. Process crash yerse ya da kill edilirse dosya oynatılamaz.
CastMane bunun yerine:

1. Kaydı **crash'e dayanıklı kapsayıcıda** biriktirir — X11'de parçalı MP4
   (`frag_keyframe+empty_moov`), Wayland'da MKV (`matroskamux`; PipeWire'ın
   verdiği damgasız ilk kareyi tolere eder) — dosyanın her parçası tek başına
   oynatılabilir, sonra MP4 teslim edilir.
2. Kaydı **`.part` dosyasına** yapar, düzgün stop sonrası **atomik rename** ile
   finale taşır. Yarım kalan `.part` dosyası yine izlenebilir.
3. Encoder'ı **nazikçe durdurur** (önce `SIGINT`, trailer yazılsın diye) ve
   encoder process'ini izler; beklenmedik ölüm sessizce geçiştirilmez, raporlanır.

> Kanıtlandı: `kill -9` ile öldürülen kayıt tamamen oynatılabilir kalıyor
> (`h264`, `ffprobe` ile doğrulandı). Wayland hattı MKV kaydeder, çünkü
> PipeWire'ın verdiği damgasız ilk karede `mp4mux` "Buffer has no PTS" diye
> ölür; MKV duruşta `ffmpeg -c copy` ile MP4'e çevrilir.
> Detay için [Crash-güvenliği](#crash-güvenliği).

## Özellikler

- 🖥️ **Wayland**'da tam ekran kayıt: `xdg-desktop-portal` ScreenCast +
  GStreamer (`pipewiresrc → openh264enc → matroskamux`), duruşta kayıpsız
  MP4 remux — OBS yok, eklenti yok
- 🖥️ **X11 yedeği**: `ffmpeg` (`x11grab`), otomatik seçilir
- 🛡️ Crash-safe çıktı hattı (parçalı MP4, `.part` staging, atomik rename,
  encoder izcisi)
- 🪶 Sade Qt arayüzü: Kayıt / Durdur, süre, durum satırı
- 🪟 Kayıt kaynağı seçimi: tam ekran, tek pencere ya da her seferinde sor
  (Wayland: portal diyafonu; X11: sabit bölge, pencere kimliği ya da sürükle-seç)
- 🔊 İsteğe bağlı ses kaydı (varsayılan mikrofon, monitor cihazıyla sistem sesi),
  aynı crash-safe MKV → MP4 hattında AAC
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
2. Kaynak seçin: **Tam Ekran**, **Pencere** ya da **Sor / Bölge Seç**.
   Wayland'da sistem diyafonu monitör ya da pencere listeler; X11'de *Sor*
   fareyle çerçeve çizdirir, sabit bölgeyi X/Y/W/H ile de verebilirsiniz
   (`0` = tam ekran).
3. **Kayda Basla**'ya tıklayın. Wayland'da sistemin ekran paylaşım diyafonu
   açılır — ekranı ya da pencereyi seçip onaylayın (180 saniye süreniz var).
4. **Durdur**'a basın. Bitmiş dosya `~/Videos/CastMane` altındadır.

Kayıt yarıda kesilirse (crash, elektrik kesintisi, `kill -9`) aynı klasördeki
`*.mkv.part` (Wayland) ya da `*.mp4.part` (X11) dosyasına bakın — aynen oynatılır.
Yeniden adlandırmanız yeterli (Wayland'da isterseniz MP4'e çevirin:
`ffmpeg -i dosya.mkv.part -c copy dosya.mp4`).

## Crash-güvenliği

| Katman | Mekanizma |
|---|---|
| Kapsayıcı | MKV staging (`matroskamux` eksik damgaları tolere eder), düzgün stop'ta kayıpsız `ffmpeg -c copy` ile MP4 |
| Dosya taşıma | `X.mp4.part` dosyasına yaz, düzgün stop'ta `os.replace()` ile `X.mp4` yap |
| Kapatma | `SIGINT` → bekle → `SIGTERM` → `SIGKILL` kademesi |
| İzleme | Encoder izcisi erken ölümleri son log satırlarıyla raporlar |

Kanıtı kendiniz tekrarlayın (canlı MKV kaydını öldürüp remux edin):

```bash
gst-launch-1.0 videotestsrc is-live=true ! videoconvert ! openh264enc \
  ! h264parse ! matroskamux ! filesink location=kanit.mkv.part &
sleep 4; kill -9 $!
ffprobe -v error -show_entries stream=codec_name kanit.mkv.part
ffmpeg -y -v error -i kanit.mkv.part -c copy kanit.mp4
ffprobe -v error -show_entries stream=codec_name,duration kanit.mp4
```

## Mimari

```
src/castmane/
├── app.py               # Qt ana pencere (Kayıt/Durdur, süre, durum)
├── config.py            # Çıktı dizini, fps, bitrate, parça ayarları
├── recorder.py          # Crash-safe çekirdek: FfmpegX11Recorder + finalize_part()
├── backends/__init__.py # create_backend(): Wayland'da portal, X11'de ffmpeg
└── backends/portal.py   # PortalRecorder: ScreenCast D-Bus + gst-launch hattı
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
- [ ] Duraklat / devam et, kalite ön ayarları

### Kayıt kaynağı

```python
from castmane.config import AppConfig
cfg = AppConfig(capture_mode="window")  # "fullscreen" | "window" | "ask"
# X11 sabit bölge (0 = tam ekran):
# cfg = AppConfig(region_x=100, region_y=200, region_w=1280, region_h=720)
# X11 tek pencere (kimlik `xwininfo` çıktısından):
# cfg = AppConfig(capture_mode="window", window_id=123456)
```

Wayland'da `window` / `ask` portal diyafonunu monitörden pencereye
çevirir (ya da ikisini birden sorar). X11'de `ask` fareyle bölge
seçtirir (`ffmpeg -select_region`), `region_*` / `window_id` ise
betiklenebilir kontrol verir. Crash-güvenliği değişmez: pencere ve
bölge kayıtları da `.part` + atomik rename hattından geçer.

### Ses

Penceredeki **Sesli kaydet (mikrofon)** kutusunu işaretleyin ya da kodla:

```python
from castmane.config import AppConfig
cfg = AppConfig(audio_enabled=True)  # varsayılan mikrofon
# sistem sesi için:
# cfg = AppConfig(audio_enabled=True,
#     audio_source="alsa_output.pci-0000_00_1f.3.analog-stereo.monitor")
```

Cihazları `pactl list short sources` ile listeleyin. Ses, aynı crash-safe
dosyaya AAC olarak yazılır (Wayland'da `avenc_aac`, X11'de `aac`); `kill -9`
ile ölen kayıt da MP4 remux da ses parçasını korur.

## Lisans

GPL-3.0-or-later. Bkz. [LICENSE](LICENSE).
