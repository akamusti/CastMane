---
title: Sorun giderme
description: Wayland ve X11'de sık görülen CastMane sorunları.
---

## Uygulama bir şeylerin eksik olduğunu söylüyor

CastMane, kurulması gereken paketi adıyla söyleyen bir pencere gösterir.
Dağıtımınıza uygun komutlar için [Kurulum](/tr/getting-started/installation/)
sayfasına bakın.

## Ekran paylaşım diyafonu açılmıyor (Wayland)

- `xdg-desktop-portal` servisinin ScreenCast destekli çalıştığından emin olun
  (KDE ve GNOME sağlar).
- Az bilinen compositor'lerde (örn. minimal wlroots kurulumları)
  `xdg-desktop-portal-wlr` kurup compositor'ünüzün portal satırını yapılandırın.

## Kayıt diyafonu zaman aşımına uğruyor

Sistemin ekran paylaşım diyafonunu onaylamak için 180 saniyeniz var. Süre
dolarsa **Kayıt**'a yeniden basın.

## Çıktı dosyası yok

- Bitmiş dosyalar `~/Videos/CastMane` altında zaman damgalı
  `castmane_*.mp4` olarak durur.
- Uygulama öldürüldüyse aynı klasördeki `*.mkv.part` (Wayland) ya da
  `*.mp4.part` (X11) dosyasına bakın — bkz.
  [Kullanım](/tr/getting-started/usage/#yarıda-kesilen-kaydı-kurtarma).

## Hata bildirimi

Issue ve pull request'lere
[akamusti/CastMane](https://github.com/akamusti/CastMane) adresinde açığız.
Kayıp ya da bozuk görüntü bildirimlerine `ffprobe` çıktısı ve tekrarlama
adımlarını ekleyin — crash-güvenliği bu uygulamanın varlık nedeni.
