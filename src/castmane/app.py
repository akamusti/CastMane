"""Qt main window: modern, refined desktop utility for crash-safe recording.

Layout:
  1. Header bar   - Mark, branding + subtitle, live status pill, digital studio timer.
  2. Main body    - Left navigation rail (Capture, Audio, Region, Output, Settings),
                    Right scrollable content area with studio cards.
  3. Transport    - Large prominent Record/Stop button + Pause/Resume + Save Replay.
  4. Status bar   - Pulsing live status dot + message on the left, output folder on the right.
"""
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtMultimedia import (
    QAudioOutput,
    QCamera,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaPlayer,
)
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import theme as theme_mod
from .__init__ import __version__
from .backends import create_backend, session_is_wayland
from .config import (
    AUTO_STOP_MAX_MIN,
    BITRATE_MAX_KBPS,
    BITRATE_MIN_KBPS,
    COUNTDOWN_CHOICES,
    FPS_MAX,
    FPS_MIN,
    MIN_FREE_MB,
    AppConfig,
    sanitize_prefix,
)
from .i18n import SUPPORTED_LANGUAGES, normalize
from .i18n import get as _get
from .icons import paint_icon, tray_icon
from .theme import (
    FONT_UI,
    FOOTER_H,
    HEADER_H,
    HEADER_TIMER_H,
    RADIUS,
    RADIUS_LG,
    RADIUS_SM,
    SEGMENT_PAD,
    SIDEBAR_W,
    logo_path,
    mark_path,
)


def build_stylesheet(t: dict[str, str]) -> str:
    """Render the full modern QSS for the given theme colour table."""
    CANVAS = t["CANVAS"]
    SURFACE = t["SURFACE"]
    SURFACE_SUNKEN = t["SURFACE_SUNKEN"]
    HAIRLINE = t["HAIRLINE"]
    HAIRLINE_STRONG = t["HAIRLINE_STRONG"]
    TEXT_MAIN = t["TEXT_MAIN"]
    TEXT_SOFT = t["TEXT_SOFT"]
    TEXT_MUTED = t["TEXT_MUTED"]
    TEXT_FAINT = t["TEXT_FAINT"]
    INK = t["INK"]
    INK_HOVER = t["INK_HOVER"]
    INK_PRESSED = t["INK_PRESSED"]
    PRIMARY_TEXT = t["PRIMARY_TEXT"]
    BTN_BG = t["BTN_BG"]
    BTN_BORDER = t["BTN_BORDER"]
    BTN_HOVER = t["BTN_HOVER"]
    BTN_PRESSED = t["BTN_PRESSED"]
    BTN_DISABLED_BG = t["BTN_DISABLED_BG"]
    BTN_DISABLED_TEXT = t["BTN_DISABLED_TEXT"]
    REC = t["REC"]
    REC_HOVER = t["REC_HOVER"]
    REC_PRESSED = t["REC_PRESSED"]
    REC_TINT = t["REC_TINT"]
    REC_BORDER = t["REC_BORDER"]
    READY = t["READY"]
    READY_TINT = t["READY_TINT"]
    PAUSED = t["PAUSED"]
    PAUSED_TINT = t["PAUSED_TINT"]

    return f"""
QMainWindow, QWidget#Root {{
    background-color: {CANVAS};
    color: {TEXT_MAIN};
    font-family: {FONT_UI};
    font-size: 13px;
}}

QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

/* Modern sleek scrollbar */
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {HAIRLINE_STRONG};
    min-height: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QLabel {{
    background: transparent;
}}

/* --- Header Bar --- */
QFrame#Header {{
    background-color: {SURFACE};
    border: none;
    border-bottom: 1px solid {HAIRLINE};
}}
QLabel#AppName {{
    color: {TEXT_MAIN};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: -0.2px;
}}
QLabel#AppSub {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QLabel#AppBadge {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 600;
    background-color: {SURFACE_SUNKEN};
    border: 1px solid {HAIRLINE};
    border-radius: 4px;
    padding: 1px 5px;
}}

/* Digital Timer Display */
QFrame#TimerDisplay {{
    background-color: {SURFACE_SUNKEN};
    border: 1px solid {HAIRLINE};
    border-radius: 10px;
}}
QLabel#Timer {{
    color: {TEXT_SOFT};
    letter-spacing: 0.5px;
    background: transparent;
}}
QLabel#Timer[recording="true"] {{
    color: {REC};
    font-weight: 700;
}}

/* State Pill (Header) — fixed pill height, text hugs its box */
QLabel#Pill {{
    border: 1px solid {HAIRLINE_STRONG};
    border-radius: 11px;
    padding: 0px 12px;
    min-height: 20px;
    max-height: 20px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: {READY};
    background-color: {READY_TINT};
}}
QLabel#Pill[state="ready"] {{
    color: {READY};
    border-color: {READY};
    background-color: {READY_TINT};
}}
QLabel#Pill[state="recording"] {{
    color: {REC};
    border-color: {REC_BORDER};
    background-color: {REC_TINT};
}}
QLabel#Pill[state="paused"] {{
    color: {PAUSED};
    border-color: {PAUSED};
    background-color: {PAUSED_TINT};
}}
QLabel#Pill[state="countdown"] {{
    color: {PAUSED};
    border-color: {PAUSED};
    background-color: {PAUSED_TINT};
}}

/* --- Sidebar (Navigation Rail) --- */
QFrame#Sidebar {{
    background-color: {CANVAS};
    border: none;
    border-right: 1px solid {HAIRLINE};
}}
QPushButton#Nav {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS}px;
    padding: 0 12px 0 42px;
    color: {TEXT_MUTED};
    font-size: 13px;
    font-weight: 500;
    text-align: left;
}}
QPushButton#Nav:hover {{
    background-color: {BTN_HOVER};
    color: {TEXT_MAIN};
}}
QPushButton#Nav:checked {{
    background-color: {SURFACE};
    border-color: {HAIRLINE};
    color: {TEXT_MAIN};
    font-weight: 700;
}}
QFrame#BackendCard {{
    background-color: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS}px;
    padding: 8px 10px;
}}
QLabel#SideNote {{
    color: {TEXT_FAINT};
    font-size: 11px;
    line-height: 1.3;
}}

/* --- Content Cards --- */
QFrame#Card {{
    background-color: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS_LG}px;
}}
QLabel#SectionTitle {{
    color: {TEXT_MAIN};
    font-size: 13px;
    font-weight: 700;
    padding-bottom: 2px;
}}
QLabel#RowLabel {{
    color: {TEXT_SOFT};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#Hint {{
    color: {TEXT_FAINT};
    font-size: 11px;
    line-height: 1.3;
}}
QLabel#Hint[error="true"] {{
    color: {REC};
    font-weight: 600;
}}
QFrame#Hairline {{
    background-color: {HAIRLINE};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}

/* --- Segmented Control --- */
QFrame#Segment {{
    background-color: {SURFACE_SUNKEN};
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS}px;
}}
QPushButton#Seg {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    padding: 6px 8px;
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#Seg:hover {{
    color: {TEXT_MAIN};
    background-color: {BTN_HOVER};
}}
QPushButton#Seg:checked {{
    background-color: {SURFACE};
    border-color: {HAIRLINE_STRONG};
    color: {TEXT_MAIN};
    font-weight: 700;
}}
QPushButton#Seg:disabled {{
    color: {TEXT_FAINT};
}}

/* --- Primary Record Button --- */
QPushButton#Record {{
    background-color: {INK};
    border: 1px solid {INK};
    border-radius: 12px;
    padding: 12px 24px;
    color: {PRIMARY_TEXT};
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.2px;
}}
QPushButton#Record:hover {{
    background-color: {INK_HOVER};
    border-color: {INK_HOVER};
}}
QPushButton#Record:pressed {{
    background-color: {INK_PRESSED};
    border-color: {INK_PRESSED};
}}
QPushButton#Record[recording="true"] {{
    background-color: {REC};
    border-color: {REC};
    color: #FFFFFF;
}}
QPushButton#Record[recording="true"]:hover {{
    background-color: {REC_HOVER};
    border-color: {REC_HOVER};
}}
QPushButton#Record[recording="true"]:pressed {{
    background-color: {REC_PRESSED};
    border-color: {REC_PRESSED};
}}

/* --- Action Buttons (Pause & Replay) --- */
QPushButton#Pause {{
    background-color: {BTN_BG};
    border: 1px solid {BTN_BORDER};
    border-radius: 10px;
    padding: 10px 16px;
    color: {TEXT_MAIN};
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#Pause:hover {{
    background-color: {BTN_HOVER};
    border-color: {HAIRLINE_STRONG};
}}
QPushButton#Pause:pressed {{
    background-color: {BTN_PRESSED};
}}
QPushButton#Pause:disabled {{
    background-color: {BTN_DISABLED_BG};
    color: {BTN_DISABLED_TEXT};
    border-color: {HAIRLINE};
}}

/* Standard push buttons */
QPushButton {{
    background-color: {BTN_BG};
    border: 1px solid {BTN_BORDER};
    border-radius: {RADIUS_SM}px;
    padding: 6px 12px;
    color: {TEXT_MAIN};
    font-size: 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {BTN_HOVER};
    border-color: {HAIRLINE_STRONG};
}}
QPushButton:pressed {{
    background-color: {BTN_PRESSED};
}}
QPushButton:disabled {{
    background-color: {BTN_DISABLED_BG};
    color: {BTN_DISABLED_TEXT};
    border-color: {HAIRLINE};
}}

/* Combo boxes (camera device picker) */
QComboBox {{
    background-color: {SURFACE};
    border: 1px solid {BTN_BORDER};
    border-radius: {RADIUS_SM}px;
    padding: 6px 10px;
    color: {TEXT_MAIN};
    font-size: 12px;
}}
QComboBox:focus {{
    border-color: {INK};
}}
QComboBox:disabled {{
    color: {BTN_DISABLED_TEXT};
    background-color: {BTN_DISABLED_BG};
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: 1px solid {HAIRLINE_STRONG};
    selection-background-color: {INK};
    selection-color: {PRIMARY_TEXT};
    color: {TEXT_MAIN};
}}
QPushButton:hover {{
    background-color: {BTN_HOVER};
    border-color: {HAIRLINE_STRONG};
}}
QPushButton:pressed {{
    background-color: {BTN_PRESSED};
}}
QPushButton:disabled {{
    background-color: {BTN_DISABLED_BG};
    color: {BTN_DISABLED_TEXT};
    border-color: {HAIRLINE};
}}

/* --- Studio Preview --- */
QVideoWidget#ScreenView {{
    background-color: #000000;
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
}}
QVideoWidget#CamView {{
    background-color: #000000;
    border: 1px solid {HAIRLINE_STRONG};
    border-radius: 6px;
}}

/* --- Inputs (Text & SpinBox) --- */
QLineEdit, QSpinBox {{
    background-color: {SURFACE};
    border: 1px solid {BTN_BORDER};
    border-radius: {RADIUS_SM}px;
    padding: 7px 10px;
    color: {TEXT_MAIN};
    font-size: 12px;
    selection-background-color: {INK};
    selection-color: {PRIMARY_TEXT};
}}
QLineEdit:focus, QSpinBox:focus {{
    border-color: {INK};
}}
QLineEdit:disabled, QSpinBox:disabled {{
    color: {BTN_DISABLED_TEXT};
    background-color: {BTN_DISABLED_BG};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0px;
    border: none;
}}

/* --- Audio Mixer Channel Strips --- */
QFrame#Strip {{
    background-color: {SURFACE_SUNKEN};
    border: 1px solid {HAIRLINE};
    border-radius: 10px;
}}
QLabel#StripName {{
    color: {TEXT_MAIN};
    font-size: 12px;
    font-weight: 700;
}}
QLabel#StripValue {{
    color: {TEXT_SOFT};
    font-size: 11px;
    font-weight: 600;
    background-color: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: 6px;
    padding: 3px 10px;
    min-width: 52px;
}}
QSlider::groove:vertical {{
    width: 8px;
    background: {BTN_BORDER};
    border: none;
    border-radius: 3px;
}}
QSlider::handle:vertical {{
    background: {SURFACE};
    border: 1.5px solid {HAIRLINE_STRONG};
    width: 18px;
    height: 18px;
    margin: 0 -6px;
    border-radius: 9px;
}}
QSlider::handle:vertical:hover {{
    border-color: {INK};
    background: {SURFACE};
}}
QSlider::handle:vertical:disabled {{
    border-color: {BTN_DISABLED_TEXT};
    background: {BTN_DISABLED_BG};
}}

/* Horizontal slider */
QSlider::groove:horizontal {{
    height: 6px;
    background: {BTN_BORDER};
    border: none;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {SURFACE};
    border: 1.5px solid {HAIRLINE_STRONG};
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{
    border-color: {INK};
}}

/* --- Recent Recordings List --- */
QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS}px;
    padding: 4px;
    color: {TEXT_MAIN};
    outline: none;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: {RADIUS_SM}px;
    margin: 1px 0;
}}
QListWidget::item:hover {{
    background-color: {BTN_HOVER};
}}
QListWidget::item:selected {{
    background-color: {INK};
    color: {PRIMARY_TEXT};
}}

/* --- Transport Bar --- */
QFrame#Transport {{
    background-color: {SURFACE};
    border: none;
    border-top: 1px solid {HAIRLINE};
}}

/* --- Status Bar --- */
QFrame#StatusBar {{
    background-color: {CANVAS};
    border: none;
    border-top: 1px solid {HAIRLINE};
}}
QLabel#StatusText {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#StatusText[error="true"] {{
    color: {REC};
    font-weight: 600;
}}
QLabel#OutPath {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QPushButton#FolderBtn {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    padding: 4px;
}}
QPushButton#FolderBtn:hover {{
    background-color: {BTN_HOVER};
    border-color: {HAIRLINE};
}}

/* Tooltip */
QToolTip {{
    background-color: {SURFACE};
    color: {TEXT_MAIN};
    border: 1px solid {HAIRLINE_STRONG};
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}}
"""


def _active_theme(widget: QWidget) -> dict[str, str]:
    """Colour table of the window this widget lives in."""
    win = widget.window()
    t = getattr(win, "theme", None)
    if isinstance(t, dict) and "CANVAS" in t:
        return t
    return theme_mod.get_theme(theme_mod.DEFAULT_THEME)


LANGUAGE_LABELS = {"en": "EN", "tr": "TR"}


def _repolish(widget: QWidget) -> None:
    """Re-evaluate stylesheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class MarkTile(QWidget):
    """Header logo tile with smooth adaptive background."""

    TILE = 36
    GLYPH = 26

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.TILE, self.TILE)
        mark_file = mark_path()
        self._pix = QPixmap(mark_file) if mark_file else QPixmap()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        t = _active_theme(self)
        if theme_mod.surface_is_dark(t):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FFFFFF"))
            p.drawRoundedRect(self.rect(), 8, 8)
        else:
            p.setPen(QPen(QColor(t["HAIRLINE"]), 1.0))
            p.setBrush(QColor(t["SURFACE_SUNKEN"]))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

        if not self._pix.isNull():
            side = float(self.GLYPH)
            x = (self.width() - side) / 2.0
            y = (self.height() - side) / 2.0
            p.drawPixmap(int(x), int(y), int(side), int(side), self._pix)


class StatusDot(QWidget):
    """A 10px state dot with pulsing support during recording."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor(theme_mod.READY)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(QRectF(1, 1, 10, 10))


class Switch(QAbstractButton):
    """Modern smooth sliding toggle switch."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._pos = 1.0 if self.isChecked() else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._apply_pos)
        self.toggled.connect(self._animate_to)

    def _animate_to(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def _apply_pos(self, value) -> None:
        self._pos = float(value)
        self.update()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(44, 24)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = float(self.width()), float(self.height())
        track = QRectF(0.5, 0.5, w - 1.0, h - 1.0)

        t = _active_theme(self)
        if self.isEnabled():
            off = QColor(t["SURFACE_SUNKEN"])
            on = QColor(t["INK"])
            knob_off = QColor(t.get("SWITCH_KNOB_OFF", "#FFFFFF"))
            knob_on = QColor(t.get("SWITCH_KNOB_ON", t["PRIMARY_TEXT"]))
            border = QColor(t["HAIRLINE_STRONG"])
        else:
            off = QColor(t["BTN_DISABLED_BG"])
            on = QColor(t["BTN_DISABLED_BG"])
            knob_off = QColor(t["BTN_DISABLED_TEXT"])
            knob_on = QColor(t["BTN_DISABLED_TEXT"])
            border = QColor(t["HAIRLINE"])

        def _mix(a: QColor, b: QColor, pos: float) -> QColor:
            return QColor(
                round(a.red() + (b.red() - a.red()) * pos),
                round(a.green() + (b.green() - a.green()) * pos),
                round(a.blue() + (b.blue() - a.blue()) * pos),
            )

        p.setPen(Qt.NoPen)
        p.setBrush(_mix(off, on, self._pos))
        p.drawRoundedRect(track.adjusted(1.0, 1.0, -1.0, -1.0), 11, 11)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(border, 1.0))
        p.drawRoundedRect(track, 11.5, 11.5)

        knob = h - 8.0
        travel = w - knob - 6.0
        knob_center = QPointF(3.0 + knob / 2 + travel * self._pos, h / 2.0)
        p.setPen(Qt.NoPen)
        p.setBrush(_mix(knob_off, knob_on, self._pos))
        p.drawEllipse(knob_center, knob / 2, knob / 2)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(border, 1.0))
        p.drawEllipse(knob_center, knob / 2 - 0.5, knob / 2 - 0.5)


class SegmentedControl(QFrame):
    """Mutually exclusive options in a sleek sunken track."""

    changed = Signal(str)

    def __init__(
        self,
        entries: list[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Segment")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SEGMENT_PAD, SEGMENT_PAD, SEGMENT_PAD, SEGMENT_PAD)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        for label, data in entries:
            btn = QPushButton(label, self)
            btn.setObjectName("Seg")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("data", data)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _=False, d=data: self.changed.emit(d))
            self._group.addButton(btn)
            layout.addWidget(btn, 1)
            self._buttons.append(btn)

    def set_labels(self, labels: list[str]) -> None:
        for btn, label in zip(self._buttons, labels):
            btn.setText(label)

    def current_data(self) -> str:
        btn = self._group.checkedButton()
        return btn.property("data") if btn is not None else ""

    def set_current_data(self, data: str) -> None:
        self._group.blockSignals(True)
        for btn in self._buttons:
            btn.setChecked(btn.property("data") == data)
        self._group.blockSignals(False)

    def set_enabled(self, enabled: bool) -> None:
        for btn in self._buttons:
            btn.setEnabled(enabled)


class NavButton(QPushButton):
    """One sidebar navigation item with an icon and active accent indicator."""

    ICON_W = 38

    def __init__(self, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Nav")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._icon = icon_name

    def _ink(self) -> QColor:
        t = _active_theme(self)
        if not self.isEnabled():
            return QColor(t["TEXT_FAINT"])
        if self.isChecked():
            return QColor(t["TEXT_MAIN"])
        return QColor(t["TEXT_MAIN"]) if self.underMouse() else QColor(t["TEXT_MUTED"])

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = _active_theme(self)

        # Draw left accent rail when active (inset, clear of the card border)
        if self.isChecked():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t["INK"]))
            p.drawRoundedRect(QRectF(5, 11, 3, self.height() - 22), 1.5, 1.5)

        # Draw icon
        side = 16.0
        x = 18.0
        y = (self.height() - side) / 2.0
        paint_icon(p, self._icon, QRectF(x, y, side, side), self._ink())

    def enterEvent(self, event) -> None:
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        self.update()


class RecordButton(QPushButton):
    """Primary transport button: red dot when idle, stop square when recording."""

    GLYPH_GAP = 12.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Record")
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("recording", False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(48)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = _active_theme(self)
        metrics = QFontMetrics(self.font())
        text_w = metrics.horizontalAdvance(self.text())
        gx = self.width() / 2.0 - text_w / 2.0 - self.GLYPH_GAP - 6.0
        gy = self.height() / 2.0 - 5.5
        if self.property("recording"):
            path = QPainterPath()
            path.addRoundedRect(QRectF(gx, gy, 11, 11), 2, 2)
            p.fillPath(path, QColor("#FFFFFF"))
        else:
            paint_icon(p, "dot", QRectF(gx, gy, 12, 12), QColor(t["REC"]))

    def set_recording(self, recording: bool) -> None:
        self.setProperty("recording", recording)
        _repolish(self)


class MainWindow(QMainWindow):
    LABEL_COL = 152
    OUT_PATH_PX = 250

    # Emitted from the finalize worker (any thread); the slot runs on the UI
    # thread, so the result is applied without polling the 500 ms tick.
    _bg_finished = Signal()

    def __init__(self, cfg: AppConfig | None = None) -> None:
        super().__init__()
        self.cfg = cfg or AppConfig()
        self.cfg.language = normalize(self.cfg.language)
        self.cfg.theme = theme_mod.normalize_theme(self.cfg.theme)
        self.theme = theme_mod.get_theme(self.cfg.theme)
        self.rec = create_backend(self.cfg)
        self._card_labels: list[QLabel] = []
        self.setWindowTitle("CastMane")
        self.resize(960, 720)
        self.setMinimumSize(780, 570)
        self.setStyleSheet(build_stylesheet(self.theme))
        icon_path = logo_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        frame = QVBoxLayout(root)
        frame.setContentsMargins(0, 0, 0, 0)
        frame.setSpacing(0)

        frame.addWidget(self._build_header())
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._build_sidebar())
        body_layout.addWidget(self._build_pane(), 1)
        frame.addWidget(body, 1)
        frame.addWidget(self._build_transport())
        frame.addWidget(self._build_statusbar())

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.tick)

        # Countdown & auto-stop timers
        self._countdown_left = 0
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._autostop_timer = QTimer(self)
        self._autostop_timer.setSingleShot(True)
        self._autostop_timer.timeout.connect(self._auto_stop_timeout)
        self._autostop_remaining_ms = 0
        self._disk_check_counter = 0
        self._quit_requested = False
        # Background finalizer: stopping the encoder also runs the crash-safe
        # MKV->MP4 remux, which can block for minutes. Running it on the UI
        # thread froze the whole window, so it runs on a worker and `tick`
        # picks the result up when it is done.
        self._bg_thread: threading.Thread | None = None
        self._bg_kind = ""  # "stop" | "replay"
        self._bg_result: Path | None = None
        self._bg_error = ""
        self._bg_reason = ""
        self._bg_quit_after = False
        self._bg_finished.connect(self._poll_background)
        self._setup_shortcuts()
        self._setup_tray()

        self._is_wayland = session_is_wayland()
        self._retranslate()
        self._refresh_custom_enabled()
        self._refresh_idle_status()
        QTimer.singleShot(0, self._maybe_offer_recovery)
        QTimer.singleShot(0, self._refresh_camera_preview)

    # --- UI Layout Construction ---

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Header")
        bar.setFixedHeight(HEADER_H + 4)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(12)

        mark = MarkTile()
        self.header_mark = mark
        row.addWidget(mark)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        name = QLabel("CastMane")
        name.setObjectName("AppName")
        title_row.addWidget(name)

        badge = QLabel(f"v{__version__}")
        badge.setObjectName("AppBadge")
        title_row.addWidget(badge)
        title_row.addStretch(1)

        self.subtitle_lbl = QLabel()
        self.subtitle_lbl.setObjectName("AppSub")

        text.addLayout(title_row)
        text.addWidget(self.subtitle_lbl)
        row.addLayout(text, 1)

        # Live State Pill — hugs its text, vertically centred in the header.
        self.state_pill = QLabel("READY")
        self.state_pill.setObjectName("Pill")
        self.state_pill.setProperty("state", "ready")
        self.state_pill.setAlignment(Qt.AlignCenter)
        self.state_pill.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        row.addWidget(self.state_pill, 0, Qt.AlignVCenter)

        # Digital Timer Capsule
        timer_box = QFrame()
        timer_box.setObjectName("TimerDisplay")
        timer_box.setFixedHeight(HEADER_TIMER_H)
        timer_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        timer_layout = QHBoxLayout(timer_box)
        timer_layout.setContentsMargins(0, 0, 0, 0)
        timer_layout.setSpacing(0)

        self.timer_lbl = QLabel("00:00:00")
        self.timer_lbl.setObjectName("Timer")
        self.timer_lbl.setAlignment(Qt.AlignCenter)
        self.timer_lbl.setProperty("recording", False)
        font = QFont()
        font.setFamilies([
            "JetBrains Mono",
            "DejaVu Sans Mono",
            "Noto Sans Mono",
            "Liberation Mono",
            "monospace",
        ])
        font.setStyleHint(QFont.Monospace)
        font.setPixelSize(18)
        font.setWeight(QFont.DemiBold)
        self.timer_lbl.setFont(font)
        self.timer_lbl.setFixedWidth(
            QFontMetrics(font).horizontalAdvance("00:00:00") + 8
        )
        timer_layout.addWidget(self.timer_lbl)
        row.addWidget(timer_box, 0, Qt.AlignVCenter)

        return bar

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(SIDEBAR_W + 12)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(4)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_buttons: list[NavButton] = []
        for code, icon in (
            ("studio", "studio"),
            ("capture", "monitor"),
            ("audio", "audio"),
            ("region", "region"),
            ("output", "folder"),
            ("settings", "gear"),
        ):
            btn = NavButton(icon, self)
            btn.setProperty("page", code)
            btn.clicked.connect(lambda _=False, c=code: self._select_tab(c))
            self.tab_group.addButton(btn)
            layout.addWidget(btn)
            self.tab_buttons.append(btn)
        self.tab_buttons[0].setChecked(True)

        layout.addStretch(1)

        # Backend Info Card at the bottom of the sidebar
        backend_box = QFrame()
        backend_box.setObjectName("BackendCard")
        b_layout = QVBoxLayout(backend_box)
        b_layout.setContentsMargins(8, 6, 8, 6)
        self.backend_lbl = QLabel()
        self.backend_lbl.setObjectName("SideNote")
        self.backend_lbl.setWordWrap(True)
        b_layout.addWidget(self.backend_lbl)
        layout.addWidget(backend_box)

        return side

    def _build_pane(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_studio_page())
        self.pages.addWidget(self._build_capture_page())
        self.pages.addWidget(self._build_audio_page())
        self.pages.addWidget(self._build_region_page())
        self.pages.addWidget(self._build_output_page())
        self.pages.addWidget(self._build_settings_page())
        layout.addWidget(self.pages)
        layout.addStretch(1)
        scroll.setWidget(holder)
        return scroll

    def _card(self, i18n_key: str) -> tuple[QFrame, QVBoxLayout]:
        """Studio card container with modern styling."""
        frame = QFrame()
        frame.setObjectName("Card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(8)
        title = QLabel()
        title.setObjectName("SectionTitle")
        title.setProperty("i18n", i18n_key)
        outer.addWidget(title)
        inner = QVBoxLayout()
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(2)
        outer.addLayout(inner)
        self._card_labels.append(title)
        return frame, inner

    @staticmethod
    def _strip(name: QLabel, slider: QSlider, value: QLabel) -> QFrame:
        """One mixer channel strip with fader and level readout."""
        frame = QFrame()
        frame.setObjectName("Strip")
        box = QVBoxLayout(frame)
        box.setContentsMargins(14, 12, 14, 12)
        box.setSpacing(8)
        box.addWidget(name)
        fader_row = QHBoxLayout()
        fader_row.setContentsMargins(0, 4, 0, 4)
        fader_row.addStretch(1)
        fader_row.addWidget(slider)
        fader_row.addStretch(1)
        box.addLayout(fader_row)
        value.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        value.setAlignment(Qt.AlignCenter)
        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.addStretch(1)
        value_row.addWidget(value)
        value_row.addStretch(1)
        box.addLayout(value_row)
        return frame

    def _row(
        self,
        label: QLabel,
        control: QWidget,
        hint: QLabel | None = None,
    ) -> QWidget:
        """Settings row with fixed label column and flexible control column."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(14)
        label.setFixedWidth(self.LABEL_COL)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        top.addWidget(label)
        top.addWidget(control, 1)
        layout.addLayout(top)
        if hint is not None:
            hint.setWordWrap(True)
            indent = QWidget()
            indent_layout = QHBoxLayout(indent)
            indent_layout.setContentsMargins(0, 0, 0, 0)
            spacer = QWidget()
            spacer.setFixedWidth(self.LABEL_COL + 14)
            indent_layout.addWidget(spacer)
            indent_layout.addWidget(hint, 1)
            layout.addWidget(indent)
        return box

    def _stacked_row(
        self,
        label: QLabel,
        control: QWidget,
        hint: QLabel | None = None,
    ) -> QWidget:
        """Row where the label sits above a full-width control.

        Used for wide controls (many segments) that would otherwise be
        squeezed into the narrow control column and clip their labels.
        """
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)
        layout.addWidget(label)
        layout.addWidget(control)
        if hint is not None:
            hint.setWordWrap(True)
            layout.addWidget(hint)
        return box

    @staticmethod
    def _hairline() -> QFrame:
        line = QFrame()
        line.setObjectName("Hairline")
        return line

    def _build_studio_page(self) -> QWidget:
        """OBS-style studio: live preview on top, Sources/Camera/Controls below."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        preview_card, preview = self._card("studio_preview")
        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.setSpacing(10)
        self.preview_badge = QLabel("READY")
        self.preview_badge.setObjectName("Pill")
        self.preview_badge.setProperty("state", "ready")
        self.preview_badge.setAlignment(Qt.AlignCenter)
        self.preview_badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        badge_row.addWidget(self.preview_badge)
        self.preview_status = QLabel()
        self.preview_status.setObjectName("Hint")
        self.preview_status.setWordWrap(True)
        badge_row.addWidget(self.preview_status, 1)
        preview.addLayout(badge_row)

        video_row = QHBoxLayout()
        video_row.setContentsMargins(0, 2, 0, 0)
        video_row.setSpacing(12)
        self.screen_view = QVideoWidget()
        self.screen_view.setObjectName("ScreenView")
        self.screen_view.setMinimumHeight(150)
        self.screen_view.setMaximumHeight(180)
        self.screen_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        video_row.addWidget(self.screen_view, 1)
        cam_col = QVBoxLayout()
        cam_col.setContentsMargins(0, 0, 0, 0)
        cam_col.setSpacing(6)
        self.cam_view = QVideoWidget()
        self.cam_view.setObjectName("CamView")
        self.cam_view.setFixedSize(200, 125)
        cam_col.addWidget(self.cam_view)
        self.cam_status = QLabel()
        self.cam_status.setObjectName("Hint")
        self.cam_status.setWordWrap(True)
        self.cam_status.setFixedWidth(200)
        cam_col.addWidget(self.cam_status)
        cam_col.addStretch(1)
        video_row.addLayout(cam_col)
        preview.addLayout(video_row)
        layout.addWidget(preview_card)

        # Media backends are best-effort: preview/camera must never
        # break the window when codecs or devices are missing.
        self.preview_player: QMediaPlayer | None = None
        try:
            self.preview_player = QMediaPlayer(self)
            self._preview_audio = QAudioOutput(self)
            self._preview_audio.setMuted(True)
            self.preview_player.setAudioOutput(self._preview_audio)
            self.preview_player.setVideoOutput(self.screen_view)
            self.preview_player.errorOccurred.connect(self._on_preview_error)
            self.preview_player.playingChanged.connect(self._on_preview_playing)
            self.preview_player.mediaStatusChanged.connect(
                self._on_preview_media_status
            )
        except Exception:
            self.preview_player = None
        self._cam: QCamera | None = None
        self._cam_session: QMediaCaptureSession | None = None

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(12)

        sources_card, sources = self._card("sources_title")
        self.sources_list = QListWidget()
        self.sources_list.setMaximumHeight(140)
        self.sources_list.setMinimumHeight(140)
        self.sources_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for key in ("display", "camera", "mic", "desktop"):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, key)
            if key == "display":
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            else:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
            self.sources_list.addItem(item)
        self.sources_list.itemChanged.connect(self._on_source_toggled)
        sources.addWidget(self.sources_list)
        self.hint_sources = QLabel()
        self.hint_sources.setObjectName("Hint")
        self.hint_sources.setWordWrap(True)
        sources.addWidget(self.hint_sources)
        bottom.addWidget(sources_card, 1)

        cam_card, cam = self._card("card_camera")
        self.lbl_camera_on = QLabel()
        self.lbl_camera_on.setObjectName("RowLabel")
        self.camera_sw = Switch()
        self.camera_sw.setChecked(self.cfg.camera_enabled)
        self.camera_sw.toggled.connect(self._on_camera_toggled)
        cam.addWidget(self._stacked_row(self.lbl_camera_on, self._switch_wrap(self.camera_sw)))
        self.lbl_camera_device = QLabel()
        self.lbl_camera_device.setObjectName("RowLabel")
        self.camera_combo = QComboBox()
        self.camera_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.camera_combo.currentIndexChanged.connect(
            self._on_camera_device_changed
        )
        cam.addWidget(self._stacked_row(self.lbl_camera_device, self.camera_combo))
        self.lbl_camera_embed = QLabel()
        self.lbl_camera_embed.setObjectName("RowLabel")
        self.camera_embed_sw = Switch()
        self.camera_embed_sw.setChecked(self.cfg.camera_embed)
        self.camera_embed_sw.toggled.connect(self._on_camera_embed_toggled)
        self.hint_camera_embed = QLabel()
        self.hint_camera_embed.setObjectName("Hint")
        cam.addWidget(
            self._stacked_row(
                self.lbl_camera_embed,
                self._switch_wrap(self.camera_embed_sw),
                self.hint_camera_embed,
            )
        )
        self.hint_camera = QLabel()
        self.hint_camera.setObjectName("Hint")
        self.hint_camera.setWordWrap(True)
        cam.addWidget(self.hint_camera)
        bottom.addWidget(cam_card, 1)

        ctrl_card, ctrl = self._card("card_controls")
        self.studio_pause_btn = QPushButton()
        self.studio_pause_btn.setObjectName("Pause")
        self.studio_pause_btn.setCursor(Qt.PointingHandCursor)
        self.studio_pause_btn.clicked.connect(self.toggle_pause)
        ctrl.addWidget(self.studio_pause_btn)
        self.studio_replay_btn = QPushButton()
        self.studio_replay_btn.setObjectName("Pause")
        self.studio_replay_btn.setCursor(Qt.PointingHandCursor)
        self.studio_replay_btn.clicked.connect(self.save_replay_clip)
        ctrl.addWidget(self.studio_replay_btn)
        bottom.addWidget(ctrl_card, 1)

        layout.addLayout(bottom)
        layout.addStretch(1)
        return page

    @staticmethod
    def _switch_wrap(sw: Switch) -> QWidget:
        """Left-aligned switch in a flexible row (for _row controls)."""
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(sw)
        row.addStretch(1)
        return wrap

    def _build_capture_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        video_card, video = self._card("card_video")

        self.lbl_source = QLabel()
        self.lbl_source.setObjectName("RowLabel")
        self.mode_seg = SegmentedControl([("", "fullscreen"), ("", "window"), ("", "ask")])
        self.mode_seg.set_current_data(self.cfg.capture_mode)
        self.mode_seg.changed.connect(self._on_mode_changed)
        self.hint_mode = QLabel()
        self.hint_mode.setObjectName("Hint")
        video.addWidget(self._row(self.lbl_source, self.mode_seg, self.hint_mode))

        self.lbl_quality = QLabel()
        self.lbl_quality.setObjectName("RowLabel")
        self.quality_seg = SegmentedControl([
            ("", "draft"),
            ("", "balanced"),
            ("", "high"),
            ("", "custom"),
        ])
        self.quality_seg.set_current_data(self.cfg.quality_preset)
        self.quality_seg.changed.connect(self._on_quality_changed)
        self.hint_quality = QLabel()
        self.hint_quality.setObjectName("Hint")
        video.addWidget(self._row(self.lbl_quality, self.quality_seg, self.hint_quality))

        self.lbl_fps = QLabel()
        self.lbl_fps.setObjectName("RowLabel")
        fps_wrap = QWidget()
        fps_row = QHBoxLayout(fps_wrap)
        fps_row.setContentsMargins(0, 0, 0, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(FPS_MIN, FPS_MAX)
        self.fps_spin.setFixedWidth(120)
        self.fps_spin.setValue(self.cfg.fps)
        self.fps_spin.valueChanged.connect(self._on_fps_changed)
        fps_row.addWidget(self.fps_spin)
        fps_row.addStretch(1)
        video.addWidget(self._row(self.lbl_fps, fps_wrap))

        self.lbl_bitrate = QLabel()
        self.lbl_bitrate.setObjectName("RowLabel")
        br_wrap = QWidget()
        br_row = QHBoxLayout(br_wrap)
        br_row.setContentsMargins(0, 0, 0, 0)
        self.br_spin = QSpinBox()
        self.br_spin.setRange(BITRATE_MIN_KBPS, BITRATE_MAX_KBPS)
        self.br_spin.setSingleStep(1000)
        self.br_spin.setSuffix(" kbps")
        self.br_spin.setFixedWidth(180)
        self.br_spin.setValue(self.cfg.video_bitrate_kbps)
        self.br_spin.valueChanged.connect(self._on_bitrate_changed)
        br_row.addWidget(self.br_spin)
        br_row.addStretch(1)
        video.addWidget(self._row(self.lbl_bitrate, br_wrap))
        layout.addWidget(video_card)

        auto_card, auto = self._card("card_automation")

        self.lbl_cursor = QLabel()
        self.lbl_cursor.setObjectName("RowLabel")
        cursor_wrap = QWidget()
        cursor_row = QHBoxLayout(cursor_wrap)
        cursor_row.setContentsMargins(0, 0, 0, 0)
        self.cursor_sw = Switch()
        self.cursor_sw.setChecked(self.cfg.show_cursor)
        self.cursor_sw.toggled.connect(self._on_cursor_toggled)
        cursor_row.addWidget(self.cursor_sw)
        cursor_row.addStretch(1)
        self.hint_cursor = QLabel()
        self.hint_cursor.setObjectName("Hint")
        auto.addWidget(self._row(self.lbl_cursor, cursor_wrap, self.hint_cursor))

        self.lbl_countdown = QLabel()
        self.lbl_countdown.setObjectName("RowLabel")
        self.countdown_seg = SegmentedControl([
            (self.t("countdown_off") if v == 0 else f"{v}s", str(v))
            for v in COUNTDOWN_CHOICES
        ])
        self.countdown_seg.set_current_data(str(self.cfg.countdown_s))
        self.countdown_seg.changed.connect(self._on_countdown_changed)
        self.hint_countdown = QLabel()
        self.hint_countdown.setObjectName("Hint")
        auto.addWidget(self._row(self.lbl_countdown, self.countdown_seg, self.hint_countdown))

        self.lbl_autostop = QLabel()
        self.lbl_autostop.setObjectName("RowLabel")
        autostop_wrap = QWidget()
        autostop_row = QHBoxLayout(autostop_wrap)
        autostop_row.setContentsMargins(0, 0, 0, 0)
        autostop_row.setSpacing(10)
        self.autostop_spin = QSpinBox()
        self.autostop_spin.setRange(0, AUTO_STOP_MAX_MIN)
        self.autostop_spin.setValue(self.cfg.auto_stop_min)
        self.autostop_spin.valueChanged.connect(self._on_autostop_changed)
        autostop_row.addWidget(self.autostop_spin)
        self.autostop_unit = QLabel()
        self.autostop_unit.setObjectName("Hint")
        autostop_row.addWidget(self.autostop_unit)
        autostop_row.addStretch(1)
        self.hint_autostop = QLabel()
        self.hint_autostop.setObjectName("Hint")
        auto.addWidget(self._row(self.lbl_autostop, autostop_wrap, self.hint_autostop))

        self.lbl_replay = QLabel()
        self.lbl_replay.setObjectName("RowLabel")
        replay_wrap = QWidget()
        replay_row = QHBoxLayout(replay_wrap)
        replay_row.setContentsMargins(0, 0, 0, 0)
        replay_row.setSpacing(10)
        self.replay_sw = Switch()
        self.replay_sw.setChecked(self.cfg.replay_enabled)
        self.replay_sw.toggled.connect(self._on_replay_toggled)
        replay_row.addWidget(self.replay_sw)
        self.replay_spin = QSpinBox()
        self.replay_spin.setRange(10, 600)
        self.replay_spin.setValue(self.cfg.replay_seconds)
        self.replay_spin.valueChanged.connect(self._on_replay_seconds_changed)
        replay_row.addWidget(self.replay_spin)
        self.replay_unit = QLabel()
        self.replay_unit.setObjectName("Hint")
        replay_row.addWidget(self.replay_unit)
        replay_row.addStretch(1)
        self.hint_replay = QLabel()
        self.hint_replay.setObjectName("Hint")
        auto.addWidget(self._row(self.lbl_replay, replay_wrap, self.hint_replay))
        layout.addWidget(auto_card)

        layout.addStretch(1)
        return page

    def _build_audio_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        mixer_card, mixer = self._card("card_mixer")

        self.mic_gain_slider = QSlider(Qt.Vertical)
        self.mic_gain_slider.setRange(0, 500)
        self.mic_gain_slider.setSingleStep(10)
        self.mic_gain_slider.setPageStep(50)
        self.mic_gain_slider.setMinimumHeight(140)
        self.mic_gain_slider.setValue(round(self.cfg.mic_gain * 100))
        self.mic_gain_slider.valueChanged.connect(self._on_mic_gain_changed)
        self.mic_gain_value = QLabel()
        self.mic_gain_value.setObjectName("StripValue")
        self.mic_gain_value.setAlignment(Qt.AlignCenter)

        self.desk_gain_slider = QSlider(Qt.Vertical)
        self.desk_gain_slider.setRange(0, 500)
        self.desk_gain_slider.setSingleStep(10)
        self.desk_gain_slider.setPageStep(50)
        self.desk_gain_slider.setMinimumHeight(140)
        self.desk_gain_slider.setValue(round(self.cfg.desktop_gain * 100))
        self.desk_gain_slider.valueChanged.connect(self._on_desk_gain_changed)
        self.desk_gain_value = QLabel()
        self.desk_gain_value.setObjectName("StripValue")
        self.desk_gain_value.setAlignment(Qt.AlignCenter)

        self.lbl_mic_gain = QLabel()
        self.lbl_mic_gain.setObjectName("StripName")
        self.lbl_mic_gain.setAlignment(Qt.AlignCenter)
        self.lbl_desk_gain = QLabel()
        self.lbl_desk_gain.setObjectName("StripName")
        self.lbl_desk_gain.setAlignment(Qt.AlignCenter)

        strips = QHBoxLayout()
        strips.setContentsMargins(0, 6, 0, 6)
        strips.setSpacing(16)
        strips.addWidget(self._strip(self.lbl_mic_gain, self.mic_gain_slider, self.mic_gain_value), 1)
        strips.addWidget(self._strip(self.lbl_desk_gain, self.desk_gain_slider, self.desk_gain_value), 1)
        mixer.addLayout(strips)

        self.hint_mixer = QLabel()
        self.hint_mixer.setObjectName("Hint")
        self.hint_mixer.setWordWrap(True)
        mixer.addWidget(self.hint_mixer)
        layout.addWidget(mixer_card)

        # Compatibility aliases
        self.gain_slider = self.mic_gain_slider
        self.gain_value = self.mic_gain_value

        src_card, src = self._card("card_sources")

        self.audio_lbl = QLabel()
        self.audio_lbl.setObjectName("RowLabel")
        audio_wrap = QWidget()
        audio_row = QHBoxLayout(audio_wrap)
        audio_row.setContentsMargins(0, 0, 0, 0)
        self.audio_sw = Switch()
        self.audio_sw.setChecked(self.cfg.audio_enabled)
        self.audio_sw.toggled.connect(self._on_audio_toggled)
        audio_row.addWidget(self.audio_sw)
        audio_row.addStretch(1)
        self.hint_audio = QLabel()
        self.hint_audio.setObjectName("Hint")
        src.addWidget(self._row(self.audio_lbl, audio_wrap, self.hint_audio))

        self.lbl_audio_mode = QLabel()
        self.lbl_audio_mode.setObjectName("RowLabel")
        self.audio_mode_seg = SegmentedControl([
            ("", "mic"),
            ("", "desktop"),
            ("", "both"),
        ])
        self.audio_mode_seg.set_current_data(self.cfg.audio_mode)
        self.audio_mode_seg.changed.connect(self._on_audio_mode_changed)
        self.hint_audio_mode = QLabel()
        self.hint_audio_mode.setObjectName("Hint")
        src.addWidget(self._row(self.lbl_audio_mode, self.audio_mode_seg, self.hint_audio_mode))

        self.lbl_source_name = QLabel()
        self.lbl_source_name.setObjectName("RowLabel")
        self.audio_source_edit = QLineEdit(self.cfg.audio_source)
        self.audio_source_edit.setPlaceholderText("auto")
        self.audio_source_edit.textChanged.connect(self._on_audio_source_changed)
        self.source_edit = self.audio_source_edit
        self.hint_source = QLabel()
        self.hint_source.setObjectName("Hint")
        src.addWidget(self._row(self.lbl_source_name, self.audio_source_edit, self.hint_source))

        self.lbl_desktop_source_name = QLabel()
        self.lbl_desktop_source_name.setObjectName("RowLabel")
        self.audio_desktop_edit = QLineEdit(self.cfg.audio_desktop_source)
        self.audio_desktop_edit.setPlaceholderText("auto")
        self.audio_desktop_edit.textChanged.connect(self._on_audio_desktop_changed)
        self.desktop_source_edit = self.audio_desktop_edit
        self.hint_desktop = QLabel()
        self.hint_desktop.setObjectName("Hint")
        src.addWidget(self._row(self.lbl_desktop_source_name, self.audio_desktop_edit, self.hint_desktop))

        layout.addWidget(src_card)
        layout.addStretch(1)
        return page

    def _build_region_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        card, body = self._card("label_region")

        self.lbl_region = QLabel()
        self.lbl_region.setObjectName("RowLabel")
        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.region_spins: dict[str, QSpinBox] = {}
        for i, (key, value) in enumerate((
            ("x", self.cfg.region_x),
            ("y", self.cfg.region_y),
            ("w", self.cfg.region_w),
            ("h", self.cfg.region_h),
        )):
            spin = QSpinBox()
            spin.setPrefix(f"{key.upper()} ")
            spin.setRange(0, 10000)
            spin.setValue(value)
            spin.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            spin.valueChanged.connect(self._on_region_changed)
            spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.region_spins[key] = spin
            grid.addWidget(spin, i // 2, i % 2)

        # Quick preset buttons (1080p, 720p, Reset)
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 4, 0, 0)
        preset_row.setSpacing(8)

        btn_1080 = QPushButton(self.t("region_preset_1080"))
        btn_1080.setCursor(Qt.PointingHandCursor)
        btn_1080.clicked.connect(lambda: self._apply_region_preset(0, 0, 1920, 1080))
        preset_row.addWidget(btn_1080)

        btn_720 = QPushButton(self.t("region_preset_720"))
        btn_720.setCursor(Qt.PointingHandCursor)
        btn_720.clicked.connect(lambda: self._apply_region_preset(0, 0, 1280, 720))
        preset_row.addWidget(btn_720)

        btn_reset = QPushButton(self.t("region_preset_full"))
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(lambda: self._apply_region_preset(0, 0, 0, 0))
        preset_row.addWidget(btn_reset)
        preset_row.addStretch(1)
        self.region_preset_btns = [btn_1080, btn_720, btn_reset]

        body.addWidget(self._row(self.lbl_region, grid_wrap))
        body.addLayout(preset_row)

        self.hint_region = QLabel()
        self.hint_region.setObjectName("Hint")
        self.hint_region.setWordWrap(True)
        body.addWidget(self.hint_region)

        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _apply_region_preset(self, x: int, y: int, w: int, h: int) -> None:
        if "x" in self.region_spins:
            self.region_spins["x"].setValue(x)
        if "y" in self.region_spins:
            self.region_spins["y"].setValue(y)
        if "w" in self.region_spins:
            self.region_spins["w"].setValue(w)
        if "h" in self.region_spins:
            self.region_spins["h"].setValue(h)

    def _build_output_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        store_card, store = self._card("card_storage")

        self.lbl_output_folder = QLabel()
        self.lbl_output_folder.setObjectName("RowLabel")
        folder_wrap = QWidget()
        folder_row = QHBoxLayout(folder_wrap)
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(8)
        self.output_edit = QLineEdit(str(self.cfg.output_dir))
        self.output_edit.textChanged.connect(self._on_output_dir_changed)
        folder_row.addWidget(self.output_edit, 1)
        self.browse_btn = QPushButton()
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self.browse_output_folder)
        folder_row.addWidget(self.browse_btn)
        self.hint_output = QLabel()
        self.hint_output.setObjectName("Hint")
        store.addWidget(self._row(self.lbl_output_folder, folder_wrap, self.hint_output))

        self.lbl_disk = QLabel()
        self.lbl_disk.setObjectName("RowLabel")
        self.disk_value = QLabel()
        self.disk_value.setObjectName("Hint")
        store.addWidget(self._row(self.lbl_disk, self.disk_value))

        self.lbl_prefix = QLabel()
        self.lbl_prefix.setObjectName("RowLabel")
        self.prefix_edit = QLineEdit(self.cfg.filename_prefix)
        self.prefix_edit.setMaxLength(32)
        self.prefix_edit.textChanged.connect(self._on_prefix_changed)
        self.hint_prefix = QLabel()
        self.hint_prefix.setObjectName("Hint")
        store.addWidget(self._row(self.lbl_prefix, self.prefix_edit, self.hint_prefix))

        self.lbl_format = QLabel()
        self.lbl_format.setObjectName("RowLabel")
        self.format_seg = SegmentedControl([("MP4", "mp4"), ("MKV", "mkv")])
        self.format_seg.set_current_data(self.cfg.output_format)
        self.format_seg.changed.connect(self._on_format_changed)
        self.hint_format = QLabel()
        self.hint_format.setObjectName("Hint")
        store.addWidget(self._row(self.lbl_format, self.format_seg, self.hint_format))
        layout.addWidget(store_card)

        # Recent Recordings Card
        self.lbl_recent = QLabel()
        self.lbl_recent.setObjectName("SectionTitle")
        recent_card = QFrame()
        recent_card.setObjectName("Card")
        rc_outer = QVBoxLayout(recent_card)
        rc_outer.setContentsMargins(18, 14, 18, 14)
        rc_outer.setSpacing(10)
        rc_outer.addWidget(self.lbl_recent)

        recent_wrap = QWidget()
        recent_col = QVBoxLayout(recent_wrap)
        recent_col.setContentsMargins(0, 0, 0, 0)
        recent_col.setSpacing(8)

        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(140)
        self.recent_list.itemDoubleClicked.connect(lambda _item: self._open_selected_recording())
        recent_col.addWidget(self.recent_list)

        recent_btns = QHBoxLayout()
        recent_btns.setContentsMargins(0, 0, 0, 0)
        recent_btns.setSpacing(8)
        self.recent_open_btn = QPushButton()
        self.recent_open_btn.setCursor(Qt.PointingHandCursor)
        self.recent_open_btn.clicked.connect(self._open_selected_recording)
        recent_btns.addWidget(self.recent_open_btn)

        self.recent_refresh_btn = QPushButton()
        self.recent_refresh_btn.setCursor(Qt.PointingHandCursor)
        self.recent_refresh_btn.clicked.connect(self._refresh_recent)
        recent_btns.addWidget(self.recent_refresh_btn)
        recent_btns.addStretch(1)

        recent_col.addLayout(recent_btns)
        rc_outer.addWidget(recent_wrap)
        layout.addWidget(recent_card)

        layout.addStretch(1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        gen_card, gen = self._card("card_general")

        self.lbl_language = QLabel()
        self.lbl_language.setObjectName("RowLabel")
        self.lang_seg = SegmentedControl([
            (LANGUAGE_LABELS[code], code) for code in SUPPORTED_LANGUAGES
        ])
        self.lang_seg.set_current_data(self.cfg.language)
        self.lang_seg.changed.connect(self._on_language_changed)
        self.hint_language = QLabel()
        self.hint_language.setObjectName("Hint")
        gen.addWidget(self._row(self.lbl_language, self.lang_seg, self.hint_language))

        self.lbl_theme = QLabel()
        self.lbl_theme.setObjectName("RowLabel")
        self.theme_seg = SegmentedControl([
            ("", name) for name in theme_mod.SUPPORTED_THEMES
        ])
        self.theme_seg.set_current_data(self.cfg.theme)
        self.theme_seg.changed.connect(self._on_theme_changed)
        self.hint_theme = QLabel()
        self.hint_theme.setObjectName("Hint")
        gen.addWidget(self._stacked_row(self.lbl_theme, self.theme_seg, self.hint_theme))
        layout.addWidget(gen_card)

        sc_card, sc_body = self._card("card_shortcuts")
        self.lbl_shortcuts = QLabel()
        self.lbl_shortcuts.setObjectName("RowLabel")
        sc_wrap = QWidget()
        sc_grid = QGridLayout(sc_wrap)
        sc_grid.setContentsMargins(0, 0, 0, 0)
        sc_grid.setHorizontalSpacing(12)
        sc_grid.setVerticalSpacing(10)
        self.sc_edits: dict[str, QLineEdit] = {}
        for i, (key, attr) in enumerate((
            ("shortcut_record", "shortcut_record"),
            ("shortcut_pause", "shortcut_pause"),
            ("shortcut_replay", "shortcut_replay"),
            ("shortcut_folder", "shortcut_folder"),
        )):
            edit = QLineEdit(getattr(self.cfg, attr))
            edit.setMaxLength(32)
            edit.setPlaceholderText(attr)
            edit.editingFinished.connect(self._on_shortcuts_edited)
            self.sc_edits[attr] = edit
            sc_grid.addWidget(edit, i // 2, (i % 2) * 2 + 1)
            tag = QLabel()
            tag.setObjectName("RowLabel")
            tag.setProperty("sc_key", key)
            sc_grid.addWidget(tag, i // 2, (i % 2) * 2)

        self._sc_tags = [
            sc_grid.itemAtPosition(r, c).widget()
            for r in range(2)
            for c in (0, 2)
        ]
        self.hint_shortcuts = QLabel()
        self.hint_shortcuts.setObjectName("Hint")
        sc_body.addWidget(self._row(self.lbl_shortcuts, sc_wrap, self.hint_shortcuts))
        layout.addWidget(sc_card)

        layout.addStretch(1)
        return page

    def _build_transport(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Transport")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        self.record_btn = RecordButton()
        self.record_btn.clicked.connect(self.toggle)
        self.record_btn.setMinimumHeight(48)
        row.addWidget(self.record_btn, 1)

        self.pause_btn = QPushButton()
        self.pause_btn.setObjectName("Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setMinimumWidth(118)
        self.pause_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.pause_btn.setMinimumHeight(48)
        row.addWidget(self.pause_btn)

        self.replay_btn = QPushButton()
        self.replay_btn.setObjectName("Pause")
        self.replay_btn.setCursor(Qt.PointingHandCursor)
        self.replay_btn.clicked.connect(self.save_replay_clip)
        self.replay_btn.setMinimumWidth(132)
        self.replay_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.replay_btn.setMinimumHeight(48)
        row.addWidget(self.replay_btn)

        return bar

    def _build_statusbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(FOOTER_H + 2)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(10)

        self.status_dot = StatusDot()
        row.addWidget(self.status_dot)

        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("StatusText")
        self.status_lbl.setProperty("error", False)
        self.status_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(self.status_lbl, 1)

        self.out_lbl = QLabel()
        self.out_lbl.setObjectName("OutPath")
        self.out_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.out_lbl)

        self.folder_btn = QPushButton()
        self.folder_btn.setObjectName("FolderBtn")
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.setFixedSize(28, 28)
        self.folder_btn.clicked.connect(self.open_output_folder)
        row.addWidget(self.folder_btn)

        return bar

    # --- Translations and Status Refresh ---

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
        lang = self.cfg.language
        self.subtitle_lbl.setText(_get("subtitle", lang))
        self._refresh_idle_status()

        recording = self.rec.state.active
        self.record_btn.setText(
            _get("rec_stop", lang) if recording else _get("rec_start", lang)
        )
        self.pause_btn.setText(
            _get("resume", lang) if self.rec.state.paused else _get("pause", lang)
        )
        self._refresh_state_dot()

        for btn, key in zip(
            self.tab_buttons,
            ("tab_studio", "tab_capture", "tab_audio", "tab_region", "tab_output", "tab_settings"),
        ):
            btn.setText(_get(key, lang))
            btn.update()

        self._refresh_preview_badge(self.rec.state.active)
        self.lbl_camera_on.setText(_get("label_camera_on", lang))
        self.lbl_camera_device.setText(_get("label_camera_device", lang))
        self.lbl_camera_embed.setText(_get("label_camera_embed", lang))
        self.hint_camera_embed.setText(_get("camera_embed_hint", lang))
        self.hint_camera.setText(_get("camera_hint", lang))
        self.hint_sources.setText(_get("sources_hint", lang))
        self._refresh_camera_devices()
        self._refresh_sources()
        self._sync_studio_controls()

        self.lbl_source.setText(_get("label_source", lang))
        self.mode_seg.set_labels([
            _get("mode_fullscreen", lang),
            _get("mode_window", lang),
            _get("mode_ask", lang),
        ])
        self._refresh_mode_hint()
        self.lbl_quality.setText(_get("label_quality", lang))
        self.quality_seg.set_labels([
            _get("quality_draft", lang),
            _get("quality_balanced", lang),
            _get("quality_high", lang),
            _get("quality_custom", lang),
        ])
        self._refresh_quality_hint()
        self.lbl_fps.setText(_get("label_fps", lang))
        self.lbl_bitrate.setText(_get("label_bitrate", lang))

        self.audio_lbl.setText(_get("audio_check", lang))
        self.lbl_audio_mode.setText(_get("audio_mode", lang))
        self.audio_mode_seg.set_labels([
            _get("audio_mode_mic", lang),
            _get("audio_mode_desktop", lang),
            _get("audio_mode_both", lang),
        ])
        self._refresh_audio_mode_hint()
        self.lbl_mic_gain.setText(_get("label_mic_gain", lang))
        self.lbl_desk_gain.setText(_get("label_desktop_gain", lang))
        self.hint_mixer.setText(_get("mixer_hint", lang))
        self.lbl_source_name.setText(_get("label_source_name", lang))
        self.lbl_desktop_source_name.setText(_get("label_desktop_source", lang))
        self.hint_audio.setText(_get("audio_hint", lang))
        self._refresh_gain_labels()

        self.lbl_region.setText(_get("label_region", lang))
        self.hint_region.setText(_get("region_hint", lang))
        self.region_preset_btns[0].setText(_get("region_preset_1080", lang))
        self.region_preset_btns[1].setText(_get("region_preset_720", lang))
        self.region_preset_btns[2].setText(_get("region_preset_full", lang))

        self.lbl_cursor.setText(_get("label_cursor", lang))
        self.hint_cursor.setText(_get("cursor_hint", lang))
        self.lbl_countdown.setText(_get("label_countdown", lang))
        self.countdown_seg.set_labels([
            _get("countdown_off", lang) if v == 0 else f"{v}s"
            for v in COUNTDOWN_CHOICES
        ])
        self.hint_countdown.setText(_get("countdown_hint", lang))
        self.lbl_autostop.setText(_get("label_autostop", lang))
        self.autostop_unit.setText(_get("autostop_minutes", lang))
        self.hint_autostop.setText(_get("autostop_hint", lang))
        self.lbl_replay.setText(_get("label_replay", lang))
        self.replay_unit.setText(_get("replay_seconds", lang))
        self.hint_replay.setText(_get("replay_hint", lang))
        self.replay_btn.setText(_get("replay_save", lang))

        self.lbl_output_folder.setText(_get("label_output_folder", lang))
        self.browse_btn.setText(_get("output_browse", lang))
        self.hint_output.setText(_get("output_hint", lang))
        self.lbl_disk.setText(_get("label_disk", lang))
        self.lbl_prefix.setText(_get("label_prefix", lang))
        self.hint_prefix.setText(_get("prefix_hint", lang))
        self.lbl_format.setText(_get("label_format", lang))
        self.hint_format.setText(_get("format_hint", lang))
        self.lbl_recent.setText(_get("label_recent", lang))
        self.recent_open_btn.setText(_get("recent_open", lang))
        self.recent_refresh_btn.setText(_get("recent_refresh", lang))
        self._refresh_disk_label()
        self._refresh_recent()

        self.lbl_language.setText(_get("label_language", lang))
        self.hint_language.setText(_get("language_hint", lang))
        self.lbl_theme.setText(_get("label_theme", lang))
        self.theme_seg.set_labels([
            _get(f"theme_{name}", lang) for name in theme_mod.SUPPORTED_THEMES
        ])
        self.hint_theme.setText(_get("theme_hint", lang))
        self.lbl_shortcuts.setText(_get("label_shortcuts", lang))
        self.hint_shortcuts.setText(_get("shortcuts_hint", lang))
        for tag in getattr(self, "_sc_tags", []):
            key = tag.property("sc_key")
            if key:
                tag.setText(_get(key, lang))

        self.backend_lbl.setText(_get("backend_line", lang).format(name=self.rec.name))
        for title in self._card_labels:
            key = title.property("i18n")
            if key:
                title.setText(_get(key, lang))
        self.folder_btn.setToolTip(_get("open_folder", lang))
        self._refresh_outcome()
        self._paint_folder_icon()
        self._refresh_tray()
        self._refresh_title()

    def _paint_folder_icon(self) -> None:
        size = self.folder_btn.size()
        if size.width() <= 0:
            return
        pix = QPixmap(size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        inset = 5.0
        paint_icon(
            p,
            "folder",
            QRectF(inset, inset, size.width() - 2 * inset, size.height() - 2 * inset),
            QColor(self.theme["TEXT_SOFT"]),
        )
        p.end()
        self.folder_btn.setIcon(QIcon(pix))

    def _refresh_outcome(self) -> None:
        path = str(self.cfg.output_dir)
        try:
            pretty = str(Path(path).relative_to(Path.home()))
            pretty = "~/" + pretty
        except ValueError:
            pretty = path
        metrics = QFontMetrics(self.out_lbl.font())
        self.out_lbl.setText(
            metrics.elidedText(pretty, Qt.ElideMiddle, self.OUT_PATH_PX)
        )
        self.out_lbl.setToolTip(path)
        self._paint_folder_icon()

    def _refresh_state_dot(self) -> None:
        if self._countdown_timer.isActive():
            self.status_dot.set_color(self.theme["PAUSED"])
            state, pill = "countdown", f"{self._countdown_left}s"
        elif self.rec.state.paused:
            self.status_dot.set_color(self.theme["PAUSED"])
            state, pill = "paused", self.t("pill_paused")
        elif self.rec.state.active:
            self.status_dot.set_color(self.theme["REC"])
            state, pill = "recording", self.t("pill_recording")
        else:
            self.status_dot.set_color(self.theme["READY"])
            state, pill = "ready", self.t("pill_ready")
        self.state_pill.setText(pill)
        self.state_pill.setProperty("state", state)
        _repolish(self.state_pill)

    def _refresh_mode_hint(self) -> None:
        self.hint_mode.setText(self.t(f"mode_{self.mode_seg.current_data()}_hint"))

    def _refresh_quality_hint(self) -> None:
        self.hint_quality.setText(
            self.t(f"quality_{self.quality_seg.current_data()}_hint")
        )

    def _refresh_audio_mode_hint(self) -> None:
        self.hint_audio_mode.setText(
            self.t(f"audio_mode_{self.audio_mode_seg.current_data()}_hint")
        )

    def _refresh_gain_labels(self) -> None:
        self.mic_gain_value.setText(
            self.t("gain_value").format(pct=self.mic_gain_slider.value())
        )
        self.desk_gain_value.setText(
            self.t("gain_value").format(pct=self.desk_gain_slider.value())
        )

    def _refresh_gain_label(self) -> None:
        self._refresh_gain_labels()

    def _on_language_changed(self, code: str) -> None:
        if not code:
            return
        self.cfg.language = normalize(code)
        try:
            self.rec.cfg.language = self.cfg.language
        except AttributeError:
            pass
        self._retranslate()
        self.cfg.save()

    def apply_theme(self, name: str) -> None:
        """Switch active theme and remember choice."""
        self.cfg.theme = theme_mod.normalize_theme(name)
        self.theme = theme_mod.get_theme(self.cfg.theme)
        self.theme_seg.set_current_data(self.cfg.theme)
        self.setStyleSheet(build_stylesheet(self.theme))
        self._refresh_state_dot()
        self._paint_folder_icon()
        for btn in self.tab_buttons:
            btn.update()
        self.header_mark.update()
        self.audio_sw.update()
        self.cursor_sw.update()
        self.record_btn.update()
        self.cfg.save()

    def _on_theme_changed(self, name: str) -> None:
        if not name:
            return
        self.apply_theme(name)

    def _select_tab(self, code: str) -> None:
        self.pages.setCurrentWidget(self.pages.widget(self._page_index(code)))

    def _page_index(self, code: str) -> int:
        return ("studio", "capture", "audio", "region", "output", "settings").index(code)

    def _setup_shortcuts(self) -> None:
        self._shortcuts: list[QShortcut] = []
        self._refresh_shortcuts()

    def _refresh_shortcuts(self) -> None:
        for sc in getattr(self, "_shortcuts", []):
            try:
                sc.setEnabled(False)
                sc.deleteLater()
            except Exception:
                pass
        self._shortcuts = []

        def _add(seq: str, slot) -> None:
            try:
                sc = QShortcut(QKeySequence(seq), self)
            except Exception:
                return
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(slot)
            self._shortcuts.append(sc)

        _add(self.cfg.shortcut_record, self.toggle)
        _add("Space", self.toggle)
        _add(self.cfg.shortcut_pause, self.toggle_pause)
        _add(self.cfg.shortcut_folder, self.open_output_folder)
        _add(self.cfg.shortcut_replay, self.save_replay_clip)

    # --- System Tray ---

    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
        except Exception:
            return
        tray = QSystemTrayIcon(tray_icon("#FFFFFF"), self)
        menu = QMenu()
        self.tray_toggle_act = menu.addAction("")
        self.tray_toggle_act.triggered.connect(self._tray_toggle_window)
        self.tray_record_act = menu.addAction("")
        self.tray_record_act.triggered.connect(self.toggle)
        self.tray_folder_act = menu.addAction("")
        self.tray_folder_act.triggered.connect(self.open_output_folder)
        menu.addSeparator()
        self.tray_quit_act = menu.addAction("")
        self.tray_quit_act.triggered.connect(self._tray_quit)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        self.tray = tray
        self._refresh_tray()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._tray_toggle_window()

    def _tray_toggle_window(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def _tray_quit(self) -> None:
        self._quit_requested = True
        self.close()

    def _notify(self, message: str) -> None:
        if self.tray is None:
            return
        try:
            self.tray.showMessage("CastMane", message, QSystemTrayIcon.Information, 4000)
        except Exception:
            pass

    @staticmethod
    def _fmt_elapsed(seconds: float) -> str:
        total = int(max(0, seconds))
        return f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}"

    def _refresh_tray(self) -> None:
        if self.tray is None:
            return
        lang = self.cfg.language
        elapsed = self._fmt_elapsed(self.rec.elapsed)
        if self.rec.state.paused:
            tip = _get("tray_paused", lang).format(elapsed=elapsed)
        elif self.rec.state.active:
            tip = _get("tray_recording", lang).format(elapsed=elapsed)
        else:
            tip = _get("tray_ready", lang)
        self.tray.setToolTip(tip)
        recording = self.rec.state.active
        self.tray_toggle_act.setText(
            _get("tray_hide", lang) if self.isVisible() else _get("tray_show", lang)
        )
        self.tray_record_act.setText(
            _get("tray_stop", lang) if recording else _get("tray_record", lang)
        )
        self.tray_folder_act.setText(_get("tray_open_folder", lang))
        self.tray_quit_act.setText(_get("tray_quit", lang))

    def _refresh_title(self) -> None:
        if self.rec.state.active:
            marker = "❚❚" if self.rec.state.paused else "●"
            self.setWindowTitle(f"{marker} {self.timer_lbl.text()} — CastMane")
        else:
            self.setWindowTitle("CastMane")

    # --- Studio: preview, sources, camera ---

    def _refresh_preview_badge(self, live: bool) -> None:
        state = "recording" if live else "ready"
        self.preview_badge.setText(
            self.t("pill_recording") if live else self.t("pill_ready")
        )
        self.preview_badge.setProperty("state", state)
        _repolish(self.preview_badge)
        self.preview_status.setText(
            self.t("preview_live") if live else self.t("preview_idle")
        )

    def _begin_screen_preview(self) -> None:
        """Play the growing `.part` file: the actual encoder output,
        ~2 s behind the live screen. Delayed 1.5 s after start so the
        container header exists before Qt opens it."""
        if not self.rec.state.active or self.preview_player is None:
            return
        tmp = self.rec.state.tmp_path
        if tmp is None:
            return
        try:
            self.preview_player.setSource(QUrl.fromLocalFile(str(tmp)))
            self.preview_player.play()
            self.preview_status.setText(self.t("preview_wait"))
        except Exception as e:  # noqa: BLE001 - preview is best-effort
            self.preview_status.setText(
                self.t("preview_failed").format(err=e)
            )

    def _end_screen_preview(self) -> None:
        try:
            if self.preview_player is not None:
                self.preview_player.stop()
                self.preview_player.setSource(QUrl())
        except Exception:  # noqa: BLE001 - best-effort teardown
            pass
        self._refresh_preview_badge(False)

    def _on_preview_error(self, _error, error_string: str = "") -> None:
        if self.rec.state.active:
            self.preview_status.setText(
                self.t("preview_failed").format(err=error_string or "?")
            )

    def _on_preview_playing(self, playing: bool) -> None:
        if playing and self.rec.state.active:
            self._refresh_preview_badge(True)

    def _on_preview_media_status(self, status) -> None:
        # A growing file can hit a transient end-of-media; loop while
        # the recording is still running.
        try:
            end = QMediaPlayer.EndOfMedia
        except AttributeError:
            return
        if status == end and self.rec.state.active:
            try:
                if self.preview_player is not None:
                    self.preview_player.play()
            except Exception:  # noqa: BLE001 - best-effort
                pass

    def _refresh_camera_devices(self) -> None:
        from .camera import list_cameras

        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()
        self.camera_combo.addItem("auto", "auto")
        for path, label in list_cameras():
            self.camera_combo.addItem(label if label != path else path, path)
        idx = self.camera_combo.findData(self.cfg.camera_device)
        self.camera_combo.setCurrentIndex(max(0, idx))
        self.camera_combo.blockSignals(False)

    def _refresh_camera_preview(self) -> None:
        try:
            if self._cam is not None:
                self._cam.stop()
        except Exception:  # noqa: BLE001 - best-effort teardown
            pass
        self._cam = None
        self._cam_session = None
        if not self.cfg.camera_enabled:
            self.cam_view.hide()
            self.cam_status.setText(self.t("camera_preview_off"))
            return
        try:
            from .camera import resolve_camera_device

            dev_path = resolve_camera_device(self.cfg.camera_device)
            devices = QMediaDevices.videoInputs()
            chosen = devices[0] if devices else None
            if dev_path and devices:
                tail = dev_path.rsplit("video", 1)[-1]
                if tail.isdigit() and int(tail) < len(devices):
                    chosen = devices[int(tail)]
            cam = QCamera(chosen) if chosen is not None else QCamera()
            session = QMediaCaptureSession()
            session.setCamera(cam)
            session.setVideoOutput(self.cam_view)
            try:
                cam.errorOccurred.connect(self._on_camera_error)
            except Exception:  # noqa: BLE001 - older Qt without the signal
                pass
            cam.start()
            self._cam = cam
            self._cam_session = session
            self.cam_view.show()
            self.cam_status.setText(dev_path or self.t("camera_none"))
        except Exception:  # noqa: BLE001 - no camera backend, show label
            self.cam_view.hide()
            self.cam_status.setText(self.t("camera_unavailable"))

    def _on_camera_error(self, _error, _message: str = "") -> None:
        self.cam_status.setText(self.t("camera_unavailable"))

    def _on_camera_toggled(self, checked: bool) -> None:
        self.cfg.camera_enabled = checked
        try:
            self.rec.cfg.camera_enabled = checked
        except AttributeError:
            pass
        self.cfg.save()
        self._refresh_camera_preview()
        self._refresh_sources()

    def _on_camera_embed_toggled(self, checked: bool) -> None:
        self.cfg.camera_embed = checked
        try:
            self.rec.cfg.camera_embed = checked
        except AttributeError:
            pass
        self.cfg.save()

    def _on_camera_device_changed(self, index: int) -> None:
        if index < 0:
            return
        from .camera import normalize_camera_device

        data = self.camera_combo.itemData(index) or "auto"
        self.cfg.camera_device = normalize_camera_device(str(data))
        try:
            self.rec.cfg.camera_device = self.cfg.camera_device
        except AttributeError:
            pass
        self.cfg.save()
        self._refresh_camera_preview()

    def _source_item(self, key: str) -> QListWidgetItem | None:
        for row in range(self.sources_list.count()):
            item = self.sources_list.item(row)
            if item.data(Qt.UserRole) == key:
                return item
        return None

    def _refresh_sources(self) -> None:
        from .audio import normalize_audio_mode

        mode = normalize_audio_mode(self.cfg.audio_mode)
        states = {
            "camera": self.cfg.camera_enabled,
            "mic": self.cfg.audio_enabled and mode in ("mic", "both"),
            "desktop": self.cfg.audio_enabled and mode in ("desktop", "both"),
        }
        self.sources_list.blockSignals(True)
        for row in range(self.sources_list.count()):
            item = self.sources_list.item(row)
            key = item.data(Qt.UserRole)
            item.setText(self.t(f"source_{key}"))
            try:
                item.setToolTip(self.t(f"source_{key}_hint"))
            except Exception:  # noqa: BLE001 - missing hint never breaks UI
                pass
            if key in states:
                item.setCheckState(
                    Qt.Checked if states[key] else Qt.Unchecked
                )
        self.sources_list.blockSignals(False)

    def _on_source_toggled(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.UserRole)
        checked = item.checkState() == Qt.Checked
        if key == "display":
            return
        if key == "camera":
            self.camera_sw.blockSignals(True)
            self.camera_sw.setChecked(checked)
            self.camera_sw.blockSignals(False)
            self._on_camera_toggled(checked)
            return
        if key in ("mic", "desktop"):
            mic_item = self._source_item("mic")
            desk_item = self._source_item("desktop")
            mic = (
                mic_item.checkState() == Qt.Checked
                if mic_item is not None
                else False
            )
            desk = (
                desk_item.checkState() == Qt.Checked
                if desk_item is not None
                else False
            )
            if mic and desk:
                self.cfg.audio_enabled = True
                self.cfg.audio_mode = "both"
            elif mic:
                self.cfg.audio_enabled = True
                self.cfg.audio_mode = "mic"
            elif desk:
                self.cfg.audio_enabled = True
                self.cfg.audio_mode = "desktop"
            else:
                self.cfg.audio_enabled = False
            try:
                self.rec.cfg.audio_enabled = self.cfg.audio_enabled
                self.rec.cfg.audio_mode = self.cfg.audio_mode
            except AttributeError:
                pass
            self.audio_sw.blockSignals(True)
            self.audio_sw.setChecked(self.cfg.audio_enabled)
            self.audio_sw.blockSignals(False)
            self.audio_mode_seg.set_current_data(self.cfg.audio_mode)
            self._refresh_audio_mode_hint()
            self.cfg.save()
            self._refresh_sources()

    def _sync_studio_controls(self) -> None:
        recording = self.rec.state.active
        self.studio_pause_btn.setText(
            self.t("resume") if self.rec.state.paused else self.t("pause")
        )
        self.studio_pause_btn.setEnabled(recording)
        self.studio_replay_btn.setText(self.t("replay_save"))

    # --- Recording Control ---

    def _set_recording_ui(self, recording: bool) -> None:
        self.record_btn.set_recording(recording)
        self.timer_lbl.setProperty("recording", recording)
        _repolish(self.timer_lbl)
        self._refresh_state_dot()

    def _set_inputs_enabled(self, enabled: bool) -> None:
        self.mode_seg.set_enabled(enabled)
        self.quality_seg.set_enabled(enabled)
        self.format_seg.set_enabled(enabled)
        self.cursor_sw.setEnabled(enabled)
        self.countdown_seg.set_enabled(enabled)
        self.autostop_spin.setEnabled(enabled)
        self.replay_sw.setEnabled(enabled)
        self.replay_spin.setEnabled(enabled)
        self.lang_seg.set_enabled(enabled)
        self.theme_seg.set_enabled(enabled)
        self.audio_sw.setEnabled(enabled)
        self.audio_mode_seg.set_enabled(enabled)
        self.mic_gain_slider.setEnabled(enabled)
        self.desk_gain_slider.setEnabled(enabled)
        self.audio_source_edit.setEnabled(enabled)
        self.audio_desktop_edit.setEnabled(enabled)
        self.output_edit.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self.prefix_edit.setEnabled(enabled)
        # Studio sources/camera reconfigure the next pipeline, so they
        # are locked while the encoder runs (like OBS locks inputs).
        self.sources_list.setEnabled(enabled)
        self.camera_sw.setEnabled(enabled)
        self.camera_combo.setEnabled(enabled)
        self.camera_embed_sw.setEnabled(enabled)
        if enabled:
            self._refresh_custom_enabled()
        else:
            self.fps_spin.setEnabled(False)
            self.br_spin.setEnabled(False)
        self._set_region_enabled(enabled)

    def toggle(self) -> None:
        if self._bg_thread is not None:
            # Still finalizing the previous take; a new one would fight it.
            return
        if self._countdown_timer.isActive():
            self._countdown_timer.stop()
            self._countdown_left = 0
            self.timer_lbl.setText("00:00:00")
            self._refresh_idle_status()
            self._set_inputs_enabled(True)
            self._refresh_state_dot()
            return
        if not self.rec.state.active:
            if self.cfg.countdown_s > 0:
                self._countdown_left = self.cfg.countdown_s
                self._set_inputs_enabled(False)
                self.status_lbl.setText(
                    self.t("countdown_status").format(n=self._countdown_left)
                )
                self.timer_lbl.setText(self._fmt_elapsed(self._countdown_left))
                self._refresh_state_dot()
                self._countdown_timer.start()
                return
            self._start_recording()
        else:
            self._stop_recording()

    def _countdown_tick(self) -> None:
        self._countdown_left -= 1
        if self._countdown_left <= 0:
            self._countdown_timer.stop()
            self._start_recording()
            return
        self.status_lbl.setText(
            self.t("countdown_status").format(n=self._countdown_left)
        )
        self.timer_lbl.setText(self._fmt_elapsed(self._countdown_left))
        self._refresh_state_dot()

    def _start_recording(self) -> None:
        free_mb = self.cfg.output_dir_free_mb()
        if free_mb is not None and free_mb < MIN_FREE_MB:
            self._set_inputs_enabled(True)
            self.timer_lbl.setText("00:00:00")
            self._fail(self.t("disk_low").format(mb=free_mb))
            return
        try:
            final = self.rec.start()
        except FileNotFoundError:
            self._set_inputs_enabled(True)
            self._fail(self.t("deps_missing"))
            return
        except Exception as e:
            self._set_inputs_enabled(True)
            self._fail(self.t("start_failed").format(err=e))
            return
        self._clear_error()
        tmp = self.rec.state.tmp_path
        self.status_lbl.setText(
            self.t("recording_to").format(name=tmp.name if tmp else final.name)
        )
        self.record_btn.setText(self.t("rec_stop"))
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText(self.t("pause"))
        self._set_inputs_enabled(False)
        self._set_recording_ui(True)
        self._sync_studio_controls()
        QTimer.singleShot(1500, self._begin_screen_preview)
        self.timer.start()
        if self.cfg.auto_stop_min > 0:
            self._autostop_remaining_ms = self.cfg.auto_stop_min * 60 * 1000
            self._autostop_timer.start(self._autostop_remaining_ms)
        else:
            self._autostop_remaining_ms = 0
        self._notify(self.t("notify_started"))
        self._refresh_tray()
        self._refresh_title()

    def _stop_recording(self, reason: str = "", quit_after: bool = False) -> None:
        """Ask the encoder to stop. The blocking part (graceful shutdown plus
        the crash-safe remux) runs on a worker thread; `tick()` applies the
        result, so the window stays responsive while finalizing."""
        if self._bg_thread is not None:
            return
        self._countdown_timer.stop()
        self._autostop_timer.stop()
        self._autostop_remaining_ms = 0
        self._countdown_left = 0
        self._end_screen_preview()
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText(self.t("pause"))
        self._sync_studio_controls()
        self.record_btn.setEnabled(False)
        self.replay_btn.setEnabled(False)
        self.studio_replay_btn.setEnabled(False)
        self.status_lbl.setText(self.t("finalizing"))
        self._refresh_tray()
        self._refresh_title()
        self._bg_kind = "stop"
        self._bg_result = None
        self._bg_error = ""
        self._bg_reason = reason
        self._bg_quit_after = quit_after
        self._bg_thread = threading.Thread(
            target=self._stop_worker, args=(self.rec,), daemon=True
        )
        self._bg_thread.start()

    def _stop_worker(self, rec) -> None:
        """Worker: never touches widgets."""
        try:
            self._bg_result = rec.stop()
        except Exception as e:  # noqa: BLE001 - reported on the UI thread
            self._bg_error = str(e)
        finally:
            self._bg_finished.emit()

    def _replay_worker(self, segments: list[Path], dest: Path) -> None:
        """Worker: concat can block for a while, keep the UI alive."""
        from . import replay as replay_mod

        try:
            self._bg_result = dest if replay_mod.save_replay(segments, dest) else None
        except Exception as e:  # noqa: BLE001 - reported on the UI thread
            self._bg_error = str(e)
        finally:
            self._bg_finished.emit()

    def _poll_background(self) -> bool:
        """`tick()` hook: true while a worker is still running."""
        thread = self._bg_thread
        if thread is None:
            return False
        if thread.is_alive():
            return True
        self._bg_thread = None
        kind, self._bg_kind = self._bg_kind, ""
        if kind == "stop":
            self._apply_stop_result()
        elif kind == "replay":
            self._apply_replay_result()
        return False

    def _apply_stop_result(self) -> None:
        self.timer.stop()
        self._set_inputs_enabled(True)
        out = self._bg_result
        reason, self._bg_reason = self._bg_reason, ""
        quit_after, self._bg_quit_after = self._bg_quit_after, False
        if self._bg_error:
            self._fail(self.t("error_prefix").format(err=self._bg_error))
            self._bg_error = ""
        elif out:
            self._clear_error()
            self.status_lbl.setText(self.t("saved").format(out=out))
            self._refresh_recent()
            self._notify(
                self.t("notify_autostop")
                if reason == "autostop"
                else self.t("notify_stopped").format(out=out.name)
            )
        else:
            self._fail(
                self.t("error_prefix").format(err=self.rec.state.last_error)
            )
        self.record_btn.setText(self.t("rec_start"))
        self.record_btn.setEnabled(True)
        self.replay_btn.setEnabled(True)
        self.studio_replay_btn.setEnabled(True)
        self._set_recording_ui(False)
        self._sync_studio_controls()
        self._refresh_tray()
        self._refresh_title()
        if quit_after:
            QApplication.quit()

    def _apply_replay_result(self) -> None:
        out = self._bg_result
        self.replay_btn.setEnabled(True)
        self.studio_replay_btn.setEnabled(True)
        if self._bg_error:
            self._fail(self.t("error_prefix").format(err=self._bg_error))
            self._bg_error = ""
        elif out is not None:
            self._clear_error()
            self.status_lbl.setText(self.t("replay_saved").format(out=out.name))
            self._refresh_recent()
            self._notify(self.t("replay_saved").format(out=out.name))
        else:
            self._fail(self.t("replay_empty"))

    def toggle_pause(self) -> None:
        if not self.rec.state.active or self._bg_thread is not None:
            return
        try:
            if self.rec.state.paused:
                self.rec.resume()
                self.pause_btn.setText(self.t("pause"))
                if self._autostop_remaining_ms > 0:
                    self._autostop_timer.start(self._autostop_remaining_ms)
                tmp = self.rec.state.tmp_path
                self.status_lbl.setText(
                    self.t("recording_to").format(name=tmp.name if tmp else "")
                )
            else:
                self.rec.pause()
                if self._autostop_timer.isActive():
                    self._autostop_remaining_ms = self._autostop_timer.remainingTime()
                    self._autostop_timer.stop()
                self.pause_btn.setText(self.t("resume"))
                self.status_lbl.setText(self.t("paused_status"))
            self._clear_error()
            self._refresh_state_dot()
            self._refresh_tray()
            self._refresh_title()
            self._sync_studio_controls()
        except Exception as e:
            self._fail(self.t("pause_error").format(err=e))

    def open_output_folder(self) -> None:
        path = self.cfg.output_dir
        try:
            path.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            self._fail(self.t("error_prefix").format(err=e))

    # --- Interrupted-recording recovery ---

    def _maybe_offer_recovery(self) -> None:
        if self.rec.state.active or os.environ.get("CASTMANE_NO_RECOVERY"):
            return
        from .recorder import find_stale_parts

        parts = find_stale_parts(self.cfg.output_dir)
        if not parts:
            return
        self._offer_recovery(parts)

    def _offer_recovery(self, parts: list[Path]) -> str:
        box = QMessageBox(self)
        box.setWindowTitle(self.t("recovery_title"))
        box.setText(self.t("recovery_text").format(n=len(parts)))
        box.setInformativeText("\n".join(p.name for p in parts[:8]))
        restore_btn = box.addButton(self.t("recovery_restore"), QMessageBox.AcceptRole)
        discard_btn = box.addButton(self.t("recovery_discard"), QMessageBox.DestructiveRole)
        box.addButton(self.t("recovery_later"), QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == restore_btn:
            return self._restore_stale_parts(parts)
        if clicked == discard_btn:
            return self._discard_stale_parts(parts)
        return "later"

    def _restore_stale_parts(self, parts: list[Path]) -> str:
        from .recorder import recover_part

        restored = [r.name for p in parts if (r := recover_part(p)) is not None]
        if restored:
            msg = self.t("recovery_restored").format(names=", ".join(restored))
            self.status_lbl.setText(msg)
            self._clear_error()
            self._notify(msg)
            return "restored"
        msg = self.t("recovery_failed").format(names=", ".join(p.name for p in parts))
        self._fail(msg)
        return "failed"

    def _discard_stale_parts(self, parts: list[Path]) -> str:
        count = 0
        for p in parts:
            try:
                Path(p).unlink(missing_ok=True)
                count += 1
            except OSError:
                pass
        msg = self.t("recovery_deleted").format(n=count)
        self.status_lbl.setText(msg)
        self._clear_error()
        return "deleted"

    # --- Setting Handlers ---

    def _on_audio_toggled(self, checked: bool) -> None:
        self.cfg.audio_enabled = checked
        try:
            self.rec.cfg.audio_enabled = checked
        except AttributeError:
            pass

    def _on_mic_gain_changed(self, pct: int) -> None:
        from .config import clamp_gain

        gain = clamp_gain(pct / 100.0)
        self.cfg.mic_gain = gain
        try:
            self.rec.cfg.mic_gain = gain
        except AttributeError:
            pass
        self._refresh_gain_labels()
        self.cfg.save()

    def _on_desk_gain_changed(self, pct: int) -> None:
        from .config import clamp_gain

        gain = clamp_gain(pct / 100.0)
        self.cfg.desktop_gain = gain
        try:
            self.rec.cfg.desktop_gain = gain
        except AttributeError:
            pass
        self._refresh_gain_labels()
        self.cfg.save()

    def _on_gain_changed(self, pct: int) -> None:
        self._on_mic_gain_changed(pct)

    def _on_audio_source_changed(self, text: str) -> None:
        value = text.strip() or "auto"
        self.cfg.audio_source = value
        try:
            self.rec.cfg.audio_source = value
        except AttributeError:
            pass

    def _on_audio_desktop_changed(self, text: str) -> None:
        value = text.strip() or "auto"
        self.cfg.audio_desktop_source = value
        try:
            self.rec.cfg.audio_desktop_source = value
        except AttributeError:
            pass

    def _on_audio_mode_changed(self, mode: str) -> None:
        if not mode:
            return
        from .audio import normalize_audio_mode

        self.cfg.audio_mode = normalize_audio_mode(mode)
        try:
            self.rec.cfg.audio_mode = self.cfg.audio_mode
        except AttributeError:
            pass
        self._refresh_audio_mode_hint()

    def _on_quality_changed(self, preset: str) -> None:
        if not preset:
            return
        try:
            self.cfg.apply_quality_preset(preset)
        except ValueError:
            return
        try:
            self.rec.cfg.apply_quality_preset(preset)
        except (AttributeError, ValueError):
            pass
        self.fps_spin.blockSignals(True)
        self.br_spin.blockSignals(True)
        self.fps_spin.setValue(self.cfg.fps)
        self.br_spin.setValue(self.cfg.video_bitrate_kbps)
        self.fps_spin.blockSignals(False)
        self.br_spin.blockSignals(False)
        self._refresh_custom_enabled()
        self._refresh_quality_hint()

    def _switch_to_custom(self) -> None:
        if self.quality_seg.current_data() == "custom":
            return
        self.cfg.apply_quality_preset("custom")
        try:
            self.rec.cfg.apply_quality_preset("custom")
        except (AttributeError, ValueError):
            pass
        self.quality_seg.set_current_data("custom")
        self._refresh_custom_enabled()
        self._refresh_quality_hint()

    def _refresh_custom_enabled(self) -> None:
        custom = self.quality_seg.current_data() == "custom"
        self.fps_spin.setEnabled(custom)
        self.br_spin.setEnabled(custom)

    def _on_fps_changed(self, value: int) -> None:
        from .config import clamp_fps

        self.cfg.fps = clamp_fps(value)
        try:
            self.rec.cfg.fps = self.cfg.fps
        except AttributeError:
            pass
        self._switch_to_custom()
        self.cfg.save()

    def _on_bitrate_changed(self, value: int) -> None:
        from .config import clamp_bitrate_kbps

        self.cfg.video_bitrate_kbps = clamp_bitrate_kbps(value)
        try:
            self.rec.cfg.video_bitrate_kbps = self.cfg.video_bitrate_kbps
        except AttributeError:
            pass
        self._switch_to_custom()
        self.cfg.save()

    def _on_format_changed(self, fmt: str) -> None:
        if not fmt:
            return
        from .config import normalize_format

        self.cfg.output_format = normalize_format(fmt)
        try:
            self.rec.cfg.output_format = self.cfg.output_format
        except AttributeError:
            pass
        self.cfg.save()

    def _refresh_recent(self) -> None:
        from datetime import datetime

        from .recorder import format_file_size, list_recent_recordings

        self.recent_list.clear()
        for path in list_recent_recordings(self.cfg.output_dir):
            try:
                st = path.stat()
            except OSError:
                continue
            when = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            size = format_file_size(st.st_size)
            item = QListWidgetItem(f"🎬  {path.name}   ·   {size}   ·   {when}")
            item.setData(Qt.UserRole, str(path))
            self.recent_list.addItem(item)
        if self.recent_list.count() == 0:
            empty = QListWidgetItem(self.t("recent_empty"))
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
            self.recent_list.addItem(empty)
        else:
            self.recent_list.setCurrentRow(0)

    def _open_selected_recording(self) -> None:
        item = self.recent_list.currentItem()
        target = item.data(Qt.UserRole) if item is not None else None
        if not target:
            for row in range(self.recent_list.count()):
                candidate = self.recent_list.item(row).data(Qt.UserRole)
                if candidate:
                    target = candidate
                    self.recent_list.setCurrentRow(row)
                    break
        if not target:
            self.status_lbl.setText(self.t("recent_none"))
            self._clear_error()
            return
        path = Path(target)
        if not path.is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self._fail(self.t("recent_open_failed").format(err=path.name))

    def _on_mode_changed(self, mode: str) -> None:
        if not mode:
            return
        self.cfg.capture_mode = mode
        try:
            self.rec.cfg.capture_mode = mode
        except AttributeError:
            pass
        self._refresh_mode_hint()

    def _on_region_changed(self) -> None:
        vals = {k: s.value() for k, s in self.region_spins.items()}
        for key, value in vals.items():
            setattr(self.cfg, f"region_{key}", value)
            try:
                setattr(self.rec.cfg, f"region_{key}", value)
            except AttributeError:
                pass

    def _on_cursor_toggled(self, checked: bool) -> None:
        self.cfg.show_cursor = checked
        try:
            self.rec.cfg.show_cursor = checked
        except AttributeError:
            pass
        self.cfg.save()

    def _on_countdown_changed(self, value: str) -> None:
        from .config import normalize_countdown

        self.cfg.countdown_s = normalize_countdown(value)
        try:
            self.rec.cfg.countdown_s = self.cfg.countdown_s
        except AttributeError:
            pass
        self.cfg.save()

    def _on_autostop_changed(self, value: int) -> None:
        from .config import normalize_auto_stop

        self.cfg.auto_stop_min = normalize_auto_stop(value)
        try:
            self.rec.cfg.auto_stop_min = self.cfg.auto_stop_min
        except AttributeError:
            pass
        self.cfg.save()

    def _on_replay_toggled(self, checked: bool) -> None:
        self.cfg.replay_enabled = checked
        try:
            self.rec.cfg.replay_enabled = checked
        except AttributeError:
            pass
        self.cfg.save()

    def _on_replay_seconds_changed(self, value: int) -> None:
        from .config import normalize_replay_seconds

        self.cfg.replay_seconds = normalize_replay_seconds(value)
        try:
            self.rec.cfg.replay_seconds = self.cfg.replay_seconds
        except AttributeError:
            pass
        self.cfg.save()

    def _on_shortcuts_edited(self) -> None:
        from .config import normalize_shortcut

        edits = getattr(self, "sc_edits", {})
        defaults = {
            "shortcut_record": "R",
            "shortcut_pause": "P",
            "shortcut_replay": "T",
            "shortcut_folder": "F",
        }
        for attr, edit in edits.items():
            value = normalize_shortcut(edit.text(), defaults[attr])
            setattr(self.cfg, attr, value)
            try:
                setattr(self.rec.cfg, attr, value)
            except AttributeError:
                pass
            edit.blockSignals(True)
            edit.setText(value)
            edit.blockSignals(False)
        self._refresh_shortcuts()
        self.cfg.save()

    def save_replay_clip(self) -> None:
        from . import replay as replay_mod

        if not self.cfg.replay_enabled:
            self._fail(self.t("replay_off"))
            return
        segs = replay_mod.list_segments(self.cfg.output_dir)
        picked = replay_mod.select_segments_for_save(segs, self.cfg.replay_seconds)
        if not picked:
            self._fail(self.t("replay_empty"))
            return
        if self._bg_thread is not None:
            return
        dest = self.cfg.next_output_path()
        # Concat can block for a while: run it off the UI thread.
        self.status_lbl.setText(self.t("finalizing"))
        self.replay_btn.setEnabled(False)
        self.studio_replay_btn.setEnabled(False)
        self._bg_kind = "replay"
        self._bg_result = None
        self._bg_error = ""
        self._bg_thread = threading.Thread(
            target=self._replay_worker, args=(picked, dest), daemon=True
        )
        self._bg_thread.start()

    def _on_output_dir_changed(self, text: str) -> None:
        value = text.strip() or str(Path.home() / "Videos" / "CastMane")
        self.cfg.output_dir = Path(value)
        try:
            self.rec.cfg.output_dir = self.cfg.output_dir
        except AttributeError:
            pass
        self._refresh_outcome()
        self._refresh_disk_label()
        self._refresh_recent()
        self.cfg.save()

    def _on_prefix_changed(self, text: str) -> None:
        self.cfg.filename_prefix = sanitize_prefix(text)
        try:
            self.rec.cfg.filename_prefix = self.cfg.filename_prefix
        except AttributeError:
            pass
        self.cfg.save()

    def browse_output_folder(self) -> None:
        picked = QFileDialog.getExistingDirectory(
            self, self.t("label_output_folder"), str(self.cfg.output_dir)
        )
        if picked:
            self.output_edit.setText(picked)

    def _refresh_disk_label(self) -> None:
        mb = self.cfg.output_dir_free_mb()
        if mb is None:
            self.disk_value.setText(self.t("disk_unknown"))
            self.disk_value.setProperty("error", False)
            _repolish(self.disk_value)
            return
        if mb < MIN_FREE_MB:
            self.disk_value.setText(self.t("disk_low").format(mb=mb))
            self.disk_value.setProperty("error", True)
        else:
            self.disk_value.setText(self.t("disk_free").format(mb=mb))
            self.disk_value.setProperty("error", False)
        _repolish(self.disk_value)

    def _auto_stop_timeout(self) -> None:
        if self.rec.state.active and not self.rec.state.paused:
            self._stop_recording(reason="autostop")

    def _disk_guard_tick(self) -> None:
        self._disk_check_counter += 1
        if self._disk_check_counter < 10:
            return
        self._disk_check_counter = 0
        free_mb = self.cfg.output_dir_free_mb()
        if free_mb is not None and free_mb < MIN_FREE_MB:
            self._stop_recording()
            self._fail(self.t("notify_disk_stopped").format(mb=MIN_FREE_MB))

    def _set_region_enabled(self, enabled: bool) -> None:
        for spin in self.region_spins.values():
            spin.setEnabled(enabled)

    # --- Errors & Status ---

    def _clear_error(self) -> None:
        self.status_lbl.setProperty("error", False)
        _repolish(self.status_lbl)

    def _fail(self, message: str) -> None:
        self.status_lbl.setText(message)
        self.status_lbl.setProperty("error", True)
        _repolish(self.status_lbl)

    # --- Ticking & Teardown ---

    def tick(self) -> None:
        if self._poll_background():
            return
        if self.rec.state.active:
            total = int(self.rec.elapsed)
            self.timer_lbl.setText(
                f"{total // 3600:02d}:{total // 60 % 60:02d}:{total % 60:02d}"
            )
            self._refresh_title()
            self._refresh_tray()
            self._disk_guard_tick()
        if self.rec.state.last_error and not self.rec.state.active:
            self.status_lbl.setText(
                self.t("error_prefix").format(err=self.rec.state.last_error)
            )
            self._fail(self.rec.state.last_error)
            self.record_btn.setText(self.t("rec_start"))
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText(self.t("pause"))
            self._set_inputs_enabled(True)
            self._set_recording_ui(False)
            self._end_screen_preview()
            self._sync_studio_controls()
            self.timer.stop()

    def closeEvent(self, event) -> None:
        if (
            self.rec.state.active
            and not self._quit_requested
            and self.tray is not None
        ):
            event.ignore()
            self.hide()
            self._notify(self.t("notify_minimized"))
            self._refresh_tray()
            return
        self._countdown_timer.stop()
        self._autostop_timer.stop()
        try:
            if self._cam is not None:
                self._cam.stop()
        except Exception:  # noqa: BLE001 - best-effort teardown
            pass
        try:
            if self.preview_player is not None:
                self.preview_player.stop()
        except Exception:  # noqa: BLE001 - best-effort teardown
            pass
        if self.rec.state.active and self._bg_thread is None:
            # Same freeze as the Stop button (graceful shutdown + remux), so
            # it goes through the worker as well. `timer` is kept running so
            # `tick()` can apply the result and quit us.
            event.ignore()
            self.timer.start()
            self._stop_recording(reason="quit", quit_after=True)
            return
        if self.rec.state.active:
            self.rec.stop()
        self.cfg.save()
        super().closeEvent(event)
