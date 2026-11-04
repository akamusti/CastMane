# CastMane — UI Güzelleştirme Roadmap (Cesur Yeni Yön)

> Skor sistemi: `docs/ROADMAP.md`'de tanımlı rubric. Her faz sonunda skor yeniden ölçülür.

## UI Score Rubric (sabit)

| Kriter | Weight | Mevcut | Hedef |
|---|---|---|---|
| Hiyerarşi ve oran | 25 | 16 | 22 |
| Boşluk ve ritim | 20 | 14 | 17 |
| Tipografi ve kontrast | 15 | 11 | 13 |
| Durum dili (READY/REC) | 15 | 13 | 14 |
| Tutarlılık / sistem | 15 | 12 | 14 |
| Detay / dokunuş | 10 | 6 | 8 |
| **Toplam** | **100** | **62** | **85+** |

## Cesur Yeni Yön — Fazlar

### Faz 1 — Varsayılan koyu tema + kontrast
- `DEFAULT_THEME = "dark"` (mevcut dark paleti zemin)
- `TEXT_FAINT` koyulaştır (light temada soluk hint metinleri)
- Focus halkası görünür (`QLineEdit:focus`, `QSpinBox:focus`, `QComboBox:focus`)
- REC pulsing dot (StatusDot'a animation)

### Faz 2 — Preview dolgu + denge
- `ScreenView` min/max 150/180 kaldır, 16:9 oran
- Kamera önizlemesiyle hizalı kartlar
- Studio sayfası boşluk dengesi

### Faz 3 — Native Sources listesini sistem dışı yap
- `QListWidget` yerine custom toggle satırları (checkbox yerine)
- Kaynak durumu tutarlılığı

### Faz 4 — Boş Controls kartını doldur
- REC süresi + kaynak özeti (sayaç/kontrol bilgisi)
- Studio controls kartı içeriği

### Faz 5 — Motion
- Buton hover/press `QPropertyAnimation`
- Pause/replay animasyonları
- QPA okunur görünüm

## Durum

- Faz 1: ✅ Tamamlandı
- Faz 2: ✅ Tamamlandı
- Faz 3: ✅ Tamamlandı
- Faz 4: ✅ Tamamlandı
- Faz 5: ⏳ Başlanmadı

## Skor Kaydı

| Tarih | Faz | Skor |
|---|---|---|
| 2026-11-04 | Baseline | 62/100 |

Generated with opencode/beam-free
