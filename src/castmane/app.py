"""Qt ana pencere - Rec/Stop + sure + durum."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .backends import create_backend, session_is_wayland
from .config import AppConfig

STYLESHEET = """
QMainWindow, QWidget {
    background-color: #15171c;
    color: #e6e8ec;
    font-family: "Noto Sans", "DejaVu Sans", "Liberation Sans", sans-serif;
    font-size: 13px;
}
QFrame#Card {
    background-color: #1e222a;
    border: 1px solid #2a303b;
    border-radius: 12px;
}
QFrame#AccentBar {
    background-color: #3d8a53;
    border-radius: 1px;
}
QFrame#Sep {
    background-color: #2a303b;
    border: none;
    max-height: 1px;
}
QLabel#StatusLabel {
    color: #9aa4b2;
    font-size: 12px;
}
QLabel#SectionTitle {
    color: #aeb6c2;
    font-size: 11px;
    font-weight: bold;
}
QLabel#OutputLabel {
    color: #7f8896;
    font-size: 11px;
}
QLabel#TimeLabel {
    color: #f2f4f8;
    font-size: 46px;
    font-weight: bold;
}
QLabel#TimeLabel[recording="true"] {
    color: #ff5f56;
}
QLabel#FieldLabel {
    color: #9aa4b2;
}
QPushButton {
    background-color: #272d38;
    border: 1px solid #333b48;
    border-radius: 8px;
    padding: 7px 14px;
    color: #e6e8ec;
}
QPushButton:hover {
    background-color: #2f3745;
    border-color: #404a5a;
}
QPushButton:pressed {
    background-color: #232935;
}
QPushButton:disabled {
    background-color: #1c2029;
    color: #565e6b;
    border-color: #262c36;
}
QPushButton#RecordButton {
    background-color: #2f6b3f;
    border: 1px solid #3d8a53;
    border-radius: 10px;
    font-size: 16px;
    font-weight: bold;
    padding: 12px 24px;
    color: #ffffff;
}
QPushButton#RecordButton:hover {
    background-color: #378049;
    border-color: #4aa066;
}
QPushButton#RecordButton:pressed {
    background-color: #265932;
}
QPushButton#RecordButton[recording="true"] {
    background-color: #8c2f2a;
    border-color: #a83c35;
}
QPushButton#RecordButton[recording="true"]:hover {
    background-color: #9d3630;
}
QPushButton#QuitButton {
    background-color: transparent;
    border-color: #333b48;
    color: #9aa4b2;
}
QPushButton#QuitButton:hover {
    background-color: #272d38;
    color: #e6e8ec;
}
QComboBox {
    background-color: #272d38;
    border: 1px solid #333b48;
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
}
QComboBox:hover {
    border-color: #404a5a;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: #1f232b;
    border: 1px solid #333b48;
    selection-background-color: #2f6b3f;
    selection-color: #ffffff;
    padding: 4px;
}
QSpinBox {
    background-color: #272d38;
    border: 1px solid #333b48;
    border-radius: 8px;
    padding: 5px 8px;
}
QSpinBox:hover {
    border-color: #404a5a;
}
QCheckBox {
    spacing: 8px;
    background: transparent;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid #333b48;
    background-color: #272d38;
}
QCheckBox::indicator:hover {
    border-color: #404a5a;
}
QCheckBox::indicator:checked {
    background-color: #2f6b3f;
    border-color: #3d8a53;
}
QCheckBox:disabled {
    color: #565e6b;
}
"""


def _section_header(text: str) -> QWidget:
    """Kart basligi: ince renk cubugu + kucuk harf etiketi."""
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    bar = QFrame()
    bar.setObjectName("AccentBar")
    bar.setFixedSize(3, 12)
    title = QLabel(text)
    title.setObjectName("SectionTitle")
    row.addWidget(bar)
    row.addWidget(title)
    row.addStretch(1)
    return box


def _separator() -> QFrame:
    line = QFrame()
    line.setObjectName("Sep")
    line.setFixedHeight(1)
    return line


def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("FieldLabel")
    return lbl


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig | None = None) -> None:
        super().__init__()
        self.cfg = cfg or AppConfig()
        self.rec = create_backend(self.cfg)
        self.setWindowTitle("CastMane")
        self.resize(460, 500)
        self.setMinimumSize(420, 460)
        self.setStyleSheet(STYLESHEET)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        # --- Ust kart: kronometre + durum ---
        self.time_lbl = QLabel("00:00")
        self.time_lbl.setObjectName("TimeLabel")
        self.time_lbl.setAlignment(Qt.AlignCenter)
        self.time_lbl.setProperty("recording", False)

        self.status_lbl = QLabel(f"Hazir [{self.rec.name}]. Cikti: ~/Videos/CastMane")
        self.status_lbl.setObjectName("StatusLabel")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setWordWrap(True)

        top = QFrame()
        top.setObjectName("Card")
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(20, 22, 20, 18)
        top_layout.setSpacing(6)
        top_layout.addWidget(self.time_lbl)
        top_layout.addWidget(self.status_lbl)
        outer.addWidget(top)

        # --- Kayit butonu ---
        self.rec_btn = QPushButton("● Kayda Başla")
        self.rec_btn.setObjectName("RecordButton")
        self.rec_btn.setProperty("recording", False)
        self.rec_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.rec_btn.setCursor(Qt.PointingHandCursor)
        self.rec_btn.clicked.connect(self.toggle)
        outer.addWidget(self.rec_btn)

        # --- Kaynak ve kalite karti ---
        self.mode_cb = QComboBox()
        self.mode_cb.addItem("Tam Ekran", "fullscreen")
        self.mode_cb.addItem("Pencere", "window")
        self.mode_cb.addItem("Sor / Bölge Seç", "ask")
        idx = self.mode_cb.findData(self.cfg.capture_mode)
        if idx >= 0:
            self.mode_cb.setCurrentIndex(idx)
        self.mode_cb.currentIndexChanged.connect(self._on_mode_changed)

        self.quality_cb = QComboBox()
        self.quality_cb.addItem("Taslak (hafif)", "draft")
        self.quality_cb.addItem("Dengeli", "balanced")
        self.quality_cb.addItem("Yüksek", "high")
        idx = self.quality_cb.findData(self.cfg.quality_preset)
        if idx >= 0:
            self.quality_cb.setCurrentIndex(idx)
        self.quality_cb.currentIndexChanged.connect(self._on_quality_changed)

        src_card = QFrame()
        src_card.setObjectName("Card")
        src_layout = QGridLayout(src_card)
        src_layout.setContentsMargins(18, 16, 18, 18)
        src_layout.setHorizontalSpacing(12)
        src_layout.setVerticalSpacing(8)
        src_layout.setColumnMinimumWidth(0, 78)

        src_layout.addWidget(_section_header("KAYIT AYARLARI"), 0, 0, 1, 2)
        src_layout.addWidget(_separator(), 1, 0, 1, 2)
        src_layout.addWidget(_field_label("Kaynak:"), 2, 0)
        src_layout.addWidget(self.mode_cb, 2, 1)
        src_layout.addWidget(_field_label("Kalite:"), 3, 0)
        src_layout.addWidget(self.quality_cb, 3, 1)
        outer.addWidget(src_card)

        # --- Ses karti ---
        self.audio_cb = QCheckBox("Sesli kaydet (mikrofon)")
        self.audio_cb.setChecked(self.cfg.audio_enabled)
        self.audio_cb.toggled.connect(self._on_audio_toggled)

        audio_row = QHBoxLayout()
        audio_row.setSpacing(10)
        audio_row.addWidget(_field_label("Ses kazancı:"))
        self.gain_spin = QSpinBox()
        self.gain_spin.setPrefix("%")
        self.gain_spin.setRange(10, 500)
        self.gain_spin.setSingleStep(10)
        self.gain_spin.setValue(int(self.cfg.audio_gain * 100))
        self.gain_spin.valueChanged.connect(self._on_gain_changed)
        self.gain_spin.setFixedWidth(110)
        audio_row.addWidget(self.gain_spin)
        audio_row.addStretch(1)

        audio_card = QFrame()
        audio_card.setObjectName("Card")
        audio_layout = QVBoxLayout(audio_card)
        audio_layout.setContentsMargins(18, 16, 18, 18)
        audio_layout.setSpacing(8)
        audio_layout.addWidget(_section_header("SES"))
        audio_layout.addWidget(_separator())
        audio_layout.addWidget(self.audio_cb)
        audio_layout.addLayout(audio_row)
        outer.addWidget(audio_card)

        # --- X11 sabit bolge karti: W/H sifirsa tam ekran, yoksa WxH+X+Y. ---
        self.region_spins: dict[str, QSpinBox] = {}
        region_row = QHBoxLayout()
        region_row.setSpacing(8)
        region_row.addWidget(_field_label("Bölge (X11):"))
        for key, maximum, value in (
            ("x", 10000, self.cfg.region_x),
            ("y", 10000, self.cfg.region_y),
            ("w", 10000, self.cfg.region_w),
            ("h", 10000, self.cfg.region_h),
        ):
            spin = QSpinBox()
            spin.setPrefix(f"{key.upper()}=")
            spin.setRange(0, maximum)
            spin.setValue(value)
            spin.valueChanged.connect(self._on_region_changed)
            spin.setMinimumWidth(74)
            spin.setAlignment(Qt.AlignCenter)
            self.region_spins[key] = spin
            region_row.addWidget(spin)
        region_row.addStretch(1)

        region_hint = QLabel("Boş/0 değerler tam ekran demektir")
        region_hint.setObjectName("OutputLabel")

        region_card = QFrame()
        region_card.setObjectName("Card")
        region_layout = QVBoxLayout(region_card)
        region_layout.setContentsMargins(18, 16, 18, 18)
        region_layout.setSpacing(8)
        region_layout.addWidget(_section_header("BÖLGE"))
        region_layout.addWidget(_separator())
        region_layout.addLayout(region_row)
        region_layout.addWidget(region_hint)
        outer.addWidget(region_card)

        outcome_lbl = QLabel(
            "Dosyalar ~/Videos/CastMane içine zaman damgasıyla kaydedilir"
        )
        outcome_lbl.setObjectName("OutputLabel")
        outcome_lbl.setAlignment(Qt.AlignCenter)
        outcome_lbl.setWordWrap(True)
        outer.addWidget(outcome_lbl)

        # --- Alt butonlar ---
        self.pause_btn = QPushButton("⏸ Duraklat")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(self.toggle_pause)

        quit_btn = QPushButton("Çıkış")
        quit_btn.setObjectName("QuitButton")
        quit_btn.setCursor(Qt.PointingHandCursor)
        quit_btn.clicked.connect(self.close)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(self.pause_btn, 1)
        btn_row.addWidget(quit_btn)
        outer.addLayout(btn_row)

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.tick)

        if not session_is_wayland():
            self.status_lbl.setText(
                "X11 algilandi: ffmpeg backend aktif. "
                "Wayland oturumunda portal backend devreye girer."
            )

    def _set_recording_ui(self, recording: bool) -> None:
        """Kayit durumunu buton/sayaç rengine yansitir."""
        self.rec_btn.setProperty("recording", recording)
        self.time_lbl.setProperty("recording", recording)
        for w in (self.rec_btn, self.time_lbl):
            w.style().unpolish(w)
            w.style().polish(w)

    def toggle(self) -> None:
        if not self.rec.state.active:
            try:
                final = self.rec.start()
            except FileNotFoundError:
                self.status_lbl.setText("ffmpeg/gst-launch bulunamadi!")
                return
            except Exception as e:  # noqa: BLE001
                self.status_lbl.setText(f"Başlatılamadı: {e}")
                return
            tmp = self.rec.state.tmp_path
            self.status_lbl.setText(f"Kaydediliyor -> {tmp.name if tmp else final.name}")
            self.rec_btn.setText("■ Durdur")
            self.audio_cb.setEnabled(False)
            self.gain_spin.setEnabled(False)
            self.mode_cb.setEnabled(False)
            self.quality_cb.setEnabled(False)
            self._set_region_enabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("⏸ Duraklat")
            self._set_recording_ui(True)
            self.timer.start()
        else:
            out = self.rec.stop()
            self.timer.stop()
            self.audio_cb.setEnabled(True)
            self.gain_spin.setEnabled(True)
            self.mode_cb.setEnabled(True)
            self.quality_cb.setEnabled(True)
            self._set_region_enabled(True)
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("⏸ Duraklat")
            if out:
                self.status_lbl.setText(f"Kurtarildi: {out}")
            else:
                self.status_lbl.setText(f"Hata: {self.rec.state.last_error}")
            self.rec_btn.setText("● Kayda Başla")
            self._set_recording_ui(False)

    def _on_audio_toggled(self, checked: bool) -> None:
        self.cfg.audio_enabled = checked
        # Backend cfg'yi referans tutar; kayit sirasi degisiklik engellenir.
        try:
            self.rec.cfg.audio_enabled = checked
        except AttributeError:
            pass

    def _on_gain_changed(self, pct: int) -> None:
        gain = pct / 100.0
        self.cfg.audio_gain = gain
        try:
            self.rec.cfg.audio_gain = gain
        except AttributeError:
            pass

    def toggle_pause(self) -> None:
        if not self.rec.state.active:
            return
        try:
            if self.rec.state.paused:
                self.rec.resume()
                self.pause_btn.setText("⏸ Duraklat")
                tmp = self.rec.state.tmp_path
                self.status_lbl.setText(
                    f"Kaydediliyor -> {tmp.name if tmp else ''}"
                )
            else:
                self.rec.pause()
                self.pause_btn.setText("▶ Sürdür")
                self.status_lbl.setText("Duraklatıldı — süre işlemiyor")
        except Exception as e:  # noqa: BLE001
            self.status_lbl.setText(f"Duraklatma hatası: {e}")

    def _on_quality_changed(self, idx: int) -> None:
        preset = self.quality_cb.itemData(idx)
        if not preset:
            return
        try:
            self.cfg.apply_quality_preset(preset)
        except ValueError:
            return
        # Backend cfg'yi referans tutar; sonraki kayda uygulanir.
        try:
            self.rec.cfg.apply_quality_preset(preset)
        except (AttributeError, ValueError):
            pass

    def _on_mode_changed(self, idx: int) -> None:
        mode = self.mode_cb.itemData(idx)
        if not mode:
            return
        self.cfg.capture_mode = mode
        try:
            self.rec.cfg.capture_mode = mode
        except AttributeError:
            pass

    def _on_region_changed(self) -> None:
        vals = {k: s.value() for k, s in self.region_spins.items()}
        self.cfg.region_x = vals["x"]
        self.cfg.region_y = vals["y"]
        self.cfg.region_w = vals["w"]
        self.cfg.region_h = vals["h"]
        try:
            self.rec.cfg.region_x = vals["x"]
            self.rec.cfg.region_y = vals["y"]
            self.rec.cfg.region_w = vals["w"]
            self.rec.cfg.region_h = vals["h"]
        except AttributeError:
            pass

    def _set_region_enabled(self, enabled: bool) -> None:
        for spin in self.region_spins.values():
            spin.setEnabled(enabled)

    def tick(self) -> None:
        if self.rec.state.active:
            s = int(self.rec.elapsed)
            self.time_lbl.setText(f"{s // 60:02d}:{s % 60:02d}")
        if self.rec.state.last_error and not self.rec.state.active:
            self.status_lbl.setText(f"Hata: {self.rec.state.last_error}")
            self.rec_btn.setText("● Kayda Başla")
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("⏸ Duraklat")
            self.audio_cb.setEnabled(True)
            self.gain_spin.setEnabled(True)
            self.mode_cb.setEnabled(True)
            self.quality_cb.setEnabled(True)
            self._set_region_enabled(True)
            self._set_recording_ui(False)
            self.timer.stop()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.rec.state.active:
            self.rec.stop()
        super().closeEvent(event)
