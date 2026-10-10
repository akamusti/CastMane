"""Qt ana pencere - MVP: Rec/Stop + sure + durum."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
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
        self.resize(420, 200)

        self.status_lbl = QLabel(f"Hazir [{self.rec.name}]. Cikti: ~/Videos/CastMane")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.time_lbl = QLabel("00:00")
        self.time_lbl.setAlignment(Qt.AlignCenter)
        self.time_lbl.setStyleSheet("font-size: 42px; font-weight: bold;")

        self.rec_btn = QPushButton("● Kayda Basla")
        self.rec_btn.setStyleSheet("font-size: 16px; padding: 10px;")
        self.rec_btn.clicked.connect(self.toggle)

        quit_btn = QPushButton("Cikis")
        quit_btn.clicked.connect(self.close)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.rec_btn)
        btn_row.addWidget(quit_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.time_lbl)
        layout.addWidget(self.status_lbl)
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
            self.timer.start()
        else:
            out = self.rec.stop()
            self.timer.stop()
            if out:
                self.status_lbl.setText(f"Kurtarildi: {out}")
            else:
                self.status_lbl.setText(f"Hata: {self.rec.state.last_error}")
            self.rec_btn.setText("● Kayda Basla")

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
