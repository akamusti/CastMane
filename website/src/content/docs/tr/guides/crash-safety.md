---
title: Crash-güvenliği
description: CastMane görüntünüzün çöküşten sağ çıkmasını nasıl garanti eder.
---

CastMane tek bir ilke üzerine kurulu: **çöküş, görüntüye mal olmamalı.**

## Koruma katmanları

| Katman       | Mekanizma                                                                                          |
| ------------ | -------------------------------------------------------------------------------------------------- |
| Kapsayıcı    | MKV staging (`matroskamux` eksik damgaları tolere eder), düzgün duruşta kayıpsız `ffmpeg -c copy` |
| Dosya taşıma | `X.mp4.part` dosyasına yaz, düzgün duruşta `os.replace()` ile `X.mp4` yap                         |
| Kapatma      | `SIGINT` → bekle → `SIGTERM` → `SIGKILL` kademesi                                                  |
| İzleme       | Encoder izcisi erken ölümleri son log satırlarıyla raporlar                                        |

## Kanıtı kendiniz tekrarlayın

Canlı bir MKV kaydını öldürüp remux edin:

```bash
gst-launch-1.0 videotestsrc is-live=true ! videoconvert ! openh264enc \
  ! h264parse ! matroskamux ! filesink location=kanit.mkv.part &
sleep 4; kill -9 $!
ffprobe -v error -show_entries stream=codec_name kanit.mkv.part
ffmpeg -y -v error -i kanit.mkv.part -c copy kanit.mp4
ffprobe -v error -show_entries stream=codec_name,duration kanit.mp4
```

`.part` dosyası `kill -9` sonrasında bile tamamen oynatılabilir kalır
(`h264`, `ffprobe` ile denetlendi).
