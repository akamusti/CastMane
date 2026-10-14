"""Qt main window: a plain desktop utility, not a landing page.

Layout, top to bottom:
  1. Header bar  - mark, name + subtitle, EN/TR switch, timer.
  2. Body        - left nav rail (Capture / Audio / Region + backend note),
                   right settings pane (stacked pages, label/control rows).
  3. Transport   - Record (primary) + Pause.
  4. Status bar  - state dot + message on the left, output folder on the right.

Deliberately un-fancy: flat surfaces, 1px hairlines, system font, and a
single red that only ever means "recording". No gradients, no glow, no
pill badges with wide letter-spacing — that is the look this rewrite
is getting away from.
"""
from __future__ import annotations

import os
import subprocess
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
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
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

from .backends import create_backend, session_is_wayland
from . import theme as theme_mod
from .config import (
    AppConfig,
    AUTO_STOP_MAX_MIN,
    BITRATE_MAX_KBPS,
    BITRATE_MIN_KBPS,
    COUNTDOWN_CHOICES,
    FPS_MAX,
    FPS_MIN,
    MIN_FREE_MB,
    sanitize_prefix,
)
from .i18n import SUPPORTED_LANGUAGES, get as _get, normalize
from .icons import paint_icon, tray_icon
from .theme import (
    FONT_MONO,
    FONT_UI,
    FOOTER_H,
    HEADER_H,
    NAV_H,
    RADIUS,
    RADIUS_LG,
    RADIUS_SM,
    SEGMENT_PAD,
    SEGMENT_TEXT_PAD,
    SIDEBAR_W,
    logo_path,
    mark_path,
)

def build_stylesheet(t: dict[str, str]) -> str:
    """Render the full QSS for one theme colour table."""
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
    background-color: {SURFACE};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: {SURFACE};
}}
QLabel {{
    background: transparent;
}}
/* --- Header --- */
QFrame#Header {{
    background-color: {SURFACE};
    border: none;
    border-bottom: 1px solid {HAIRLINE};
}}
QLabel#AppName {{
    color: {TEXT_MAIN};
    font-size: 14px;
    font-weight: 700;
}}
QLabel#AppSub {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QLabel#Timer {{
    color: {TEXT_SOFT};
}}
QLabel#Timer[recording="true"] {{
    color: {REC};
}}
/* --- Sidebar --- */
QFrame#Sidebar {{
    background-color: {CANVAS};
    border: none;
    border-right: 1px solid {HAIRLINE};
}}
QPushButton#Nav {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    padding: 0 8px 0 34px;
    color: {TEXT_MUTED};
    font-size: 13px;
    text-align: left;
}}
QPushButton#Nav:hover {{
    background-color: {BTN_HOVER};
    color: {TEXT_MAIN};
}}
QPushButton#Nav:checked {{
    background-color: {SURFACE};
    border-color: {HAIRLINE_STRONG};
    color: {TEXT_MAIN};
    font-weight: 700;
}}
QLabel#SideNote {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
/* --- Settings pane --- */
QLabel#RowLabel {{
    color: {TEXT_SOFT};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#Hint {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QLabel#Hint[error="true"] {{
    color: {REC};
}}
QFrame#Hairline {{
    background-color: {HAIRLINE};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
/* --- Segmented control: sunken well, selected segment is plain white --- */
QFrame#Segment {{
    background-color: {SURFACE_SUNKEN};
    border: 1px solid {HAIRLINE};
    border-radius: {RADIUS}px;
}}
QPushButton#Seg {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_SM}px;
    padding: 6px 4px;
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QPushButton#Seg:hover {{
    color: {TEXT_MAIN};
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
/* --- Buttons --- */
QPushButton#Record {{
    background-color: {INK};
    border: 1px solid {INK};
    border-radius: 11px;
    padding: 13px 16px;
    color: {PRIMARY_TEXT};
    font-size: 15px;
    font-weight: 700;
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
}}
QPushButton#Record[recording="true"]:hover {{
    background-color: {REC_HOVER};
    border-color: {REC_HOVER};
}}
QPushButton#Record[recording="true"]:pressed {{
    background-color: {REC_PRESSED};
    border-color: {REC_PRESSED};
}}
QPushButton#Pause {{
    background-color: {BTN_BG};
    border: 1px solid {BTN_BORDER};
    border-radius: {RADIUS}px;
    padding: 10px 12px;
    color: {TEXT_MAIN};
    font-size: 13px;
}}
QPushButton#Pause:hover {{
    background-color: {BTN_HOVER};
}}
QPushButton#Pause:pressed {{
    background-color: {BTN_PRESSED};
}}
QPushButton#Pause:disabled {{
    background-color: {BTN_DISABLED_BG};
    color: {BTN_DISABLED_TEXT};
    border-color: {HAIRLINE};
}}
/* --- Inputs --- */
QLineEdit, QSpinBox {{
    background-color: {SURFACE};
    border: 1px solid {BTN_BORDER};
    border-radius: {RADIUS_SM}px;
    padding: 6px 9px;
    color: {TEXT_MAIN};
    selection-background-color: {INK};
    selection-color: {PRIMARY_TEXT};
}}
QLineEdit:focus, QSpinBox:focus {{
    border-color: {TEXT_SOFT};
}}
QLineEdit:disabled, QSpinBox:disabled {{
    color: {BTN_DISABLED_TEXT};
    background-color: {BTN_DISABLED_BG};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0px;
    border: none;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {BTN_BORDER};
    border: none;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {SURFACE};
    border: 1px solid {HAIRLINE_STRONG};
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    border-color: {TEXT_SOFT};
}}
QSlider::handle:horizontal:disabled {{
    border-color: {BTN_DISABLED_TEXT};
    background: {BTN_DISABLED_BG};
}}
/* --- Transport + status bar --- */
QFrame#Transport {{
    background-color: {SURFACE};
    border: none;
    border-top: 1px solid {HAIRLINE};
}}
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
/* --- Studio cards --- */
QFrame#Card {{
    background-color: {SURFACE};
    border: 1px solid {HAIRLINE};
    border-radius: 10px;
}}
QLabel#SectionTitle {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
}}
/* --- State pill (header) --- */
QLabel#Pill {{
    border: 1px solid {HAIRLINE_STRONG};
    border-radius: 9px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
    color: {TEXT_MUTED};
    background-color: {SURFACE_SUNKEN};
}}
QLabel#Pill[state="recording"] {{
    color: {REC};
    border-color: {REC_BORDER};
    background-color: {REC_TINT};
}}
QLabel#Pill[state="paused"] {{
    color: {PAUSED};
    border-color: {HAIRLINE_STRONG};
    background-color: {PAUSED_TINT};
}}
/* --- Mixer channel strips --- */
QFrame#Strip {{
    background-color: {SURFACE_SUNKEN};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
}}
QLabel#StripName {{
    color: {TEXT_MAIN};
    font-size: 12px;
    font-weight: 700;
}}
QLabel#StripValue {{
    color: {TEXT_SOFT};
    font-size: 11px;
}}
QSlider::groove:vertical {{
    width: 4px;
    background: {BTN_BORDER};
    border: none;
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    background: {SURFACE};
    border: 1px solid {HAIRLINE_STRONG};
    width: 14px;
    height: 14px;
    margin: 0 -6px;
    border-radius: 7px;
}}
QToolTip {{
    background-color: {SURFACE};
    color: {TEXT_MAIN};
    border: 1px solid {HAIRLINE_STRONG};
    padding: 4px 7px;
}}
"""


def _active_theme(widget: QWidget) -> dict[str, str]:
    """Colour table of the window this widget lives in.

    Paint code goes through here so a runtime theme switch repaints
    every custom-drawn control without restarting the app.
    """
    win = widget.window()
    t = getattr(win, "theme", None)
    if isinstance(t, dict) and "CANVAS" in t:
        return t
    return theme_mod.get_theme(theme_mod.DEFAULT_THEME)

LANGUAGE_LABELS = {"en": "EN", "tr": "TR"}


def _repolish(widget: QWidget) -> None:
    """Re-evaluate the stylesheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class MarkTile(QWidget):
    """Header logo: bare ink mark on light themes, white tile on dark ones.

    The bundled mark is dark ink on transparency, so it vanishes on
    dark headers. The tile keeps the original asset untouched and
    adapts via the live theme (no per-theme artwork to maintain).
    """

    TILE = 34
    GLYPH = 24

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.TILE, self.TILE)
        mark_file = mark_path()
        self._pix = QPixmap(mark_file) if mark_file else QPixmap()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        if theme_mod.surface_is_dark(_active_theme(self)):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FFFFFF"))
            p.drawRoundedRect(self.rect(), 8, 8)
        if not self._pix.isNull():
            side = float(self.GLYPH)
            x = (self.width() - side) / 2.0
            y = (self.height() - side) / 2.0
            p.drawPixmap(int(x), int(y), int(side), int(side), self._pix)


class StatusDot(QWidget):
    """A 10px state dot. Colour carries the state; text stays plain."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._color = QColor(theme_mod.READY)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(self.rect())


class Switch(QAbstractButton):
    """Plain sliding toggle: grey when off, ink when on."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._pos = 1.0 if self.isChecked() else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
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

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        # Constructor runs before signals exist; keep paint in sync.
        self._pos = 1.0 if checked else 0.0
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(44, 24)

    def paintEvent(self, _event) -> None:  # noqa: N802
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
        # Hairline edge so a light knob still reads on a light track.
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(border, 1.0))
        p.drawEllipse(knob_center, knob / 2 - 0.5, knob / 2 - 0.5)


class SegmentedControl(QFrame):
    """Mutually exclusive options in a sunken well.

    The checked segment is plain white with a hairline edge — the same
    idiom GNOME/macOS settings use — instead of a coloured fill.
    """

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
    """One sidebar row: vector icon on the left, label after it."""

    ICON_W = 34  # matches the QSS padding-left

    def __init__(self, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Nav")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(NAV_H)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._icon = icon_name

    def _ink(self) -> QColor:
        t = _active_theme(self)
        if not self.isEnabled():
            return QColor(t["TEXT_FAINT"])
        if self.isChecked():
            return QColor(t["TEXT_MAIN"])
        return QColor(t["TEXT_MUTED"]) if not self.underMouse() else QColor(t["TEXT_MAIN"])

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        side = 16.0
        x = (self.ICON_W - side) / 2.0
        y = (self.height() - side) / 2.0
        paint_icon(p, self._icon, QRectF(x, y, side, side), self._ink())

    def enterEvent(self, event) -> None:  # noqa: N802
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        super().leaveEvent(event)
        self.update()


class RecordButton(QPushButton):
    """Primary transport button: red dot when idle, square when recording."""

    GLYPH_GAP = 10.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Record")
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("recording", False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(42)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = _active_theme(self)
        metrics = QFontMetrics(self.font())
        text_w = metrics.horizontalAdvance(self.text())
        gx = self.width() / 2.0 - text_w / 2.0 - self.GLYPH_GAP - 7.0
        gy = self.height() / 2.0 - 5.5
        if self.property("recording"):
            path = QPainterPath()
            path.addRoundedRect(QRectF(gx, gy, 11, 11), 2, 2)
            p.fillPath(path, QColor(t["PRIMARY_TEXT"]))
        else:
            paint_icon(p, "dot", QRectF(gx, gy, 11, 11), QColor(t["REC"]))

    def set_recording(self, recording: bool) -> None:
        self.setProperty("recording", recording)
        _repolish(self)


class MainWindow(QMainWindow):
    LABEL_COL = 148
    OUT_PATH_PX = 240

    def __init__(self, cfg: AppConfig | None = None) -> None:
        super().__init__()
        self.cfg = cfg or AppConfig()
        self.cfg.language = normalize(self.cfg.language)
        self.cfg.theme = theme_mod.normalize_theme(self.cfg.theme)
        self.theme = theme_mod.get_theme(self.cfg.theme)
        self.rec = create_backend(self.cfg)
        self._card_labels: list[QLabel] = []
        self.setWindowTitle("CastMane")
        self.resize(920, 660)
        self.setMinimumSize(760, 560)
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

        # Countdown (3-2-1) + auto-stop state. Countdown ticks once per
        # second on this timer; auto-stop is a one-shot wall-clock timer.
        self._countdown_left = 0
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._countdown_tick)
        self._autostop_timer = QTimer(self)
        self._autostop_timer.setSingleShot(True)
        self._autostop_timer.timeout.connect(self._auto_stop_timeout)
        # Remaining auto-stop time (ms), so pause freezes the deadline
        # instead of letting it fire (and get skipped) mid-pause.
        self._autostop_remaining_ms = 0
        # Throttle the live disk-space guard: check every ~5s, not every tick.
        self._disk_check_counter = 0
        self._quit_requested = False
        self._setup_shortcuts()
        self._setup_tray()

        self._is_wayland = session_is_wayland()
        self._retranslate()
        self._refresh_custom_enabled()
        self._refresh_idle_status()
        # Offer to restore leftover `.part` files once the window is up.
        QTimer.singleShot(0, self._maybe_offer_recovery)

    # --- Construction ---

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Header")
        bar.setFixedHeight(HEADER_H)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(10)

        mark = MarkTile()
        self.header_mark = mark
        row.addWidget(mark)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        name = QLabel("CastMane")
        name.setObjectName("AppName")
        self.subtitle_lbl = QLabel()
        self.subtitle_lbl.setObjectName("AppSub")
        text.addWidget(name)
        text.addWidget(self.subtitle_lbl)
        row.addLayout(text, 1)

        self.state_pill = QLabel("READY")
        self.state_pill.setObjectName("Pill")
        self.state_pill.setProperty("state", "ready")
        self.state_pill.setAlignment(Qt.AlignCenter)
        row.addWidget(self.state_pill)

        self.timer_lbl = QLabel("00:00:00")
        self.timer_lbl.setObjectName("Timer")
        self.timer_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.timer_lbl.setProperty("recording", False)
        font = QFont()
        font.setFamilies(
            [
                "JetBrains Mono",
                "DejaVu Sans Mono",
                "Noto Sans Mono",
                "Liberation Mono",
                "monospace",
            ]
        )
        font.setStyleHint(QFont.Monospace)
        font.setPixelSize(20)
        font.setWeight(QFont.DemiBold)
        self.timer_lbl.setFont(font)
        self.timer_lbl.setFixedWidth(
            QFontMetrics(font).horizontalAdvance("00:00:00") + 4
        )
        row.addWidget(self.timer_lbl)
        return bar

    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(SIDEBAR_W)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(2)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_buttons: list[NavButton] = []
        for code, icon in (
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
        self.backend_lbl = QLabel()
        self.backend_lbl.setObjectName("SideNote")
        self.backend_lbl.setWordWrap(True)
        layout.addWidget(self.backend_lbl)
        return side

    def _build_pane(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(22, 20, 26, 20)
        layout.setSpacing(0)

        self.pages = QStackedWidget()
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
        """One studio card: titled SURFACE panel holding settings rows."""
        frame = QFrame()
        frame.setObjectName("Card")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(4)
        title = QLabel()
        title.setObjectName("SectionTitle")
        title.setProperty("i18n", i18n_key)
        outer.addWidget(title)
        inner = QVBoxLayout()
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)
        outer.addLayout(inner)
        self._card_labels.append(title)
        return frame, inner

    @staticmethod
    def _strip(name: QLabel, slider: QSlider, value: QLabel) -> QFrame:
        """One mixer channel strip: name, vertical fader, % readout."""
        frame = QFrame()
        frame.setObjectName("Strip")
        box = QVBoxLayout(frame)
        box.setContentsMargins(10, 10, 10, 10)
        box.setSpacing(6)
        box.addWidget(name)
        fader_row = QHBoxLayout()
        fader_row.setContentsMargins(0, 0, 0, 0)
        fader_row.addStretch(1)
        fader_row.addWidget(slider)
        fader_row.addStretch(1)
        box.addLayout(fader_row)
        box.addWidget(value)
        return frame

    def _row(
        self,
        label: QLabel,
        control: QWidget,
        hint: QLabel | None = None,
    ) -> QWidget:
        """One settings row: fixed label column, control column, hint below."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
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
            spacer.setFixedWidth(self.LABEL_COL + 12)
            indent_layout.addWidget(spacer)
            indent_layout.addWidget(hint, 1)
            layout.addWidget(indent)
        return box

    @staticmethod
    def _hairline() -> QFrame:
        line = QFrame()
        line.setObjectName("Hairline")
        return line

    def _build_capture_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        video_card, video = self._card("card_video")

        self.lbl_source = QLabel()
        self.lbl_source.setObjectName("RowLabel")
        self.mode_seg = SegmentedControl(
            [("", "fullscreen"), ("", "window"), ("", "ask")]
        )
        self.mode_seg.set_current_data(self.cfg.capture_mode)
        self.mode_seg.changed.connect(self._on_mode_changed)
        self.hint_mode = QLabel()
        self.hint_mode.setObjectName("Hint")
        video.addWidget(self._row(self.lbl_source, self.mode_seg, self.hint_mode))

        self.lbl_quality = QLabel()
        self.lbl_quality.setObjectName("RowLabel")
        self.quality_seg = SegmentedControl(
            [("", "draft"), ("", "balanced"), ("", "high"), ("", "custom")]
        )
        self.quality_seg.set_current_data(self.cfg.quality_preset)
        self.quality_seg.changed.connect(self._on_quality_changed)
        self.hint_quality = QLabel()
        self.hint_quality.setObjectName("Hint")
        video.addWidget(
            self._row(self.lbl_quality, self.quality_seg, self.hint_quality)
        )

        self.lbl_fps = QLabel()
        self.lbl_fps.setObjectName("RowLabel")
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(FPS_MIN, FPS_MAX)
        self.fps_spin.setFixedWidth(110)
        self.fps_spin.setValue(self.cfg.fps)
        self.fps_spin.valueChanged.connect(self._on_fps_changed)
        video.addWidget(self._row(self.lbl_fps, self.fps_spin))

        self.lbl_bitrate = QLabel()
        self.lbl_bitrate.setObjectName("RowLabel")
        self.br_spin = QSpinBox()
        self.br_spin.setRange(BITRATE_MIN_KBPS, BITRATE_MAX_KBPS)
        self.br_spin.setSingleStep(1000)
        self.br_spin.setSuffix(" kbps")
        self.br_spin.setFixedWidth(170)
        self.br_spin.setValue(self.cfg.video_bitrate_kbps)
        self.br_spin.valueChanged.connect(self._on_bitrate_changed)
        video.addWidget(self._row(self.lbl_bitrate, self.br_spin))
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
        self.countdown_seg = SegmentedControl(
            [(self.t("countdown_off") if v == 0 else f"{v}s", str(v)) for v in COUNTDOWN_CHOICES]
        )
        self.countdown_seg.set_current_data(str(self.cfg.countdown_s))
        self.countdown_seg.changed.connect(self._on_countdown_changed)
        self.hint_countdown = QLabel()
        self.hint_countdown.setObjectName("Hint")
        auto.addWidget(
            self._row(self.lbl_countdown, self.countdown_seg, self.hint_countdown)
        )

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
        auto.addWidget(
            self._row(self.lbl_autostop, autostop_wrap, self.hint_autostop)
        )

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
        auto.addWidget(
            self._row(self.lbl_replay, replay_wrap, self.hint_replay)
        )
        layout.addWidget(auto_card)
        layout.addStretch(1)
        return page

    def _build_audio_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        mixer_card, mixer = self._card("card_mixer")

        self.mic_gain_slider = QSlider(Qt.Vertical)
        self.mic_gain_slider.setRange(0, 500)
        self.mic_gain_slider.setSingleStep(10)
        self.mic_gain_slider.setPageStep(50)
        self.mic_gain_slider.setMinimumHeight(130)
        self.mic_gain_slider.setValue(round(self.cfg.mic_gain * 100))
        self.mic_gain_slider.valueChanged.connect(self._on_mic_gain_changed)
        self.mic_gain_value = QLabel()
        self.mic_gain_value.setObjectName("StripValue")
        self.mic_gain_value.setAlignment(Qt.AlignCenter)

        self.desk_gain_slider = QSlider(Qt.Vertical)
        self.desk_gain_slider.setRange(0, 500)
        self.desk_gain_slider.setSingleStep(10)
        self.desk_gain_slider.setPageStep(50)
        self.desk_gain_slider.setMinimumHeight(130)
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
        strips.setContentsMargins(0, 4, 0, 4)
        strips.setSpacing(12)
        strips.addWidget(self._strip(self.lbl_mic_gain, self.mic_gain_slider,
                                     self.mic_gain_value), 1)
        strips.addWidget(self._strip(self.lbl_desk_gain, self.desk_gain_slider,
                                     self.desk_gain_value), 1)
        mixer.addLayout(strips)
        self.hint_mixer = QLabel()
        self.hint_mixer.setObjectName("Hint")
        self.hint_mixer.setWordWrap(True)
        mixer.addWidget(self.hint_mixer)
        layout.addWidget(mixer_card)
        # Compat alias: old code/tests touched `gain_slider`.
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
        src.addWidget(self._row(self.audio_lbl, audio_wrap))

        self.lbl_audio_mode = QLabel()
        self.lbl_audio_mode.setObjectName("RowLabel")
        self.audio_mode_seg = SegmentedControl(
            [("", "mic"), ("", "desktop"), ("", "both")]
        )
        self.audio_mode_seg.set_current_data(self.cfg.audio_mode)
        self.audio_mode_seg.changed.connect(self._on_audio_mode_changed)
        self.hint_audio_mode = QLabel()
        self.hint_audio_mode.setObjectName("Hint")
        src.addWidget(
            self._row(self.lbl_audio_mode, self.audio_mode_seg, self.hint_audio_mode)
        )

        self.lbl_source_name = QLabel()
        self.lbl_source_name.setObjectName("RowLabel")
        self.audio_source_edit = QLineEdit(self.cfg.audio_source)
        self.audio_source_edit.setPlaceholderText("auto")
        self.audio_source_edit.textChanged.connect(self._on_audio_source_changed)
        self.hint_audio = QLabel()
        self.hint_audio.setObjectName("Hint")
        src.addWidget(
            self._row(self.lbl_source_name, self.audio_source_edit, self.hint_audio)
        )

        self.lbl_desktop_source_name = QLabel()
        self.lbl_desktop_source_name.setObjectName("RowLabel")
        self.audio_desktop_edit = QLineEdit(self.cfg.audio_desktop_source)
        self.audio_desktop_edit.setPlaceholderText("auto")
        self.audio_desktop_edit.textChanged.connect(self._on_audio_desktop_changed)
        src.addWidget(
            self._row(self.lbl_desktop_source_name, self.audio_desktop_edit)
        )
        layout.addWidget(src_card)
        layout.addStretch(1)
        return page

    def _build_region_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        card, body = self._card("label_region")

        self.lbl_region = QLabel()
        self.lbl_region.setObjectName("RowLabel")
        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.region_spins: dict[str, QSpinBox] = {}
        for i, (key, value) in enumerate(
            (
                ("x", self.cfg.region_x),
                ("y", self.cfg.region_y),
                ("w", self.cfg.region_w),
                ("h", self.cfg.region_h),
            )
        ):
            spin = QSpinBox()
            spin.setPrefix(f"{key.upper()}  ")
            spin.setRange(0, 10000)
            spin.setValue(value)
            spin.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            spin.valueChanged.connect(self._on_region_changed)
            spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.region_spins[key] = spin
            grid.addWidget(spin, i // 2, i % 2)
        self.hint_region = QLabel()
        self.hint_region.setObjectName("Hint")
        body.addWidget(self._row(self.lbl_region, grid_wrap, self.hint_region))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_output_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
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
        self.browse_btn.clicked.connect(self.browse_output_folder)
        folder_row.addWidget(self.browse_btn)
        self.hint_output = QLabel()
        self.hint_output.setObjectName("Hint")
        store.addWidget(
            self._row(self.lbl_output_folder, folder_wrap, self.hint_output)
        )

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
        store.addWidget(
            self._row(self.lbl_prefix, self.prefix_edit, self.hint_prefix)
        )

        self.lbl_format = QLabel()
        self.lbl_format.setObjectName("RowLabel")
        self.format_seg = SegmentedControl([("MP4", "mp4"), ("MKV", "mkv")])
        self.format_seg.set_current_data(self.cfg.output_format)
        self.format_seg.changed.connect(self._on_format_changed)
        self.hint_format = QLabel()
        self.hint_format.setObjectName("Hint")
        store.addWidget(
            self._row(self.lbl_format, self.format_seg, self.hint_format)
        )
        layout.addWidget(store_card)

        self.lbl_recent = QLabel()
        self.lbl_recent.setObjectName("SectionTitle")
        recent_wrap = QWidget()
        recent_col = QVBoxLayout(recent_wrap)
        recent_col.setContentsMargins(0, 0, 0, 0)
        recent_col.setSpacing(8)
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(132)
        self.recent_list.itemDoubleClicked.connect(
            lambda _item: self._open_selected_recording()
        )
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
        recent_card = QFrame()
        recent_card.setObjectName("Card")
        rc_outer = QVBoxLayout(recent_card)
        rc_outer.setContentsMargins(16, 12, 16, 12)
        rc_outer.setSpacing(4)
        rc_outer.addWidget(self.lbl_recent)
        rc_outer.addWidget(recent_wrap)
        layout.addWidget(recent_card)
        layout.addStretch(1)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        gen_card, gen = self._card("card_general")

        self.lbl_language = QLabel()
        self.lbl_language.setObjectName("RowLabel")
        self.lang_seg = SegmentedControl(
            [(LANGUAGE_LABELS[code], code) for code in SUPPORTED_LANGUAGES]
        )
        self.lang_seg.set_current_data(self.cfg.language)
        self.lang_seg.changed.connect(self._on_language_changed)
        self.hint_language = QLabel()
        self.hint_language.setObjectName("Hint")
        gen.addWidget(
            self._row(self.lbl_language, self.lang_seg, self.hint_language)
        )

        self.lbl_theme = QLabel()
        self.lbl_theme.setObjectName("RowLabel")
        self.theme_seg = SegmentedControl(
            [("", name) for name in theme_mod.SUPPORTED_THEMES]
        )
        self.theme_seg.set_current_data(self.cfg.theme)
        self.theme_seg.changed.connect(self._on_theme_changed)
        self.hint_theme = QLabel()
        self.hint_theme.setObjectName("Hint")
        gen.addWidget(self._row(self.lbl_theme, self.theme_seg, self.hint_theme))
        layout.addWidget(gen_card)

        sc_card, sc_body = self._card("card_shortcuts")
        self.lbl_shortcuts = QLabel()
        self.lbl_shortcuts.setObjectName("RowLabel")
        sc_wrap = QWidget()
        sc_grid = QGridLayout(sc_wrap)
        sc_grid.setContentsMargins(0, 0, 0, 0)
        sc_grid.setHorizontalSpacing(10)
        sc_grid.setVerticalSpacing(8)
        self.sc_edits: dict[str, QLineEdit] = {}
        for i, (key, attr) in enumerate(
            (
                ("shortcut_record", "shortcut_record"),
                ("shortcut_pause", "shortcut_pause"),
                ("shortcut_replay", "shortcut_replay"),
                ("shortcut_folder", "shortcut_folder"),
            )
        ):
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
        self._sc_tags = [sc_grid.itemAtPosition(r, c).widget()
                         for r in range(2) for c in (0, 2)]
        self.hint_shortcuts = QLabel()
        self.hint_shortcuts.setObjectName("Hint")
        sc_body.addWidget(
            self._row(self.lbl_shortcuts, sc_wrap, self.hint_shortcuts)
        )
        layout.addWidget(sc_card)
        layout.addStretch(1)
        return page

    def _build_transport(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Transport")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)
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
        bar.setFixedHeight(FOOTER_H)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 10, 0)
        row.setSpacing(8)
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
        self.folder_btn.setFixedSize(26, 26)
        self.folder_btn.clicked.connect(self.open_output_folder)
        row.addWidget(self.folder_btn)
        return bar

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
            ("tab_capture", "tab_audio", "tab_region", "tab_output", "tab_settings"),
        ):
            btn.setText(_get(key, lang))
            btn.update()

        self.lbl_source.setText(_get("label_source", lang))
        self.mode_seg.set_labels(
            [
                _get("mode_fullscreen", lang),
                _get("mode_window", lang),
                _get("mode_ask", lang),
            ]
        )
        self._refresh_mode_hint()
        self.lbl_quality.setText(_get("label_quality", lang))
        self.quality_seg.set_labels(
            [
                _get("quality_draft", lang),
                _get("quality_balanced", lang),
                _get("quality_high", lang),
                _get("quality_custom", lang),
            ]
        )
        self._refresh_quality_hint()
        self.lbl_fps.setText(_get("label_fps", lang))
        self.lbl_bitrate.setText(_get("label_bitrate", lang))

        self.audio_lbl.setText(_get("audio_check", lang))
        self.lbl_audio_mode.setText(_get("audio_mode", lang))
        self.audio_mode_seg.set_labels(
            [
                _get("audio_mode_mic", lang),
                _get("audio_mode_desktop", lang),
                _get("audio_mode_both", lang),
            ]
        )
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

        self.lbl_cursor.setText(_get("label_cursor", lang))
        self.hint_cursor.setText(_get("cursor_hint", lang))
        self.lbl_countdown.setText(_get("label_countdown", lang))
        self.countdown_seg.set_labels(
            [_get("countdown_off", lang) if v == 0 else f"{v}s" for v in COUNTDOWN_CHOICES]
        )
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
        self.theme_seg.set_labels(
            [_get(f"theme_{name}", lang) for name in theme_mod.SUPPORTED_THEMES]
        )
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
        from pathlib import Path

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
        if self.rec.state.paused:
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
            self.t("gain_value").format(pct=self.mic_gain_slider.value()))
        self.desk_gain_value.setText(
            self.t("gain_value").format(pct=self.desk_gain_slider.value()))

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
        """Switch the whole window to ``name`` and remember the choice."""
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
        return ("capture", "audio", "region", "output", "settings").index(code)

    def _setup_shortcuts(self) -> None:
        """Window shortcuts: configurable (Settings page) + Space alias."""
        self._shortcuts: list[QShortcut] = []
        self._refresh_shortcuts()

    def _refresh_shortcuts(self) -> None:
        for sc in getattr(self, "_shortcuts", []):
            try:
                sc.setEnabled(False)
                sc.deleteLater()
            except Exception:  # noqa: BLE001, S110 - best effort teardown
                pass
        self._shortcuts = []

        def _add(seq: str, slot) -> None:
            try:
                sc = QShortcut(QKeySequence(seq), self)
            except Exception:  # noqa: BLE001, S110 - bad shortcut string
                return
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(slot)
            self._shortcuts.append(sc)

        _add(self.cfg.shortcut_record, self.toggle)
        _add("Space", self.toggle)
        _add(self.cfg.shortcut_pause, self.toggle_pause)
        _add(self.cfg.shortcut_folder, self.open_output_folder)
        _add(self.cfg.shortcut_replay, self.save_replay_clip)

    # --- System tray + notifications ---

    def _setup_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                return
        except Exception:  # noqa: BLE001
            return
        # Top-bar (tray) icon is symbolic white like Discord's so it
        # blends with the other indicators. The colourful logo.png stays
        # as the window/desktop icon and is intentionally not used here.
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
        except Exception:  # noqa: BLE001
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

    # --- Recording control ---

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
        if enabled:
            self._refresh_custom_enabled()
        else:
            self.fps_spin.setEnabled(False)
            self.br_spin.setEnabled(False)
        self._set_region_enabled(enabled)

    def toggle(self) -> None:
        # A second press while counting down cancels the countdown.
        if self._countdown_timer.isActive():
            self._countdown_timer.stop()
            self._countdown_left = 0
            self.timer_lbl.setText("00:00:00")
            self._refresh_idle_status()
            self._set_inputs_enabled(True)
            return
        if not self.rec.state.active:
            if self.cfg.countdown_s > 0:
                self._countdown_left = self.cfg.countdown_s
                self._set_inputs_enabled(False)
                self.status_lbl.setText(
                    self.t("countdown_status").format(n=self._countdown_left)
                )
                self.timer_lbl.setText(self._fmt_elapsed(self._countdown_left))
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
        except Exception as e:  # noqa: BLE001
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
        self.timer.start()
        if self.cfg.auto_stop_min > 0:
            self._autostop_remaining_ms = self.cfg.auto_stop_min * 60 * 1000
            self._autostop_timer.start(self._autostop_remaining_ms)
        else:
            self._autostop_remaining_ms = 0
        self._notify(self.t("notify_started"))
        self._refresh_tray()
        self._refresh_title()

    def _stop_recording(self, reason: str = "") -> None:
        self._countdown_timer.stop()
        self._autostop_timer.stop()
        self._autostop_remaining_ms = 0
        self._countdown_left = 0
        out = self.rec.stop()
        self.timer.stop()
        self._set_inputs_enabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText(self.t("pause"))
        if out:
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
        self._set_recording_ui(False)
        self._refresh_tray()
        self._refresh_title()

    def toggle_pause(self) -> None:
        if not self.rec.state.active:
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
                    # Freeze the deadline: resume() restarts it with the rest.
                    self._autostop_remaining_ms = self._autostop_timer.remainingTime()
                    self._autostop_timer.stop()
                self.pause_btn.setText(self.t("resume"))
                self.status_lbl.setText(self.t("paused_status"))
            self._clear_error()
            self._refresh_state_dot()
            self._refresh_tray()
            self._refresh_title()
        except Exception as e:  # noqa: BLE001
            self._fail(self.t("pause_error").format(err=e))

    def open_output_folder(self) -> None:
        path = self.cfg.output_dir
        try:
            path.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:  # noqa: BLE001
            self._fail(self.t("error_prefix").format(err=e))

    # --- Interrupted-recording recovery ---

    def _maybe_offer_recovery(self) -> None:
        """Ask about leftover `.part` files from a crash, if any.

        Skipped when a recording is already active and when
        `CASTMANE_NO_RECOVERY` is set (tests / headless runs).
        """
        if self.rec.state.active or os.environ.get("CASTMANE_NO_RECOVERY"):
            return
        from .recorder import find_stale_parts

        parts = find_stale_parts(self.cfg.output_dir)
        if not parts:
            return
        self._offer_recovery(parts)

    def _offer_recovery(self, parts: list[Path]) -> str:
        """Show the Restore / Delete / Later dialog. Returns the action."""
        box = QMessageBox(self)
        box.setWindowTitle(self.t("recovery_title"))
        box.setText(self.t("recovery_text").format(n=len(parts)))
        box.setInformativeText("\n".join(p.name for p in parts[:8]))
        restore_btn = box.addButton(
            self.t("recovery_restore"), QMessageBox.AcceptRole
        )
        discard_btn = box.addButton(
            self.t("recovery_discard"), QMessageBox.DestructiveRole
        )
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
        msg = self.t("recovery_failed").format(
            names=", ".join(p.name for p in parts)
        )
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

    # --- Setting handlers ---

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
        # Named presets own fps/bitrate: show their values without
        # tripping the custom switch.
        self.fps_spin.blockSignals(True)
        self.br_spin.blockSignals(True)
        self.fps_spin.setValue(self.cfg.fps)
        self.br_spin.setValue(self.cfg.video_bitrate_kbps)
        self.fps_spin.blockSignals(False)
        self.br_spin.blockSignals(False)
        self._refresh_custom_enabled()
        self._refresh_quality_hint()

    def _switch_to_custom(self) -> None:
        """Editing fps/bitrate by hand means the Custom preset."""
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
            item = QListWidgetItem(f"{path.name}  ·  {size}  ·  {when}")
            item.setData(Qt.UserRole, str(path))
            self.recent_list.addItem(item)
        if self.recent_list.count() == 0:
            empty = QListWidgetItem(self.t("recent_empty"))
            empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
            self.recent_list.addItem(empty)
        else:
            # A row is always selected, so Aç/Open just works.
            self.recent_list.setCurrentRow(0)

    def _open_selected_recording(self) -> None:
        item = self.recent_list.currentItem()
        target = item.data(Qt.UserRole) if item is not None else None
        if not target:
            # No selection (or the empty placeholder): fall back to the
            # newest recording, if the list holds one.
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
        # QDesktopServices reports failure (unlike fire-and-forget
        # xdg-open, whose errors died silently with the child).
        if not path.is_file() or not QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(path))
        ):
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
        defaults = {"shortcut_record": "R", "shortcut_pause": "P",
                    "shortcut_replay": "T", "shortcut_folder": "F"}
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
        dest = self.cfg.next_output_path()
        if replay_mod.save_replay(picked, dest):
            self._clear_error()
            self.status_lbl.setText(self.t("replay_saved").format(out=dest.name))
            self._refresh_recent()
            self._notify(self.t("replay_saved").format(out=dest.name))
        else:
            self._fail(self.t("replay_empty"))

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
        """Live disk guard: stop cleanly before the disk fills mid-take."""
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

    # --- Errors ---

    def _clear_error(self) -> None:
        self.status_lbl.setProperty("error", False)
        _repolish(self.status_lbl)

    def _fail(self, message: str) -> None:
        self.status_lbl.setText(message)
        self.status_lbl.setProperty("error", True)
        _repolish(self.status_lbl)

    # --- Tick ---

    def tick(self) -> None:
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
            self.timer.stop()

    def closeEvent(self, event) -> None:  # noqa: N802
        # Recording + tray available: minimize to tray instead of killing
        # the take. Tray menu Quit still exits for real.
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
        if self.rec.state.active:
            self.rec.stop()
        self.cfg.save()
        super().closeEvent(event)
