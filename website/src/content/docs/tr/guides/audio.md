---
title: Ses
description: Yazılımsal kazançlı mikrofon ve sistem sesi kaydı.
---

Penceredeki **Sesli kaydet (mikrofon)** kutusunu işaretleyin ya da kodla verin:

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

:::tip[Sistem sesi cılız mı geliyor?]
Monitor kaynaklarında mikrofonlardaki gibi giriş yükseltmesi yoktur, o yüzden
sistem sesi mikrofon kaydına göre çok daha kısık duyulur. Penceredeki
**Ses kazancı (%)** ayarını yükseltin ya da kodla verin
(`AppConfig(audio_gain=2.0)` ≈ +6 dB, `3.0` ≈ +9,5 dB). Kırpılma olmaması
için `5.0` üstüne çıkmayın.
:::
