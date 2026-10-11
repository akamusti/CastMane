"""Qt main window.

Layout (top to bottom):
  1. Header      - logo, wordmark, EN/TR segmented switch
  2. Hero card   - status pill, monospace timer, thin activity bar
  3. Record      - full-width primary button
  4. Actions     - pause (expands) + quit (compact)
  5. Tab bar     - Capture / Audio / Region
  6. Page card   - stacked settings pages
  7. Footer      - output folder hint
"""
from __future__ import annotations

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
    QLinearGradient,
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
from .theme import (
    ACCENT_CYAN,
    ACCENT_GRADIENT,
    ACCENT_INDIGO,
    ACCENT_PURPLE,
    BG_BASE,
    BG_CARD,
    BG_DISABLED,
    BG_HOVER,
    BG_INPUT,
    BG_PRESSED,
    BG_SUNKEN,
    BORDER,
    BORDER_HOVER,
    FONT_MONO,
    FONT_UI,
    RECORD_BG,
    RECORD_BG_HOVER,
    RECORD_BORDER,
    RECORD_RED,
    RADIUS_CARD,
    RADIUS_CONTROL,
    RADIUS_SMALL,
    TEXT_DISABLED,
    TEXT_FAINT,
    TEXT_MAIN,
    TEXT_MUTED,
    logo_path,
)

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_BASE};
    color: {TEXT_MAIN};
    font-family: {FONT_UI};
    font-size: 13px;
}}
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: {BG_BASE};
    border: none;
}}
/* --- Cards --- */
QFrame#Card {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CARD}px;
}}
QFrame#TabBar {{
    background-color: {BG_DISABLED};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
}}
QFrame#Divider {{
    background-color: {BORDER};
    border: none;
    max-height: 1px;
}}
/* --- Text --- */
QLabel {{
    background: transparent;
}}
QLabel#Wordmark {{
    color: {TEXT_MAIN};
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 0.3px;
}}
QLabel#WordmarkSub {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QLabel#Timer {{
    color: {TEXT_MAIN};
}}
QLabel#Timer[recording="true"] {{
    color: {RECORD_RED};
}}
QLabel#Pill {{
    color: {TEXT_MUTED};
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.2px;
}}
QLabel#Pill[state="recording"] {{
    color: {RECORD_RED};
    background-color: #2A1A22;
    border-color: {RECORD_BORDER};
}}
QLabel#Pill[state="paused"] {{
    color: {ACCENT_PURPLE};
    background-color: #241B34;
    border-color: #4A2F73;
}}
QLabel#StatusLine {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel#FieldName {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.8px;
}}
QLabel#FieldValue {{
    color: {TEXT_MAIN};
    font-size: 12px;
}}
QLabel#Hint {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QLabel#Footer {{
    color: {TEXT_FAINT};
    font-size: 11px;
}}
QLabel#ErrorLine {{
    color: {RECORD_RED};
    font-size: 11px;
}}
/* --- Buttons --- */
QPushButton {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_CONTROL}px;
    padding: 8px 14px;
    color: {TEXT_MAIN};
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {BORDER_HOVER};
}}
QPushButton:pressed {{
    background-color: {BG_PRESSED};
}}
QPushButton:disabled {{
    background-color: {BG_DISABLED};
    color: {TEXT_DISABLED};
    border-color: {BORDER};
}}
/* Tab bar buttons */
QPushButton#Tab {{
    background: transparent;
    border: none;
    border-radius: {RADIUS_SMALL}px;
    padding: 7px 6px;
    color: {TEXT_FAINT};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#Tab:hover {{
    color: {TEXT_MAIN};
    background-color: {BG_HOVER};
}}
QPushButton#Tab:checked {{
    background-color: {ACCENT_GRADIENT};
    color: #FFFFFF;
    font-weight: 700;
}}
/* Segmented switch (language, source, quality) */
QPushButton#Seg {{
    background: transparent;
    border: none;
    border-radius: {RADIUS_SMALL}px;
    padding: 7px 4px;
    color: {TEXT_MUTED};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#Seg:hover {{
    color: {TEXT_MAIN};
    background-color: {BG_HOVER};
}}
QPushButton#Seg:checked {{
    background-color: {BG_SUNKEN};
    color: {ACCENT_CYAN};
    font-weight: 700;
}}
/* Primary record button */
QPushButton#Record {{
    background-color: {ACCENT_GRADIENT};
    border: none;
    border-radius: {RADIUS_CARD}px;
    padding: 15px 20px;
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 800;
    letter-spacing: 0.4px;
}}
QPushButton#Record:hover {{
    background-color: {ACCENT_INDIGO};
}}
QPushButton#Record:pressed {{
    background-color: #4A43D6;
}}
QPushButton#Record[recording="true"] {{
    background-color: {RECORD_BG};
    border: 1px solid {RECORD_BORDER};
}}
QPushButton#Record[recording="true"]:hover {{
    background-color: {RECORD_BG_HOVER};
}}
QPushButton#Quit {{
    background: transparent;
    border-color: {BORDER};
    color: {TEXT_MUTED};
    padding: 9px 18px;
}}
QPushButton#Quit:hover {{
    background-color: {BG_HOVER};
    color: {RECORD_RED};
    border-color: {RECORD_BORDER};
}}
/* --- Inputs --- */
QLineEdit, QSpinBox {{
    background-color: {BG_SUNKEN};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_SMALL}px;
    padding: 7px 10px;
    color: {TEXT_MAIN};
    selection-background-color: {ACCENT_INDIGO};
}}
QLineEdit:focus, QSpinBox:focus {{
    border-color: {ACCENT_CYAN};
}}
QLineEdit:disabled, QSpinBox:disabled {{
    color: {TEXT_DISABLED};
    background-color: {BG_DISABLED};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 0px;
    border: none;
}}
QSlider::groove:horizontal {{
    height: 5px;
    background: {BG_INPUT};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT_GRADIENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: #FFFFFF;
    border: 2px solid {ACCENT_CYAN};
    width: 15px;
    height: 15px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    border-color: #FFFFFF;
}}
QSlider:disabled::sub-page:horizontal {{
    background: {TEXT_DISABLED};
}}
QSlider:disabled::handle:horizontal {{
    border-color: {TEXT_DISABLED};
    background: {BG_DISABLED};
}}
/* --- Scrollbars --- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_HOVER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_DISABLED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QToolTip {{
    background-color: {BG_CARD};
    color: {TEXT_MAIN};
    border: 1px solid {BORDER_HOVER};
    padding: 5px 8px;
}}
"""

LANGUAGE_LABELS = {"en": "EN", "tr": "TR"}
LANGUAGE_NAMES = {"en": "English", "tr": "Türkçe"}


def _repolish(widget: QWidget) -> None:
    """Re-evaluate the stylesheet after a dynamic property changed."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ActivityBar(QWidget):
    """Thin indeterminate bar; animates only while recording."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(4)
        self._phase = 0.0
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._advance)

    def set_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        if active:
            self._phase = 0.0
            self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def _advance(self) -> None:
        if not self._active:
            return
        self._phase = (self._phase + 0.013) % 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        radius = self.height() / 2.0
        track = QPainterPath()
        track.addRoundedRect(QRectF(self.rect()), radius, radius)
        p.fillPath(track, QColor(BORDER))
        if not self._active:
            return
        width = self.width()
        segment = max(56.0, width * 0.38)
        travel = width + segment
        x = -segment + travel * self._phase
        grad = QLinearGradient(x, 0, x + segment, 0)
        start = QColor(ACCENT_INDIGO)
        start.setAlpha(0)
        mid = QColor(ACCENT_CYAN)
        end = QColor(ACCENT_CYAN)
        end.setAlpha(0)
        grad.setColorAt(0.0, start)
        grad.setColorAt(0.5, mid)
        grad.setColorAt(1.0, end)
        p.fillPath(track, grad)


class Switch(QAbstractButton):
    """Hand-painted toggle so it matches the theme exactly."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._pos = 0.0
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

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(46, 26)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        track = QRectF(0.5, 0.5, w - 1.0, h - 1.0)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG_INPUT))
        p.drawRoundedRect(track.adjusted(1.5, 1.5, -1.5, -1.5), 11, 11)

        if self._pos > 0.01:
            grad = QLinearGradient(track.topLeft(), track.topRight())
            on = QColor(ACCENT_INDIGO)
            on.setAlphaF(self._pos)
            other = QColor(ACCENT_CYAN)
            other.setAlphaF(self._pos)
            grad.setColorAt(0.0, on)
            grad.setColorAt(1.0, other)
            p.setBrush(grad)
            p.drawRoundedRect(track.adjusted(1.5, 1.5, -1.5, -1.5), 11, 11)

        border = QColor(BORDER)
        if self._pos > 0.5:
            border = QColor(ACCENT_CYAN)
            # Ramp the highlight in over the second half of the slide.
            border.setAlphaF((self._pos - 0.5) * 2.0)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(border, 1.0))
        p.drawRoundedRect(track, 12, 12)

        knob = h - 10.0
        travel = w - knob - 8.0
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(4.0 + knob / 2 + travel * self._pos, h / 2.0),
                     knob / 2, knob / 2)


class RecordButton(QPushButton):
    """Primary action: painted status glyph beside the label."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Record")
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("recording", False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(52)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        metrics = QFontMetrics(self.font())
        text_w = metrics.horizontalAdvance(self.text())
        cx = self.width() / 2.0 - text_w / 2.0 - 13.0
        cy = self.height() / 2.0
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        if self.property("recording"):
            p.drawRoundedRect(QRectF(cx - 5.5, cy - 5.5, 11, 11), 2, 2)
        else:
            p.drawEllipse(QPointF(cx, cy), 6.0, 6.0)

    def set_recording(self, recording: bool) -> None:
        self.setProperty("recording", recording)
        _repolish(self)


class SegmentedControl(QWidget):
    """Row of mutually exclusive buttons (source, quality, language)."""

    changed = Signal(str)

    def __init__(
        self,
        entries: list[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entries = list(entries)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        for label, data in self._entries:
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


class MainWindow(QMainWindow):
    # Horizontal chrome that eats into the timer's usable width:
    # outer layout margins + hero card margins + a safety gap.
    TIMER_CHROME = 18 * 2 + 22 * 2 + 12
    TIMER_MAX_PX = 54
    TIMER_MIN_PX = 26
    # Widest glyph run is "00:00:00" -> 8 mono characters.
    TIMER_CHARS = 8

    def __init__(self, cfg: AppConfig | None = None) -> None:
        super().__init__()
        self.cfg = cfg or AppConfig()
        self.cfg.language = normalize(self.cfg.language)
        self.rec = create_backend(self.cfg)
        self.setWindowTitle("CastMane")
        self.resize(440, 700)
        self.setMinimumSize(340, 520)
        self.setStyleSheet(STYLESHEET)
        icon_path = logo_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)

        root = QWidget()
        root.setObjectName("Root")
        scroll.setWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        outer.addWidget(self._build_header(icon_path))
        outer.addWidget(self._build_hero())
        outer.addLayout(self._build_actions())
        outer.addWidget(self._build_tabbar())
        outer.addWidget(self._build_pages())
        outer.addWidget(self._build_footer())
        outer.addStretch(1)

        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.tick)

        self._is_wayland = session_is_wayland()
        self._retranslate()
        self._refresh_idle_status()

    # --- Construction ---

    def _build_header(self, icon_path: str | None) -> QWidget:
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        logo = QLabel()
        logo.setFixedSize(42, 42)
        logo.setScaledContents(True)
        logo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if icon_path:
            logo.setPixmap(QPixmap(icon_path))
        row.addWidget(logo)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        title = QLabel("CastMane")
        title.setObjectName("Wordmark")
        title.setMinimumWidth(0)
        font = QFont()
        font.setBold(True)
        title.setFont(font)
        self.subtitle_lbl = QLabel()
        self.subtitle_lbl.setObjectName("WordmarkSub")
        self.subtitle_lbl.setWordWrap(True)
        self.subtitle_lbl.setMinimumWidth(0)
        text.addWidget(title)
        text.addWidget(self.subtitle_lbl)
        row.addLayout(text, 1)

        self.lang_seg = SegmentedControl(
            [(LANGUAGE_LABELS[code], code) for code in SUPPORTED_LANGUAGES]
        )
        self.lang_seg.setFixedWidth(92)
        self.lang_seg.set_current_data(self.cfg.language)
        self.lang_seg.changed.connect(self._on_language_changed)
        row.addWidget(self.lang_seg, 0)
        return header

    def _build_hero(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        pill_row = QHBoxLayout()
        pill_row.setContentsMargins(0, 0, 0, 0)
        self.pill_lbl = QLabel()
        self.pill_lbl.setObjectName("Pill")
        self.pill_lbl.setProperty("state", "ready")
        self.pill_lbl.setAlignment(Qt.AlignCenter)
        self.pill_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        pill_row.addWidget(self.pill_lbl)
        pill_row.addStretch(1)
        layout.addLayout(pill_row)

        self.timer_lbl = QLabel("00:00:00")
        self.timer_lbl.setObjectName("Timer")
        self.timer_lbl.setAlignment(Qt.AlignCenter)
        self.timer_lbl.setProperty("recording", False)
        self.timer_lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.timer_lbl.setMinimumWidth(0)
        self._timer_px = -1
        self._apply_timer_font()
        layout.addWidget(self.timer_lbl)

        self.activity = ActivityBar()
        layout.addWidget(self.activity)

        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("StatusLine")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        self.record_btn = RecordButton()
        self.record_btn.clicked.connect(self.toggle)
        layout.addWidget(self.record_btn)
        return card

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self.pause_btn = QPushButton()
        self.pause_btn.setEnabled(False)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setMinimumHeight(38)
        row.addWidget(self.pause_btn, 1)

        self.quit_btn = QPushButton()
        self.quit_btn.setObjectName("Quit")
        self.quit_btn.setCursor(Qt.PointingHandCursor)
        self.quit_btn.clicked.connect(self.close)
        self.quit_btn.setMinimumHeight(38)
        row.addWidget(self.quit_btn, 0)
        return row

    def _build_tabbar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TabBar")
        bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_buttons: list[QPushButton] = []
        for code in ("capture", "audio", "region"):
            btn = QPushButton(code, self)
            btn.setObjectName("Tab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("page", code)
            btn.clicked.connect(lambda _=False, c=code: self._select_tab(c))
            self.tab_group.addButton(btn)
            layout.addWidget(btn, 1)
            self.tab_buttons.append(btn)
        self.tab_buttons[0].setChecked(True)
        return bar

    def _build_pages(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 16, 18, 18)
        outer.setSpacing(0)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_capture_page())
        self.pages.addWidget(self._build_audio_page())
        self.pages.addWidget(self._build_region_page())
        outer.addWidget(self.pages)
        return card

    @staticmethod
    def _field(
        name_lbl: QLabel,
        value_widget: QWidget,
        hint: QLabel | None = None,
    ) -> QWidget:
        """Row: label on the left, control on the right, hint underneath."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        name_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        top.addWidget(name_lbl, 0, Qt.AlignVCenter)
        top.addWidget(value_widget, 1, Qt.AlignVCenter)
        layout.addLayout(top)
        if hint is not None:
            layout.addWidget(hint)
        return box

    def _build_capture_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.lbl_source = QLabel()
        self.lbl_source.setObjectName("FieldName")
        self.mode_seg = SegmentedControl(
            [("", "fullscreen"), ("", "window"), ("", "ask")]
        )
        self.mode_seg.set_current_data(self.cfg.capture_mode)
        self.mode_seg.changed.connect(self._on_mode_changed)
        self.hint_mode = QLabel()
        self.hint_mode.setObjectName("Hint")
        self.hint_mode.setWordWrap(True)
        layout.addWidget(self._field(self.lbl_source, self.mode_seg, self.hint_mode))

        divider = QFrame()
        divider.setObjectName("Divider")
        layout.addWidget(divider)

        self.lbl_quality = QLabel()
        self.lbl_quality.setObjectName("FieldName")
        self.quality_seg = SegmentedControl(
            [("", "draft"), ("", "balanced"), ("", "high")]
        )
        self.quality_seg.set_current_data(self.cfg.quality_preset)
        self.quality_seg.changed.connect(self._on_quality_changed)
        self.hint_quality = QLabel()
        self.hint_quality.setObjectName("Hint")
        self.hint_quality.setWordWrap(True)
        layout.addWidget(
            self._field(self.lbl_quality, self.quality_seg, self.hint_quality)
        )
        return page

    def _build_audio_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.setSpacing(12)
        self.audio_lbl = QLabel()
        self.audio_lbl.setObjectName("FieldName")
        self.audio_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toggle_row.addWidget(self.audio_lbl, 1)
        self.audio_sw = Switch()
        self.audio_sw.setChecked(self.cfg.audio_enabled)
        self.audio_sw.toggled.connect(self._on_audio_toggled)
        toggle_row.addWidget(self.audio_sw, 0)
        layout.addLayout(toggle_row)

        divider = QFrame()
        divider.setObjectName("Divider")
        layout.addWidget(divider)

        self.lbl_gain = QLabel()
        self.lbl_gain.setObjectName("FieldName")
        gain_box = QHBoxLayout()
        gain_box.setSpacing(10)
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(10, 500)
        self.gain_slider.setSingleStep(10)
        self.gain_slider.setPageStep(50)
        self.gain_slider.setValue(int(round(self.cfg.audio_gain * 100)))
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        self.gain_slider.setMinimumWidth(0)
        gain_box.addWidget(self.gain_slider, 1)
        self.gain_value = QLabel()
        self.gain_value.setObjectName("FieldValue")
        self.gain_value.setMinimumWidth(48)
        self.gain_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gain_box.addWidget(self.gain_value, 0)
        gain_container = QWidget()
        gain_container.setLayout(gain_box)
        gain_box.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._field(self.lbl_gain, gain_container))

        self.lbl_source_name = QLabel()
        self.lbl_source_name.setObjectName("FieldName")
        self.audio_source_edit = QLineEdit(self.cfg.audio_source)
        self.audio_source_edit.setPlaceholderText("auto")
        self.audio_source_edit.setMinimumWidth(0)
        self.audio_source_edit.textChanged.connect(self._on_audio_source_changed)
        self.hint_audio = QLabel()
        self.hint_audio.setObjectName("Hint")
        self.hint_audio.setWordWrap(True)
        layout.addWidget(
            self._field(
                self.lbl_source_name, self.audio_source_edit, self.hint_audio
            )
        )
        return page

    def _build_region_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.lbl_region = QLabel()
        self.lbl_region.setObjectName("FieldName")
        layout.addWidget(self.lbl_region)

        self.region_spins: dict[str, QSpinBox] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for i, (key, value) in enumerate(
            (
                ("x", self.cfg.region_x),
                ("y", self.cfg.region_y),
                ("w", self.cfg.region_w),
                ("h", self.cfg.region_h),
            )
        ):
            spin = QSpinBox()
            spin.setPrefix(f"{key.upper()} ")
            spin.setRange(0, 10000)
            spin.setValue(value)
            spin.setAlignment(Qt.AlignCenter)
            spin.valueChanged.connect(self._on_region_changed)
            spin.setMinimumWidth(0)
            spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.region_spins[key] = spin
            grid.addWidget(spin, i // 2, i % 2)
        layout.addLayout(grid)

        self.hint_region = QLabel()
        self.hint_region.setObjectName("Hint")
        self.hint_region.setWordWrap(True)
        layout.addWidget(self.hint_region)
        return page

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)
        self.output_lbl = QLabel()
        self.output_lbl.setObjectName("FieldName")
        self.outcome_lbl = QLabel()
        self.outcome_lbl.setObjectName("Footer")
        self.outcome_lbl.setWordWrap(True)
        self.error_lbl = QLabel()
        self.error_lbl.setObjectName("ErrorLine")
        self.error_lbl.setWordWrap(True)
        self.error_lbl.hide()
        layout.addWidget(self.output_lbl)
        layout.addWidget(self.outcome_lbl)
        layout.addWidget(self.error_lbl)
        return footer

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
        """Re-apply every static string after a language switch."""
        lang = self.cfg.language
        self.subtitle_lbl.setText(_get("subtitle", lang))
        self._refresh_idle_status()

        recording = self.rec.state.active
        self.record_btn.setText(
            _get("rec_stop", lang) if recording else _get("rec_start", lang)
        )
        self.pause_btn.setText(
            _get("resume", lang)
            if self.rec.state.paused
            else _get("pause", lang)
        )
        self.quit_btn.setText(_get("quit", lang))
        self._refresh_pill()

        # Tab bar.
        for btn, key in zip(
            self.tab_buttons, ("tab_capture", "tab_audio", "tab_region")
        ):
            btn.setText(_get(key, lang))

        # Capture page.
        self.lbl_source.setText(_get("label_source", lang).upper())
        self.mode_seg.set_labels(
            [
                _get("mode_fullscreen", lang),
                _get("mode_window", lang),
                _get("mode_ask", lang),
            ]
        )
        self._refresh_mode_hint()
        self.lbl_quality.setText(_get("label_quality", lang).upper())
        self.quality_seg.set_labels(
            [
                _get("quality_draft", lang),
                _get("quality_balanced", lang),
                _get("quality_high", lang),
            ]
        )
        self._refresh_quality_hint()

        # Audio page.
        self.audio_lbl.setText(_get("audio_check", lang))
        self.lbl_gain.setText(_get("label_gain", lang).upper())
        self.lbl_source_name.setText(_get("label_source_name", lang).upper())
        self.hint_audio.setText(_get("audio_hint", lang))
        self._refresh_gain_label()

        # Region page.
        self.lbl_region.setText(_get("label_region", lang).upper())
        self.hint_region.setText(_get("region_hint", lang))

        # Footer.
        self.output_lbl.setText(_get("label_output", lang).upper())
        self.outcome_lbl.setText(_get("outcome", lang))

    def _refresh_pill(self) -> None:
        lang = self.cfg.language
        if self.rec.state.paused:
            state, key = "paused", "pill_paused"
        elif self.rec.state.active:
            state, key = "recording", "pill_recording"
        else:
            state, key = "ready", "pill_ready"
        self.pill_lbl.setProperty("state", state)
        self.pill_lbl.setText(_get(key, lang))
        _repolish(self.pill_lbl)

    def _refresh_mode_hint(self) -> None:
        self.hint_mode.setText(
            self.t(f"mode_{self.mode_seg.current_data()}_hint")
        )

    def _refresh_quality_hint(self) -> None:
        self.hint_quality.setText(
            self.t(f"quality_{self.quality_seg.current_data()}_hint")
        )

    def _refresh_gain_label(self) -> None:
        self.gain_value.setText(
            self.t("gain_value").format(pct=self.gain_slider.value())
        )

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
        self.activity.set_active(recording)
        self._refresh_pill()

    def _set_inputs_enabled(self, enabled: bool) -> None:
        # Tab buttons stay clickable so pages remain readable mid-recording;
        # only the settings inside them are locked.
        self.mode_seg.set_enabled(enabled)
        self.quality_seg.set_enabled(enabled)
        self.lang_seg.set_enabled(enabled)
        self.audio_sw.setEnabled(enabled)
        self.gain_slider.setEnabled(enabled)
        self.audio_source_edit.setEnabled(enabled)
        self._set_region_enabled(enabled)

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
            self._clear_error()
            tmp = self.rec.state.tmp_path
            self.status_lbl.setText(
                self.t("recording_to").format(
                    name=tmp.name if tmp else final.name
                )
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
                self.status_lbl.setText(self.t("saved").format(out=out))
            else:
                self.status_lbl.setText(
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
            self._refresh_pill()
        except Exception as e:  # noqa: BLE001
            self.status_lbl.setText(self.t("pause_error").format(err=e))

    # --- Setting handlers ---

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
        self._refresh_gain_label()

    def _on_audio_source_changed(self, text: str) -> None:
        value = text.strip() or "auto"
        self.cfg.audio_source = value
        try:
            self.rec.cfg.audio_source = value
        except AttributeError:
            pass

    def _on_quality_changed(self, preset: str) -> None:
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

    # --- Timer scaling ---

    def _apply_timer_font(self) -> None:
        """Shrink the mono timer so 00:00:00 always fits the hero card.

        Set through the widget stylesheet on purpose: the global
        `QWidget { font-size: 13px }` rule would otherwise win over
        QWidget.setFont() and pin the timer to 13px.
        """
        available = max(0, self.width() - self.TIMER_CHROME)
        # Mono advance is ~0.6em per glyph; leave a little slack.
        size = int(available / (self.TIMER_CHARS * 0.62))
        size = max(self.TIMER_MIN_PX, min(self.TIMER_MAX_PX, size))
        if size == self._timer_px:
            return
        self._timer_px = size
        self.timer_lbl.setStyleSheet(
            f"QLabel#Timer {{ font-family: {FONT_MONO}; "
            f"font-size: {size}px; font-weight: 700; }}"
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_timer_font()

    # --- Errors ---

    def _clear_error(self) -> None:
        if not self.error_lbl.text():
            return
        self.error_lbl.clear()
        self.error_lbl.hide()

    def _show_error(self, err: object) -> None:
        self.error_lbl.setText(str(err))
        self.error_lbl.show()

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
            self._show_error(self.rec.state.last_error)
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