---
title: Kullanım
description: CastMane ile kayıt, duraklatma, durdurma ve kurtarma.
---

## Kayıt

![CastMane ana pencere — Yakalama ayarları](../../../../assets/screenshots/main-capture-tr.png)

1. **Uygulamayı başlatın.** Durum satırı aktif backend'i gösterir, örn.
   `Hazır [portal (Wayland)]`.
2. **Kaynak seçin:** Tam Ekran, Pencere ya da Sor / Bölge Seç.
   Wayland'da sistem diyafonu monitörleri veya pencereleri listeler; X11'de
   *Sor* sürükle-seç çerçevesi açar.
3. **Kayda basın.** Wayland'da sistemin ekran paylaşım diyafonu açılır —
   monitörü ya da pencereyi seçip onaylayın (180 saniye süreniz var).

Kayıt sırasında süre kırmızıya döner ve düğme Durdur olur:

![CastMane kayıt sırasında — süre ve kırmızı Durdur düğmesi](../../../../assets/screenshots/main-recording-light.png)

4. **Durdur'a basın.** Bitmiş dosya `~/Videos/CastMane` altında
   `castmane_YYYY-MM-DD_HH-MM-SS.mp4` olarak durur.

## Dil

Arayüz varsayılan olarak İngilizcedir. Türkçeye geçmek için Kayıt
Ayarları'ndaki **Dil** menüsünden **Türkçe**'yi seçin.
Kod ile: `AppConfig(language="tr")`.

## Duraklatma ve sürdürme

Kayıt sırasında **Duraklat**'a basarak encoder'ı dondurun (`SIGSTOP`); süre
durur ve duraklatılan aralık görüntüye girmez. **Sürdür** aynı dosyaya devam
eder. Duraklatılmışken durdurma yapılırsa önce sürdürme yapılır, böylece
trailer her zaman temiz yazılır.

## Yarıda kesilen kaydı kurtarma

Aynı klasördeki `*.mkv.part` (Wayland) ya da `*.mp4.part` (X11) dosyasına
bakın — aynen oynatılır. Yeniden adlandırmanız yeterli (Wayland'da isterseniz
MP4'e kendiniz çevirin):

```bash
ffmpeg -i dosya.mkv.part -c copy dosya.mp4
```

Neden çalıştığını [Crash-güvenliği](../guides/crash-safety/) sayfasında
anlattık.
