"""Qt main window - Rec/Stop + timer + status."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .backends import create_backend, session_is_wayland
from .config import AppConfig
from .i18n import SUPPORTED_LANGUAGES, get as _get, normalize
from .theme import (
    ACCENT_CYAN,
    ACCENT_GRADIENT,
    ACCENT_INDIGO,
    ACCENT_PURPLE,
    BG_BASE,
    BG_CARD,
    BG_INPUT,
    BORDER,
    BORDER_HOVER,
    TEXT_FAINT,
    TEXT_MAIN,
    TEXT_MUTED,
    logo_path,
)

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_BASE};
    color: {TEXT_MAIN};
    font-family: "Noto Sans", "DejaVu Sans", "Liberation Sans", sans-serif;
    font-size: 13px;
}}
QFrame#Card {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#AccentBar {{
    background-color: {ACCENT_GRADIENT};
    border-radius: 1px;
}}
QFrame#Sep {{
    background-color: {BORDER};
    border: none;
    max-height: 1px;
}}
QLabel#StatusLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#SectionTitle {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: bold;
}}
QLabel#BrandTitle {{
    color: {TEXT_MAIN};
    font-size: 18px;
    font-weight: bold;
}}
QLabel#BrandSubtitle {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QLabel#OutputLabel {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QLabel#TimeLabel {{
    color: {TEXT_MAIN};
    font-size: 40px;
    font-weight: bold;
}}
QLabel#TimeLabel[recording="true"] {{
    color: {ACCENT_PURPLE};
}}
QLabel#FieldLabel {{
    color: {TEXT_MUTED};
}}
QPushButton {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT_MAIN};
}}
QPushButton:hover {{
    background-color: #2D3459;
    border-color: {BORDER_HOVER};
}}
QPushButton:pressed {{
    background-color: #20264A;
}}
QPushButton:disabled {{
    background-color: #1A1F3A;
    color: #565E86;
    border-color: {BORDER};
}}
QPushButton#RecordButton {{
    background-color: {ACCENT_GRADIENT};
    border: 1px solid {ACCENT_CYAN};
    border-radius: 10px;
    font-size: 16px;
    font-weight: bold;
    padding: 12px 24px;
    color: #ffffff;
}}
QPushButton#RecordButton:hover {{
    background-color: {ACCENT_CYAN};
    border-color: #7AD6FF;
}}
QPushButton#RecordButton:pressed {{
    background-color: {ACCENT_INDIGO};
}}
QPushButton#RecordButton[recording="true"] {{
    background-color: #8c2f2a;
    border-color: #a83c35;
}}
QPushButton#RecordButton[recording="true"]:hover {{
    background-color: #9d3630;
}}
QPushButton#QuitButton {{
    background-color: transparent;
    border-color: {BORDER};
    color: {TEXT_MUTED};
}}
QPushButton#QuitButton:hover {{
    background-color: {BG_INPUT};
    color: {TEXT_MAIN};
}}
QComboBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 20px;
}}
QComboBox:hover {{
    border-color: {BORDER_HOVER};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_INDIGO};
    selection-color: #ffffff;
    padding: 4px;
}}
QSpinBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px 8px;
}}
QSpinBox:hover {{
    border-color: {BORDER_HOVER};
}}
QCheckBox {{
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid {BORDER};
    background-color: {BG_INPUT};
}}
QCheckBox::indicator:hover {{
    border-color: {BORDER_HOVER};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT_GRADIENT};
    border-color: {ACCENT_CYAN};
}}
QCheckBox:disabled {{
    color: #565E86;
}}
"""

LANGUAGE_LABELS = {"en": "English", "tr": "Türkçe"}


def _section_header(text: str) -> QWidget:
    """Card title: thin accent bar + small-caps label."""
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
        self.cfg.language = normalize(self.cfg.language)
        self.rec = create_backend(self.cfg)
        self.setWindowTitle("CastMane")
        self.resize(460, 640)
        self.setMinimumSize(320, 480)
        self.setStyleSheet(STYLESHEET)
        icon_path = logo_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        self.setCentralWidget(scroll)

        root = QWidget()
        scroll.setWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        # --- Brand row: logo + name ---
        brand = QWidget()
        brand.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        brand_row = QHBoxLayout(brand)
        brand_row.setContentsMargins(2, 0, 2, 0)
        brand_row.setSpacing(12)
        self.logo_lbl = QLabel()
        self.logo_lbl.setFixedSize(44, 44)
        self.logo_lbl.setScaledContents(True)
        self.logo_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if icon_path:
            self.logo_lbl.setPixmap(QPixmap(icon_path))
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(0)
        brand_title = QLabel("CastMane")
        brand_title.setObjectName("BrandTitle")
        brand_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.brand_sub = QLabel()
        self.brand_sub.setObjectName("BrandSubtitle")
        self.brand_sub.setWordWrap(True)
        self.brand_sub.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        brand_text.addWidget(brand_title)
        brand_text.addWidget(self.brand_sub)
        brand_row.addWidget(self.logo_lbl)
        brand_row.addLayout(brand_text, 1)
        outer.addWidget(brand)

        # --- Top card: timer + status ---
        self.time_lbl = QLabel("00:00")
        self.time_lbl.setObjectName("TimeLabel")
        self.time_lbl.setAlignment(Qt.AlignCenter)
        self.time_lbl.setProperty("recording", False)
        self.time_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.time_lbl.setMinimumWidth(0)

        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("StatusLabel")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        top = QFrame()
        top.setObjectName("Card")
        top.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(20, 22, 20, 18)
        top_layout.setSpacing(6)
        top_layout.addWidget(self.time_lbl)
        top_layout.addWidget(self.status_lbl)
        outer.addWidget(top)

        # --- Record button ---
        self.rec_btn = QPushButton()
        self.rec_btn.setObjectName("RecordButton")
        self.rec_btn.setProperty("recording", False)
        self.rec_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.rec_btn.setMinimumWidth(0)
        self.rec_btn.setCursor(Qt.PointingHandCursor)
        self.rec_btn.clicked.connect(self.toggle)
        outer.addWidget(self.rec_btn)

        # --- Source & quality card ---
        self.mode_cb = QComboBox()
        self.mode_cb.currentIndexChanged.connect(self._on_mode_changed)

        self.quality_cb = QComboBox()
        self.quality_cb.currentIndexChanged.connect(self._on_quality_changed)

        self.lang_cb = QComboBox()
        for code in SUPPORTED_LANGUAGES:
            self.lang_cb.addItem(LANGUAGE_LABELS[code], code)
        self.lang_cb.setCurrentIndex(
            SUPPORTED_LANGUAGES.index(self.cfg.language)
        )
        self.lang_cb.currentIndexChanged.connect(self._on_language_changed)
        for cb in (self.mode_cb, self.quality_cb, self.lang_cb):
            cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            cb.setMinimumWidth(0)
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)

        src_card = QFrame()
        src_card.setObjectName("Card")
        src_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        src_layout = QGridLayout(src_card)
        src_layout.setContentsMargins(18, 16, 18, 18)
        src_layout.setHorizontalSpacing(12)
        src_layout.setVerticalSpacing(8)
        src_layout.setColumnStretch(0, 0)
        src_layout.setColumnStretch(1, 1)

        self.src_header = _section_header("")
        src_layout.addWidget(self.src_header, 0, 0, 1, 2)
        src_layout.addWidget(_separator(), 1, 0, 1, 2)
        self.lbl_src = _field_label("")
        self.lbl_src.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        src_layout.addWidget(self.lbl_src, 2, 0)
        src_layout.addWidget(self.mode_cb, 2, 1)
        self.lbl_q = _field_label("")
        self.lbl_q.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        src_layout.addWidget(self.lbl_q, 3, 0)
        src_layout.addWidget(self.quality_cb, 3, 1)
        self.lbl_lang = _field_label("")
        self.lbl_lang.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        src_layout.addWidget(self.lbl_lang, 4, 0)
        src_layout.addWidget(self.lang_cb, 4, 1)
        outer.addWidget(src_card)

        # --- Audio card ---
        self.audio_cb = QCheckBox()
        self.audio_cb.setChecked(self.cfg.audio_enabled)
        self.audio_cb.toggled.connect(self._on_audio_toggled)

        audio_row = QHBoxLayout()
        audio_row.setSpacing(10)
        self.lbl_gain = _field_label("")
        self.lbl_gain.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        audio_row.addWidget(self.lbl_gain)
        self.gain_spin = QSpinBox()
        self.gain_spin.setPrefix("%")
        self.gain_spin.setRange(10, 500)
        self.gain_spin.setSingleStep(10)
        self.gain_spin.setValue(int(self.cfg.audio_gain * 100))
        self.gain_spin.valueChanged.connect(self._on_gain_changed)
        self.gain_spin.setFixedWidth(100)
        self.gain_spin.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        audio_row.addWidget(self.gain_spin)
        audio_row.addStretch(1)

        audio_card = QFrame()
        audio_card.setObjectName("Card")
        audio_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        audio_layout = QVBoxLayout(audio_card)
        audio_layout.setContentsMargins(18, 16, 18, 18)
        audio_layout.setSpacing(8)
        self.audio_header = _section_header("")
        audio_layout.addWidget(self.audio_header)
        audio_layout.addWidget(_separator())
        audio_layout.addWidget(self.audio_cb)
        audio_layout.addLayout(audio_row)
        outer.addWidget(audio_card)

        # --- X11 fixed-region card: wraps 2x2 in narrow windows. ---
        self.region_spins: dict[str, QSpinBox] = {}
        region_grid = QGridLayout()
        region_grid.setSpacing(8)
        for i, (key, maximum, value) in enumerate(
            (
                ("x", 10000, self.cfg.region_x),
                ("y", 10000, self.cfg.region_y),
                ("w", 10000, self.cfg.region_w),
                ("h", 10000, self.cfg.region_h),
            )
        ):
            spin = QSpinBox()
            spin.setPrefix(f"{key.upper()}=")
            spin.setRange(0, maximum)
            spin.setValue(value)
            spin.valueChanged.connect(self._on_region_changed)
            spin.setMinimumWidth(0)
            spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            spin.setAlignment(Qt.AlignCenter)
            self.region_spins[key] = spin
            region_grid.addWidget(spin, i // 2, i % 2)

        self.region_hint = QLabel()
        self.region_hint.setObjectName("OutputLabel")
        self.region_hint.setWordWrap(True)

        region_card = QFrame()
        region_card.setObjectName("Card")
        region_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        region_layout = QVBoxLayout(region_card)
        region_layout.setContentsMargins(18, 16, 18, 18)
        region_layout.setSpacing(8)
        self.region_header = _section_header("")
        region_layout.addWidget(self.region_header)
        region_layout.addWidget(_separator())
        self.lbl_region = _field_label("")
        region_layout.addWidget(self.lbl_region)
        region_layout.addLayout(region_grid)
        region_layout.addWidget(self.region_hint)
        outer.addWidget(region_card)

        self.outcome_lbl = QLabel()
        self.outcome_lbl.setObjectName("OutputLabel")
        self.outcome_lbl.setAlignment(Qt.AlignCenter)
        self.outcome_lbl.setWordWrap(True)
        self.outcome_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        outer.addWidget(self.outcome_lbl)

        # --- Bottom buttons ---
        self.pause_btn = QPushButton()
        self.pause_btn.setEnabled(False)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.pause_btn.setMinimumWidth(0)

        self.quit_btn = QPushButton()
        self.quit_btn.setObjectName("QuitButton")
        self.quit_btn.setCursor(Qt.PointingHandCursor)
        self.quit_btn.clicked.connect(self.close)
        self.quit_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.quit_btn.setMinimumWidth(0)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(self.pause_btn, 1)
        btn_row.addWidget(self.quit_btn, 0)
        outer.addLayout(btn_row)
        outer.addStretch(1)

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.tick)

        self._is_wayland = session_is_wayland()
        self._retranslate()
        self._refresh_idle_status()

    # --- i18n ---

    def t(self, key: str) -> str:
        return _get(key, self.cfg.language)

    def _refresh_idle_status(self) -> None:
        if self.rec.state.active:
            return
        if not self._is_wayland:
            self.status_lbl.setText(self.t("status_x11"))
        else:
            self.status_lbl.setText(
                self.t("status_ready").format(backend=self.rec.name)
            )

    def _retranslate(self) -> None:
        """Re-apply all static texts after a language switch."""
        lang = self.cfg.language
        self.brand_sub.setText(_get("subtitle", lang))
        self._refresh_idle_status()
        recording = self.rec.state.active
        self.rec_btn.setText(
            _get("rec_stop", lang) if recording else _get("rec_start", lang)
        )
        self.pause_btn.setText(
            _get("resume", lang)
            if self.rec.state.paused
            else _get("pause", lang)
        )
        self.quit_btn.setText(_get("quit", lang))
        self.outcome_lbl.setText(_get("outcome", lang))
        self.region_hint.setText(_get("region_hint", lang))
        self.lbl_src.setText(_get("label_source", lang))
        self.lbl_q.setText(_get("label_quality", lang))
        self.lbl_lang.setText(_get("label_language", lang))
        self.lbl_gain.setText(_get("label_gain", lang))
        self.lbl_region.setText(_get("label_region", lang))
        self.audio_cb.setText(_get("audio_check", lang))

        for header, key in (
            (self.src_header, "section_capture"),
            (self.audio_header, "section_audio"),
            (self.region_header, "section_region"),
        ):
            lbl = header.findChild(QLabel)
            if lbl is not None:
                lbl.setText(_get(key, lang))

        self.mode_cb.blockSignals(True)
        self.mode_cb.clear()
        self.mode_cb.addItem(_get("mode_fullscreen", lang), "fullscreen")
        self.mode_cb.addItem(_get("mode_window", lang), "window")
        self.mode_cb.addItem(_get("mode_ask", lang), "ask")
        idx = self.mode_cb.findData(self.cfg.capture_mode)
        if idx >= 0:
            self.mode_cb.setCurrentIndex(idx)
        self.mode_cb.blockSignals(False)

        self.quality_cb.blockSignals(True)
        self.quality_cb.clear()
        self.quality_cb.addItem(_get("quality_draft", lang), "draft")
        self.quality_cb.addItem(_get("quality_balanced", lang), "balanced")
        self.quality_cb.addItem(_get("quality_high", lang), "high")
        idx = self.quality_cb.findData(self.cfg.quality_preset)
        if idx >= 0:
            self.quality_cb.setCurrentIndex(idx)
        self.quality_cb.blockSignals(False)

    def _on_language_changed(self, idx: int) -> None:
        code = self.lang_cb.itemData(idx)
        if not code:
            return
        self.cfg.language = normalize(code)
        try:
            self.rec.cfg.language = self.cfg.language
        except AttributeError:
            pass
        self._retranslate()

    def _set_recording_ui(self, recording: bool) -> None:
        """Reflect the recording state on the button/timer color."""
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
                self.status_lbl.setText(self.t("deps_missing"))
                return
            except Exception as e:  # noqa: BLE001
                self.status_lbl.setText(self.t("start_failed").format(err=e))
                return
            tmp = self.rec.state.tmp_path
            self.status_lbl.setText(
                self.t("recording_to").format(
                    name=tmp.name if tmp else final.name
                )
            )
            self.rec_btn.setText(self.t("rec_stop"))
            self.audio_cb.setEnabled(False)
            self.gain_spin.setEnabled(False)
            self.mode_cb.setEnabled(False)
            self.quality_cb.setEnabled(False)
            self.lang_cb.setEnabled(False)
            self._set_region_enabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText(self.t("pause"))
            self._set_recording_ui(True)
            self.timer.start()
        else:
            out = self.rec.stop()
            self.timer.stop()
            self.audio_cb.setEnabled(True)
            self.gain_spin.setEnabled(True)
            self.mode_cb.setEnabled(True)
            self.quality_cb.setEnabled(True)
            self.lang_cb.setEnabled(True)
            self._set_region_enabled(True)
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText(self.t("pause"))
            if out:
                self.status_lbl.setText(self.t("saved").format(out=out))
            else:
                self.status_lbl.setText(
                    self.t("error_prefix").format(err=self.rec.state.last_error)
                )
            self.rec_btn.setText(self.t("rec_start"))
            self._set_recording_ui(False)

    def _on_audio_toggled(self, checked: bool) -> None:
        self.cfg.audio_enabled = checked
        # The backend holds cfg by reference; changes mid-recording are blocked.
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
                self.pause_btn.setText(self.t("pause"))
                tmp = self.rec.state.tmp_path
                self.status_lbl.setText(
                    self.t("recording_to").format(name=tmp.name if tmp else "")
                )
            else:
                self.rec.pause()
                self.pause_btn.setText(self.t("resume"))
                self.status_lbl.setText(self.t("paused_status"))
        except Exception as e:  # noqa: BLE001
            self.status_lbl.setText(self.t("pause_error").format(err=e))

    def _on_quality_changed(self, idx: int) -> None:
        preset = self.quality_cb.itemData(idx)
        if not preset:
            return
        try:
            self.cfg.apply_quality_preset(preset)
        except ValueError:
            return
        # The backend holds cfg by reference; applies to the next recording.
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
            self.status_lbl.setText(
                self.t("error_prefix").format(err=self.rec.state.last_error)
            )
            self.rec_btn.setText(self.t("rec_start"))
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText(self.t("pause"))
            self.audio_cb.setEnabled(True)
            self.gain_spin.setEnabled(True)
            self.mode_cb.setEnabled(True)
            self.quality_cb.setEnabled(True)
            self.lang_cb.setEnabled(True)
            self._set_region_enabled(True)
            self._set_recording_ui(False)
            self.timer.stop()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.rec.state.active:
            self.rec.stop()
        super().closeEvent(event)
