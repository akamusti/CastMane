"""Hand-drawn vector icons.

Everything the chrome needs is drawn here with QPainter paths in a 0..1
box, then scaled into the target rect. No icon font, no SVG files, no
downloads: the icons inherit whatever colour a state calls for, which is
what keeps the sidebar and the buttons consistent while an icon is
hovered, checked or disabled.
"""
from __future__ import annotations

from math import cos, pi, sin

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTransform,
)

# Icons stroked with a pen: monitors, gauges, frames, glyph outlines.
_STROKED = (
    "monitor",
    "studio",
    "camera",
    "audio",
    "region",
    "power",
    "folder",
    "gear",
    "refresh",
    "mic",
    "speaker",
)
# Icons filled solid: the small transport glyphs.
_FILLED = ("dot", "stop", "pause", "play", "sparkle")

# Fraction of the icon's short side used as the stroke width.
_STROKE = 0.09


def _geometry(name: str) -> QPainterPath:
    """Return the icon outline in a 0..1 coordinate box."""
    p = QPainterPath()
    if name == "monitor":
        p.addRoundedRect(QRectF(0.07, 0.14, 0.86, 0.56), 0.11, 0.11)
        p.moveTo(0.5, 0.7)
        p.lineTo(0.5, 0.85)
        p.moveTo(0.31, 0.86)
        p.lineTo(0.69, 0.86)
    elif name == "studio":
        # Monitor outline with a play triangle in the screen area.
        p.addRoundedRect(QRectF(0.07, 0.14, 0.86, 0.56), 0.11, 0.11)
        p.moveTo(0.5, 0.7)
        p.lineTo(0.5, 0.85)
        p.moveTo(0.31, 0.86)
        p.lineTo(0.69, 0.86)
        p.moveTo(0.44, 0.30)
        p.lineTo(0.62, 0.42)
        p.lineTo(0.44, 0.54)
        p.closeSubpath()
    elif name == "camera":
        # Camera body + lens ring.
        p.addRoundedRect(QRectF(0.12, 0.30, 0.76, 0.48), 0.10, 0.10)
        p.moveTo(0.32, 0.30)
        p.lineTo(0.40, 0.20)
        p.lineTo(0.60, 0.20)
        p.lineTo(0.68, 0.30)
        p.addEllipse(QRectF(0.38, 0.42, 0.24, 0.24))
    elif name == "audio":
        # Waveform: the centre bar is the tallest, the ends taper off.
        for x, height in (
            (0.16, 0.32),
            (0.32, 0.58),
            (0.5, 0.84),
            (0.68, 0.48),
            (0.84, 0.24),
        ):
            p.addRoundedRect(
                QRectF(x - 0.055, 0.5 - height / 2, 0.11, height), 0.055, 0.055
            )
    elif name == "region":
        inset, arm = 0.14, 0.2
        p.moveTo(inset, inset + arm)
        p.lineTo(inset, inset)
        p.lineTo(inset + arm, inset)
        p.moveTo(1 - inset - arm, inset)
        p.lineTo(1 - inset, inset)
        p.lineTo(1 - inset, inset + arm)
        p.moveTo(1 - inset, 1 - inset - arm)
        p.lineTo(1 - inset, 1 - inset)
        p.lineTo(1 - inset - arm, 1 - inset)
        p.moveTo(inset + arm, 1 - inset)
        p.lineTo(inset, 1 - inset)
        p.lineTo(inset, 1 - inset - arm)
    elif name == "power":
        # Open arc on the top-left..top-right, plus the vertical stem.
        p.arcMove(QRectF(0.22, 0.22, 0.56, 0.56), 56)
        p.arcTo(QRectF(0.22, 0.22, 0.56, 0.56), 56, 248)
        p.moveTo(0.5, 0.08)
        p.lineTo(0.5, 0.36)
    elif name == "folder":
        p.addRoundedRect(QRectF(0.08, 0.31, 0.84, 0.49), 0.08, 0.08)
        p.moveTo(0.33, 0.31)
        p.lineTo(0.33, 0.23)
        p.lineTo(0.63, 0.23)
        p.lineTo(0.63, 0.31)
    elif name == "gear":
        # Ring plus eight teeth: reads as a settings cog at 16px.
        p.addEllipse(QRectF(0.30, 0.30, 0.40, 0.40))
        for i in range(8):
            angle = pi / 8 + i * pi / 4
            p.moveTo(0.5 + 0.21 * cos(angle), 0.5 + 0.21 * sin(angle))
            p.lineTo(0.5 + 0.30 * cos(angle), 0.5 + 0.30 * sin(angle))
    elif name == "dot":
        p.addEllipse(QRectF(0.22, 0.22, 0.56, 0.56))
    elif name == "stop":
        p.addRoundedRect(QRectF(0.22, 0.22, 0.56, 0.56), 0.13, 0.13)
    elif name == "pause":
        for x in (0.29, 0.59):
            p.addRoundedRect(QRectF(x, 0.25, 0.12, 0.5), 0.06, 0.06)
    elif name == "play":
        p.moveTo(0.32, 0.22)
        p.lineTo(0.78, 0.50)
        p.lineTo(0.32, 0.78)
        p.closeSubpath()
    elif name == "refresh":
        # 270 deg circular arc with an arrow tip
        p.arcMove(QRectF(0.20, 0.20, 0.60, 0.60), 45)
        p.arcTo(QRectF(0.20, 0.20, 0.60, 0.60), 45, 270)
        # arrow head at top
        p.moveTo(0.50, 0.10)
        p.lineTo(0.65, 0.22)
        p.lineTo(0.50, 0.34)
    elif name == "mic":
        # Mic capsule + stand
        p.addRoundedRect(QRectF(0.38, 0.15, 0.24, 0.44), 0.12, 0.12)
        p.arcMove(QRectF(0.26, 0.28, 0.48, 0.42), 0)
        p.arcTo(QRectF(0.26, 0.28, 0.48, 0.42), 0, -180)
        p.moveTo(0.50, 0.70)
        p.lineTo(0.50, 0.85)
        p.moveTo(0.34, 0.85)
        p.lineTo(0.66, 0.85)
    elif name == "speaker":
        # Speaker cone
        p.moveTo(0.18, 0.38)
        p.lineTo(0.32, 0.38)
        p.lineTo(0.52, 0.22)
        p.lineTo(0.52, 0.78)
        p.lineTo(0.32, 0.62)
        p.lineTo(0.18, 0.62)
        p.closeSubpath()
        # Sound waves
        p.arcMove(QRectF(0.42, 0.35, 0.30, 0.30), -45)
        p.arcTo(QRectF(0.42, 0.35, 0.30, 0.30), -45, 90)
        p.arcMove(QRectF(0.35, 0.24, 0.48, 0.52), -45)
        p.arcTo(QRectF(0.35, 0.24, 0.48, 0.52), -45, 90)
    elif name == "sparkle":
        # 4-pointed sparkle / star
        p.moveTo(0.50, 0.16)
        p.quadTo(0.50, 0.50, 0.84, 0.50)
        p.quadTo(0.50, 0.50, 0.50, 0.84)
        p.quadTo(0.50, 0.50, 0.16, 0.50)
        p.quadTo(0.50, 0.50, 0.50, 0.16)
        p.closeSubpath()
    return p


def paint_icon(
    painter: QPainter,
    name: str,
    rect: QRectF,
    color: QColor | str,
) -> None:
    """Draw ``name`` inside ``rect`` using ``color``.

    Unknown names are ignored on purpose: a missing icon should never
    take the window down, it should just leave the space empty.
    """
    if name not in _STROKED and name not in _FILLED:
        return
    tint = QColor(color)
    if not tint.isValid():
        return

    box = QRectF(rect)
    if box.width() <= 0 or box.height() <= 0:
        return

    path = _geometry(name)
    # Row-vector convention: point * (A * B) applies A first, then B.
    # Scale the 0..1 geometry into shape first, then move it to box.x/y.
    matrix = QTransform.fromScale(box.width(), box.height()) * QTransform.fromTranslate(
        box.x(), box.y()
    )
    path = matrix.map(path)

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)
    if name in _FILLED:
        painter.setPen(Qt.NoPen)
        painter.setBrush(tint)
        painter.drawPath(path)
    else:
        width = max(1.0, min(box.width(), box.height()) * _STROKE)
        painter.setPen(QPen(tint, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
    painter.restore()


def tray_pixmap(px: int = 64, color: QColor | str = "#FFFFFF") -> QPixmap:
    """White symbolic top-bar pixmap: monitor outline + centre dot.

    GNOME top bar icons are monochrome white (like Discord's). The
    colourful ``logo.png`` stays as the window/desktop icon ("ana
    simge"); this is only for ``QSystemTrayIcon`` so it blends in
    with the other white indicators.
    """
    tint = QColor(color)
    if not tint.isValid():
        tint = QColor("#FFFFFF")
    side = max(16, int(px))
    pix = QPixmap(side, side)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    # Monitor fills the box; dot sits in the middle of the screen area
    # (screen centre y ~= 0.42 in the 0..1 geometry).
    paint_icon(p, "monitor", QRectF(0, 0, side, side), tint)
    dot_side = side * 0.24
    paint_icon(
        p,
        "dot",
        QRectF(
            (side - dot_side) / 2.0,
            side * 0.42 - dot_side / 2.0,
            dot_side,
            dot_side,
        ),
        tint,
    )
    p.end()
    return pix


def tray_icon(color: QColor | str = "#FFFFFF") -> QIcon:
    """White ``QIcon`` for the system tray (top bar)."""
    return QIcon(tray_pixmap(64, color))
