---
title: Yapılandırma
description: Kalite ön ayarları ve yakalama kaynağı seçenekleri.
---

## Duraklatma ve kalite ön ayarları

Kayıt sırasında **Duraklat**'a basarak encoder'ı dondurun (`SIGSTOP`); süre
durur ve duraklatılan aralık görüntüye girmez. **Sürdür** aynı dosyaya devam
eder.

```python
from castmane.config import AppConfig
cfg = AppConfig()
cfg.apply_quality_preset("high")  # "draft" | "balanced" | "high"
```

| Ön ayar | fps | Bit hızı |
| ------- | --- | -------- |
| Taslak  | 24  | 4 Mbps   |
| Dengeli | 30  | 8 Mbps   |
| Yüksek  | 60  | 16 Mbps  |

## Yakalama kaynağı

```python
from castmane.config import AppConfig
cfg = AppConfig(capture_mode="window")  # "fullscreen" | "window" | "ask"
# X11 sabit bölge (0 = tam ekran):
# cfg = AppConfig(region_x=100, region_y=200, region_w=1280, region_h=720)
# X11 tek pencere (kimlik `xwininfo` çıktısından):
# cfg = AppConfig(capture_mode="window", window_id=123456)
```

Wayland'da `window` / `ask` portal diyafonunu monitörden pencereye çevirir
(ya da ikisini birden sorar). X11'de `ask` fareyle bölge seçtirir
(`ffmpeg -select_region`), `region_*` / `window_id` ise betiklenebilir kontrol
verir. Crash-güvenliği değişmez: pencere ve bölge kayıtları da `.part` +
atomik rename hattından geçer.
