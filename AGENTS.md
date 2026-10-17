# AGENTS.md — CastMane AI Agent Instructions

Bu dosya AI kod ajanları içindir. Kullanıcıyla hep Türkçe konuş.

## Proje

CastMane: Linux (Wayland öncelikli) crash-safe ekran kaydedici. Qt (PySide6) + GStreamer / FFmpeg.
Python >= 3.10. Paket kökü: `src/castmane/`.

## Komutlar

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python3 -m castmane            # uygulamayı çalıştır
python3 -m pytest -q           # testler
python3 -m ruff check src tests  # lint
```

## Mimari

- `app.py` — Qt ana pencere (Record/Stop/Pause, timer, status)
- `config.py` — `AppConfig`: çıktı dizini, fps, bitrate, presetler (`draft|balanced|high`)
- `recorder.py` — crash-safe çekirdek: `FfmpegX11Recorder` + `finalize_part()`
- `backends/__init__.py` — `create_backend()`: Wayland'de portal, X11'de ffmpeg
- `backends/portal.py` — ScreenCast D-Bus + `gst-launch` pipe (MKV kayıt, stop'ta MP4 remux)
- `audio.py`, `i18n.py`, `theme.py`, `icons.py` — yardımcı modüller

Kurallar:

- `PyGObject` kullanma. Portal istemcisi `dbus-next` + subprocess `gst-launch` ile çalışır.
- Kayıtlar `.part` dosyasına yazılır, temiz stop sonrası `os.replace()` ile atomik rename yapılır.
- `finalize_part()` mantığını değiştirme: boş/sıfır baytlık `.part` promote edilmez, crash artığı silinmez.
- Portal imzaları runtime'da keşfedilir (`session_handle` tipi, `Start` argüman sırası) — hardcode etme.
- Backend seçimi `WAYLAND_DISPLAY` / `XDG_SESSION_TYPE` ile yapılır (`backends/__init__.py`) — elle override ekleme.
- UI varsayılanı İngilizce + light tema; `AppConfig(language, theme)` ile değişir.
- `AppConfig.save()/load()/from_dict()` asla exception fırlatmaz: bozuk/eski settings dosyası = default'lara dön. Bu garantiyi bozma.
- Pause = `SIGSTOP`, resume = `SIGCONT`; stop sırasında pause aktifse önce resume yap (trailer temiz yazılsın).
- Kapatma sırası: `SIGINT` → bekle → `SIGTERM` → `SIGKILL`. Sıralamayı değiştirme.
- Subprocess çağrılarında `shell=True` yasak; argümanları liste olarak geçir.
- Ses: Wayland'de `avenc_aac`, X11'de `aac`. `audio_gain` en fazla `5.0` (clipping riski).
- Dosya adı `sanitize_prefix()` + `YYYY-MM-DD_HH-MM-SS` timestamp; boş alan `MIN_FREE_MB` (100 MB) altında kayda başlama.
- Yeni UI metni eklenirse `i18n.py`'da `en` + `tr` anahtarları birebir aynı olmalı; `get()` İngilizce'ye düşer.

## Test

- Yeni/değişen kayıt mantığı için `tests/` altına test ekle, `ffprobe` kanıtını PR açıklamasına koy.
- Wayland portal gerçek donanım gerektirir; headless ortamda subprocess mock'la, gerçek portal bekleme.
- GUI testi gerekiyorsa `QT_QPA_PLATFORM=offscreen` ile çalıştır, gerçek ekran bekleme.

## Repo hijyeni (ajanların sık bozduğu yerler)

- `website/` Astro Starlight sitesidir — Python venv'e kurma, `node_modules` / `dist` / `.astro` commit'leme.
- AppImage derlemesi `packaging/build-appimage.sh` ile yapılır, `.venv-appimage` kullanır — normal `.venv`'i kirletme.
- `README.md` kullanıcıya dönük değişirse `README.tr.md`'yi de senkron tut.
- Commit'e ASLA katma: `*.part`, `*.AppImage`, `AppDir/`, `build/`, `dist/`, `Videos/`, `.venv*/`, `__pycache__/`, `.env`.

## Zorunlu güvenlik kontrolü (her görev bitiminde)

Kod bitmeden önce şunları ara: token, API key/secret, parola, kişisel bilgi
(e-posta, kullanıcı adı, path, IP, makine adı), hardcode credential.

```bash
git diff --cached --name-only; git diff --name-only
grep -rniE "api[_-]?key|secret|token|password|passwd|bearer" src tests --include="*.py" || true
```

- Bulguyu koda ASLA gömme. Varsa `.env`'e taşı (zaten git-ignored), koda `os.getenv()` ile oku.
- `.env.example`'a sadece `ANAHTAR_ADI=` placeholder ekle, değer yazma.
- `.env`, `.env.*` dosyalarını `git add` etme, commit'e katma.

## Git workflow

- Commit + push mesajları hep İngilizce, conventional format: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`.
- Push öncesi `pytest -q` ve `ruff check` temiz olmalı.
- Varsayılan branch: `main`, remote: `origin`. Kullanıcı aksini söylemedikçe doğrudan `main`'e commit + push.
- Push'tan önce `git status --short` ile `.env` / `*.part` / `*.AppImage` sızmadığını doğrula.
- AI destekli her commit sonuna imza ekle (kullanıcı açıkça isterse):
  `Co-Authored-By: opencode <noreply@opencode.ai>`. Gerçek kimliği yaz —
  başka bir model/vendor adı uydurma. Yayınlanmış `main` geçmişi geriye
  dönük rewrite edilmez; imza yalnızca yeni commit'lere konur.

### Her düzeltme için branch + PR (kalıcı kural)

- **Her issue ayrı branch, her issue ayrı PR.** Düzeltmeler `main`'e doğrudan push edilmez;
  GitHub ana branch'ten aynı branch'e PR'a izin vermediği için her iş için `main`'den türeyen
  bir feature branch açılır ve PR ile `main`'e önerilir.
- Branch adı: `fix/<kısa-konu>` / `feat/<kısa-konu>`. Örnek: `fix/x11-partial-muxer`.
- PR gövdesi: ne bozuktu, nasıl yeniden üretilir, beklenen vs. gerçekleşen davranış,
  `Closes #<n>`. PR'ın **sonunda** `Closes #<n>` satırı bulunur, gövdenin ortasında değil.
- Versiyon bump'ı hangi PR'da yapılacaksa o PR'da (`pyproject.toml` + `__init__.py:4` senkron).
- Sıralama: bağımlı düzeltmeler önce bağımsız olanlar. Her PR'da `pytest -q` + `ruff check` temiz.
- Tasarım/kapsam belirsizliği varsa düzeltmeden önce tek soru sor; onaysız yarım çözüm yazma.

## Versiyonlama (ilerideki tüm update'ler için geçerli, kalıcı kural)

- Varsayılan patch artır: `0.8.0` → `0.8.1`, `0.8.2`, `0.8.3`... Küçük fix / küçük iyileştirme = patch.
- Çok küçük düzeltmeler (tek satırlık fix, layout sıkıştırma, yazım/çeviri, padding vb. — yeni davranış yok)
  patch hanesini büyütmez, son haneye eklenir: `0.9.5` → `0.9.51`, `0.9.52`... Sıradaki gerçek
  patch/fix paketi normal numaraya döner (`0.9.6`). Sadece küçük updatelerde bu şema kullanılır.
- `0.9.0` (minor) sadece gözle görülür yeni özellik / birikmiş özellik paketi için, kullanıcı onayı ile.
- `1.0.0` (major) sadece büyük kırıcı değişiklik / stable milestone için, açık kullanıcı onayı olmadan geçme.
- Ajan kendiliğinden minor/major'a zıplamaz; emin değilse patch'te kalır ve kullanıcıya sorar.
- Version bump'ta `pyproject.toml` + `src/castmane/__init__.py:4` senkron tutulur.

## Release yayınlama (kalıcı kural)

PR'lar merge edildikten sonra, kullanıcı istediğinde release şu sırayla yapılır:

1. **Doğrula.** `pytest -q` + `ruff check` temiz olmalı; `pyproject.toml` ile
   `src/castmane/__init__.py:4` aynı sürümü göstermeli.
2. **Build.** `./packaging/build-appimage.sh` → `dist/CastMane-<version>-x86_64.AppImage`.
   Script `.venv-appimage` kullanır, normal `.venv`'i kirletmez.
   `appimagetool` `packaging/tools/` altında cache'lenir; zaten varsa yeniden indirme.
3. **Smoke test.** `./dist/CastMane-*.AppImage --help` ve
   `QT_QPA_PLATFORM=offscreen ./dist/CastMane-*.AppImage` ile açılışı doğrula.
4. **Yayınla.**
   ```sh
   gh release create v<version> dist/CastMane-<version>-x86_64.AppImage \
     --title "CastMane v<version>" --notes-file <notlar>
   ```
   Tag biçimi `v<version>` (sürümün başına `v` ile: `v0.9.10`).
5. **Notlar:** Soğuk bir changelog değil, **ne yapıldığını anlatan** bir metin yaz. Her düzeltme
   için: hata nasıl bulundu, neden oluştu, ne değişti, gerçek ortamda nasıl doğrulandı (ölçüm
   rakamlarıyla), ve kullanıcıya etkisi ne. Bilinen/çözülmemiş sorunları açıkça belirt.
   Kullanıcı bunu "ne yaptığımı anlat" diye özellikle istedi — teknik liste değil, anlatı.
6. `.AppImage`, `AppDir/`, `build/`, `dist/` commit'e **giremez**, sadece release asset'i olur.

## İletişim

- Kullanıcıyla hep Türkçe konuş. Kısa ve net ol.
- Kod referansı verirken `dosya:satır` formatı kullan.
