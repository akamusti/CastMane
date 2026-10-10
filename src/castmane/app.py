"""Qt ana pencere - MVP: Rec/Stop + sure + durum."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .backends import create_backend, session_is_wayland
from .config import AppConfig


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig | None = None) -> None:
        super().__init__()
        self.cfg = cfg or AppConfig()
        self.rec = create_backend(self.cfg)
        self.setWindowTitle("CastMane")
        self.resize(420, 280)

        self.status_lbl = QLabel(f"Hazir [{self.rec.name}]. Cikti: ~/Videos/CastMane")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.time_lbl = QLabel("00:00")
        self.time_lbl.setAlignment(Qt.AlignCenter)
        self.time_lbl.setStyleSheet("font-size: 42px; font-weight: bold;")

        self.rec_btn = QPushButton("● Kayda Basla")
        self.rec_btn.setStyleSheet("font-size: 16px; padding: 10px;")
        self.rec_btn.clicked.connect(self.toggle)

        self.audio_cb = QCheckBox("Sesli kaydet (mikrofon)")
        self.audio_cb.setChecked(self.cfg.audio_enabled)
        self.audio_cb.toggled.connect(self._on_audio_toggled)

        self.mode_cb = QComboBox()
        self.mode_cb.addItem("Tam Ekran", "fullscreen")
        self.mode_cb.addItem("Pencere", "window")
        self.mode_cb.addItem("Sor / Bölge Seç", "ask")
        idx = self.mode_cb.findData(self.cfg.capture_mode)
        if idx >= 0:
            self.mode_cb.setCurrentIndex(idx)
        self.mode_cb.currentIndexChanged.connect(self._on_mode_changed)

        # X11 sabit bolge: W/H sifirsa tam ekran, yoksa WxH+X+Y.
        self.region_spins: dict[str, QSpinBox] = {}
        region_row = QHBoxLayout()
        region_row.addWidget(QLabel("Bölge (X11):"))
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
            self.region_spins[key] = spin
            region_row.addWidget(spin)

        quit_btn = QPushButton("Cikis")
        quit_btn.clicked.connect(self.close)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.rec_btn)
        btn_row.addWidget(quit_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.time_lbl)
        layout.addWidget(self.status_lbl)
        layout.addWidget(self.audio_cb)
        layout.addWidget(self.mode_cb)
        layout.addLayout(region_row)
        layout.addLayout(btn_row)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.tick)

        if not session_is_wayland():
            self.status_lbl.setText(
                "X11 algilandi: ffmpeg backend aktif. "
                "Wayland oturumunda portal backend devreye girer."
            )

    def toggle(self) -> None:
        if not self.rec.state.active:
            try:
                final = self.rec.start()
            except FileNotFoundError:
                self.status_lbl.setText("ffmpeg/gst-launch bulunamadi!")
                return
            except Exception as e:  # noqa: BLE001
                self.status_lbl.setText(f"Baslatilamadi: {e}")
                return
            tmp = self.rec.state.tmp_path
            self.status_lbl.setText(f"Kaydediliyor -> {tmp.name if tmp else final.name}")
            self.rec_btn.setText("■ Durdur")
            self.audio_cb.setEnabled(False)
            self.mode_cb.setEnabled(False)
            self._set_region_enabled(False)
            self.timer.start()
        else:
            out = self.rec.stop()
            self.timer.stop()
            self.audio_cb.setEnabled(True)
            self.mode_cb.setEnabled(True)
            self._set_region_enabled(True)
            if out:
                self.status_lbl.setText(f"Kurtarildi: {out}")
            else:
                self.status_lbl.setText(f"Hata: {self.rec.state.last_error}")
            self.rec_btn.setText("● Kayda Basla")

    def _on_audio_toggled(self, checked: bool) -> None:
        self.cfg.audio_enabled = checked
        # Backend cfg'yi referans tutar; kayit sirasi degisiklik engellenir.
        try:
            self.rec.cfg.audio_enabled = checked
        except AttributeError:
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
            self.rec_btn.setText("● Kayda Basla")
            self.timer.stop()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.rec.state.active:
            self.rec.stop()
        super().closeEvent(event)
