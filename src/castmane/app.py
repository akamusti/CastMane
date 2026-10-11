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

import subprocess

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .backends import create_backend, session_is_wayland
from .config import AppConfig
from .i18n import SUPPORTED_LANGUAGES, get as _get, normalize
from .icons import paint_icon
from .theme import (
    BTN_BG,
    BTN_BORDER,
    BTN_DISABLED_BG,
    BTN_DISABLED_TEXT,
    BTN_HOVER,
    BTN_PRESSED,
    CANVAS,
    FONT_MONO,
    FONT_UI,
    FOOTER_H,
    HAIRLINE,
    HAIRLINE_STRONG,
    HEADER_H,
    INK,
    INK_HOVER,
    INK_PRESSED,
    NAV_H,
    PAUSED,
    RADIUS,
    RADIUS_LG,
    RADIUS_SM,
    READY,
    REC,
    REC_BORDER,
    REC_HOVER,
    REC_PRESSED,
    REC_TINT,
    SEGMENT_PAD,
    SEGMENT_TEXT_PAD,
    SIDEBAR_W,
    SURFACE,
    SURFACE_SUNKEN,
    TEXT_FAINT,
    TEXT_MAIN,
    TEXT_MUTED,
    TEXT_SOFT,
    logo_path,
    mark_path,
)

STYLESHEET = f"""
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
    border-radius: {RADIUS}px;
    padding: 10px 16px;
    color: #FFFFFF;
    font-size: 14px;
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
    selection-color: #FFFFFF;
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
QToolTip {{
    background-color: {SURFACE};
    color: {TEXT_MAIN};
    border: 1px solid {HAIRLINE_STRONG};
    padding: 4px 7px;
}}
"""

LANGUAGE_LABELS = {"en": "EN", "tr": "TR"}


def _repolish(widget: QWidget) -> None:
    """Re-evaluate the stylesheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class StatusDot(QWidget):
    """A 10px state dot. Colour carries the state; text stays plain."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._color = QColor(READY)

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

        off = QColor(SURFACE_SUNKEN)
        on = QColor(INK)
        mixed = QColor(
            round(off.red() + (on.red() - off.red()) * self._pos),
            round(off.green() + (on.green() - off.green()) * self._pos),
            round(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(mixed)
        p.drawRoundedRect(track.adjusted(1.0, 1.0, -1.0, -1.0), 11, 11)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(HAIRLINE_STRONG), 1.0))
        p.drawRoundedRect(track, 11.5, 11.5)

        knob = h - 8.0
        travel = w - knob - 6.0
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(
            QPointF(3.0 + knob / 2 + travel * self._pos, h / 2.0),
            knob / 2,
            knob / 2,
        )


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
        if not self.isEnabled():
            return QColor(TEXT_FAINT)
        if self.isChecked():
            return QColor(TEXT_MAIN)
        return QColor(TEXT_MUTED) if not self.underMouse() else QColor(TEXT_MAIN)

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
        metrics = QFontMetrics(self.font())
        text_w = metrics.horizontalAdvance(self.text())
        gx = self.width() / 2.0 - text_w / 2.0 - self.GLYPH_GAP - 7.0
        gy = self.height() / 2.0 - 5.5
        if self.property("recording"):
            path = QPainterPath()
            path.addRoundedRect(QRectF(gx, gy, 11, 11), 2, 2)
            p.fillPath(path, QColor("#FFFFFF"))
        else:
            paint_icon(p, "dot", QRectF(gx, gy, 11, 11), QColor(REC))

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
        self.rec = create_backend(self.cfg)
        self.setWindowTitle("CastMane")
        self.resize(820, 600)
        self.setMinimumSize(680, 500)
        self.setStyleSheet(STYLESHEET)
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

        self._is_wayland = session_is_wayland()
        self._retranslate()
        self._refresh_idle_status()

    # --- Construction ---

    def _build_header(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Header")
        bar.setFixedHeight(HEADER_H)
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(10)

        mark = QLabel()
        mark.setFixedSize(28, 28)
        mark.setScaledContents(True)
        mark_file = mark_path()
        if mark_file:
            mark.setPixmap(QPixmap(mark_file))
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

        self.lang_seg = SegmentedControl(
            [(LANGUAGE_LABELS[code], code) for code in SUPPORTED_LANGUAGES]
        )
        self.lang_seg.setFixedWidth(104)
        self.lang_seg.set_current_data(self.cfg.language)
        self.lang_seg.changed.connect(self._on_language_changed)
        row.addWidget(self.lang_seg)

        self.timer_lbl = QLabel("00:00:00")
        self.timer_lbl.setObjectName("Timer")
        self.timer_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.timer_lbl.setProperty("recording", False)
        font = QFont()
        font.setFamily("JetBrains Mono")
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
        layout.addWidget(self.pages)
        layout.addStretch(1)
        scroll.setWidget(holder)
        return scroll

    def _row(
        self,
        label: QLabel,
        control: QWidget,
        hint: QLabel | None = None,
    ) -> QWidget:
        """One settings row: fixed label column, control column, hint below."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 12, 0, 12)
        layout.setSpacing(8)
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
        layout.setSpacing(0)

        self.lbl_source = QLabel()
        self.lbl_source.setObjectName("RowLabel")
        self.mode_seg = SegmentedControl(
            [("", "fullscreen"), ("", "window"), ("", "ask")]
        )
        self.mode_seg.set_current_data(self.cfg.capture_mode)
        self.mode_seg.changed.connect(self._on_mode_changed)
        self.hint_mode = QLabel()
        self.hint_mode.setObjectName("Hint")
        layout.addWidget(self._row(self.lbl_source, self.mode_seg, self.hint_mode))
        layout.addWidget(self._hairline())

        self.lbl_quality = QLabel()
        self.lbl_quality.setObjectName("RowLabel")
        self.quality_seg = SegmentedControl(
            [("", "draft"), ("", "balanced"), ("", "high")]
        )
        self.quality_seg.set_current_data(self.cfg.quality_preset)
        self.quality_seg.changed.connect(self._on_quality_changed)
        self.hint_quality = QLabel()
        self.hint_quality.setObjectName("Hint")
        layout.addWidget(
            self._row(self.lbl_quality, self.quality_seg, self.hint_quality)
        )
        return page

    def _build_audio_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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
        layout.addWidget(self._row(self.audio_lbl, audio_wrap))
        layout.addWidget(self._hairline())

        self.lbl_audio_mode = QLabel()
        self.lbl_audio_mode.setObjectName("RowLabel")
        self.audio_mode_seg = SegmentedControl(
            [("", "mic"), ("", "desktop"), ("", "both")]
        )
        self.audio_mode_seg.set_current_data(self.cfg.audio_mode)
        self.audio_mode_seg.changed.connect(self._on_audio_mode_changed)
        self.hint_audio_mode = QLabel()
        self.hint_audio_mode.setObjectName("Hint")
        layout.addWidget(
            self._row(self.lbl_audio_mode, self.audio_mode_seg, self.hint_audio_mode)
        )
        layout.addWidget(self._hairline())

        self.lbl_gain = QLabel()
        self.lbl_gain.setObjectName("RowLabel")
        gain_wrap = QWidget()
        gain_row = QHBoxLayout(gain_wrap)
        gain_row.setContentsMargins(0, 0, 0, 0)
        gain_row.setSpacing(10)
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(10, 500)
        self.gain_slider.setSingleStep(10)
        self.gain_slider.setPageStep(50)
        self.gain_slider.setValue(int(round(self.cfg.audio_gain * 100)))
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        gain_row.addWidget(self.gain_slider, 1)
        self.gain_value = QLabel()
        self.gain_value.setObjectName("RowLabel")
        self.gain_value.setMinimumWidth(52)
        self.gain_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gain_row.addWidget(self.gain_value)
        layout.addWidget(self._row(self.lbl_gain, gain_wrap))
        layout.addWidget(self._hairline())

        self.lbl_source_name = QLabel()
        self.lbl_source_name.setObjectName("RowLabel")
        self.audio_source_edit = QLineEdit(self.cfg.audio_source)
        self.audio_source_edit.setPlaceholderText("auto")
        self.audio_source_edit.textChanged.connect(self._on_audio_source_changed)
        self.hint_audio = QLabel()
        self.hint_audio.setObjectName("Hint")
        layout.addWidget(
            self._row(self.lbl_source_name, self.audio_source_edit, self.hint_audio)
        )
        layout.addWidget(self._hairline())

        self.lbl_desktop_source_name = QLabel()
        self.lbl_desktop_source_name.setObjectName("RowLabel")
        self.audio_desktop_edit = QLineEdit(self.cfg.audio_desktop_source)
        self.audio_desktop_edit.setPlaceholderText("auto")
        self.audio_desktop_edit.textChanged.connect(self._on_audio_desktop_changed)
        layout.addWidget(
            self._row(self.lbl_desktop_source_name, self.audio_desktop_edit)
        )
        return page

    def _build_region_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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
        layout.addWidget(self._row(self.lbl_region, grid_wrap, self.hint_region))
        return page

    def _build_transport(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("Transport")
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)
        self.record_btn = RecordButton()
        self.record_btn.clicked.connect(self.toggle)
        row.addWidget(self.record_btn, 1)
        self.pause_btn = QPushButton()
        self.pause_btn.setObjectName("Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setFixedWidth(118)
        row.addWidget(self.pause_btn)
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
            self.tab_buttons, ("tab_capture", "tab_audio", "tab_region")
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
            ]
        )
        self._refresh_quality_hint()

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
        self.lbl_gain.setText(_get("label_gain", lang))
        self.lbl_source_name.setText(_get("label_source_name", lang))
        self.lbl_desktop_source_name.setText(_get("label_desktop_source", lang))
        self.hint_audio.setText(_get("audio_hint", lang))
        self._refresh_gain_label()

        self.lbl_region.setText(_get("label_region", lang))
        self.hint_region.setText(_get("region_hint", lang))

        self.backend_lbl.setText(_get("backend_line", lang).format(name=self.rec.name))
        self.folder_btn.setToolTip(_get("open_folder", lang))
        self._refresh_outcome()
        self._paint_folder_icon()

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
            QColor(TEXT_SOFT),
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
            self.status_dot.set_color(PAUSED)
        elif self.rec.state.active:
            self.status_dot.set_color(REC)
        else:
            self.status_dot.set_color(READY)

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

    def _refresh_gain_label(self) -> None:
        self.gain_value.setText(self.t("gain_value").format(pct=self.gain_slider.value()))

    def _on_language_changed(self, code: str) -> None:
        if not code:
            return
        self.cfg.language = normalize(code)
        try:
            self.rec.cfg.language = self.cfg.language
        except AttributeError:
            pass
        self._retranslate()

    def _select_tab(self, code: str) -> None:
        self.pages.setCurrentWidget(self.pages.widget(self._page_index(code)))

    def _page_index(self, code: str) -> int:
        return ("capture", "audio", "region").index(code)

    # --- Recording control ---

    def _set_recording_ui(self, recording: bool) -> None:
        self.record_btn.set_recording(recording)
        self.timer_lbl.setProperty("recording", recording)
        _repolish(self.timer_lbl)
        self._refresh_state_dot()

    def _set_inputs_enabled(self, enabled: bool) -> None:
        self.mode_seg.set_enabled(enabled)
        self.quality_seg.set_enabled(enabled)
        self.lang_seg.set_enabled(enabled)
        self.audio_sw.setEnabled(enabled)
        self.audio_mode_seg.set_enabled(enabled)
        self.gain_slider.setEnabled(enabled)
        self.audio_source_edit.setEnabled(enabled)
        self.audio_desktop_edit.setEnabled(enabled)
        self._set_region_enabled(enabled)

    def toggle(self) -> None:
        if not self.rec.state.active:
            try:
                final = self.rec.start()
            except FileNotFoundError:
                self._fail(self.t("deps_missing"))
                return
            except Exception as e:  # noqa: BLE001
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
        else:
            out = self.rec.stop()
            self.timer.stop()
            self._set_inputs_enabled(True)
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText(self.t("pause"))
            if out:
                self._clear_error()
                self.status_lbl.setText(self.t("saved").format(out=out))
            else:
                self._fail(
                    self.t("error_prefix").format(err=self.rec.state.last_error)
                )
            self.record_btn.setText(self.t("rec_start"))
            self._set_recording_ui(False)

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
            self._clear_error()
            self._refresh_state_dot()
        except Exception as e:  # noqa: BLE001
            self._fail(self.t("pause_error").format(err=e))

    def open_output_folder(self) -> None:
        path = self.cfg.output_dir
        try:
            path.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:  # noqa: BLE001
            self._fail(self.t("error_prefix").format(err=e))

    # --- Setting handlers ---

    def _on_audio_toggled(self, checked: bool) -> None:
        self.cfg.audio_enabled = checked
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
        self._refresh_gain_label()

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
        self._refresh_quality_hint()

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
        if self.rec.state.active:
            self.rec.stop()
        super().closeEvent(event)
