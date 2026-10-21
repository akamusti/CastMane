"""OBS-style preview stage: a screen frame with a draggable camera PiP.

The stage paints the frames itself (`QVideoSink` -> `QImage`) instead of
stacking two `QVideoWidget`s. A native video widget can sit above child
widgets on some compositors, which made a floating camera overlay
unreliable; painting both layers in one widget always stacks correctly and
lets us draw the OBS-like selection border and resize grip.

Geometry is stored the same way the recorders use it: `pos` is the
fraction of the free space (0 = left/top edge, 1 = right/bottom edge) and
`scale` is the camera width as a fraction of the frame width. Normalised
values survive a resolution change, so the preview matches the file.

No camera or media backend is required for the geometry: tests can drive
the widget with the public `set_position`/`set_scale` helpers.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QWheelEvent,
)
from PySide6.QtMultimedia import QVideoFrame, QVideoSink
from PySide6.QtWidgets import QSizePolicy, QWidget

from .camera import (
    CAMERA_POS_DEFAULT_X,
    CAMERA_POS_DEFAULT_Y,
    CAMERA_SCALE_DEFAULT,
    CAMERA_SCALE_MAX,
    CAMERA_SCALE_MIN,
    clamp_camera_position,
    clamp_camera_scale,
)

#: Corner buttons / double-click reset to these.
CORNER_POSITIONS = {
    "tl": (0.0, 0.0),
    "tr": (1.0, 0.0),
    "bl": (0.0, 1.0),
    "br": (1.0, 1.0),
}

_STAGE_RADIUS = 10.0
_CAMERA_RADIUS = 8.0
_GRIP_SIZE = 14.0
_EDGE_SNAP_PX = 12.0
_WHEEL_STEP = 0.02


def fit_aspect(outer: QRectF, aspect: float) -> QRectF:
    """Largest `aspect` (w/h) rectangle centred inside `outer`."""
    if outer.width() <= 0 or outer.height() <= 0:
        return QRectF(outer)
    if aspect <= 0:
        aspect = 16 / 9
    width = outer.width()
    height = width / aspect
    if height > outer.height():
        height = outer.height()
        width = height * aspect
    return QRectF(
        outer.x() + (outer.width() - width) / 2.0,
        outer.y() + (outer.height() - height) / 2.0,
        width,
        height,
    )


def camera_rect_for(
    content: QRectF,
    pos_x: float,
    pos_y: float,
    scale: float,
    aspect: float = 4 / 3,
) -> QRectF:
    """Camera rectangle inside `content` for normalised position/scale."""
    if content.width() <= 0 or content.height() <= 0:
        return QRectF()
    scale = clamp_camera_scale(scale)
    pos_x = clamp_camera_position(pos_x)
    pos_y = clamp_camera_position(pos_y)
    if aspect <= 0:
        aspect = 4 / 3
    width = content.width() * scale
    height = width / aspect
    # Never let the PiP swallow the stage (tiny windows, extreme scales).
    max_height = content.height() * 0.92
    if height > max_height:
        height = max_height
        width = height * aspect
    slack_x = max(0.0, content.width() - width)
    slack_y = max(0.0, content.height() - height)
    return QRectF(
        content.x() + slack_x * pos_x,
        content.y() + slack_y * pos_y,
        width,
        height,
    )


def position_from_rect(
    content: QRectF, rect: QRectF
) -> tuple[float, float]:
    """Inverse of `camera_rect_for`: rect -> normalised position."""
    slack_x = max(0.0, content.width() - rect.width())
    slack_y = max(0.0, content.height() - rect.height())
    px = (rect.x() - content.x()) / slack_x if slack_x > 0 else 0.0
    py = (rect.y() - content.y()) / slack_y if slack_y > 0 else 0.0
    return clamp_camera_position(px), clamp_camera_position(py)


@dataclass
class StageGeometry:
    """Normalised camera placement, as persisted in `AppConfig`."""

    pos_x: float = CAMERA_POS_DEFAULT_X
    pos_y: float = CAMERA_POS_DEFAULT_Y
    scale: float = CAMERA_SCALE_DEFAULT


class PreviewStage(QWidget):
    """Screen frame + draggable/resizable camera picture-in-picture."""

    #: (pos_x, pos_y, scale) after a drag, resize, corner snap or wheel.
    geometry_changed = Signal(float, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreviewStage")
        self.setMinimumHeight(180)
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._screen = QImage()
        self._camera = QImage()
        self._screen_aspect = 16 / 9
        self._camera_aspect = 4 / 3
        self._geometry = StageGeometry()
        self._camera_visible = False
        self._interactive = True
        self._placeholder = ""
        self._drag_mode = ""  # "" | "move" | "resize"
        self._drag_offset = QPointF()
        self._hover = False

        self.screen_sink = QVideoSink(self)
        self.screen_sink.videoFrameChanged.connect(self._on_screen_frame)
        self.camera_sink = QVideoSink(self)
        self.camera_sink.videoFrameChanged.connect(self._on_camera_frame)

    # --- media input -------------------------------------------------

    def _on_screen_frame(self, frame: QVideoFrame) -> None:
        image = self._frame_image(frame)
        if image is None:
            return
        self._screen = image
        if image.height() > 0:
            self._screen_aspect = image.width() / image.height()
        self.update()

    def _on_camera_frame(self, frame: QVideoFrame) -> None:
        image = self._frame_image(frame)
        if image is None:
            return
        self._camera = image
        if image.height() > 0:
            self._camera_aspect = image.width() / image.height()
        self.update()

    @staticmethod
    def _frame_image(frame: QVideoFrame) -> QImage | None:
        try:
            if not frame.isValid():
                return None
            image = frame.toImage()
        except Exception:  # noqa: BLE001 - a bad frame must not kill the UI
            return None
        return None if image.isNull() else image

    def clear_screen(self) -> None:
        """Drop the last screen frame (new take, otherwise it looks stale)."""
        self._screen = QImage()
        self.update()

    def clear_camera(self) -> None:
        self._camera = QImage()
        self.update()

    # --- public state ------------------------------------------------

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self.update()

    def set_camera_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if visible != self._camera_visible:
            self._camera_visible = visible
            self.update()

    def camera_visible(self) -> bool:
        return self._camera_visible

    def camera_aspect(self) -> float:
        """Aspect of the last camera frame (4:3 until one arrives)."""
        return self._camera_aspect

    def set_interactive(self, enabled: bool) -> None:
        self._interactive = bool(enabled)
        if not enabled:
            self._drag_mode = ""
            self._hover = False
            self.unsetCursor()
            self.update()

    def is_interactive(self) -> bool:
        return self._interactive

    def geometry(self) -> StageGeometry:
        return StageGeometry(
            self._geometry.pos_x, self._geometry.pos_y, self._geometry.scale
        )

    def set_position(self, pos_x: float, pos_y: float) -> None:
        self._geometry.pos_x = clamp_camera_position(pos_x)
        self._geometry.pos_y = clamp_camera_position(pos_y)
        self.update()

    def set_scale(self, scale: float) -> None:
        self._geometry.scale = clamp_camera_scale(scale)
        self.update()

    def set_corner(self, corner: str) -> None:
        pos = CORNER_POSITIONS.get(corner)
        if pos is None:
            return
        self.set_position(*pos)
        self._emit_geometry()

    def reset_camera(self) -> None:
        self.set_position(CAMERA_POS_DEFAULT_X, CAMERA_POS_DEFAULT_Y)
        self.set_scale(CAMERA_SCALE_DEFAULT)
        self._emit_geometry()

    def _emit_geometry(self) -> None:
        self.geometry_changed.emit(
            self._geometry.pos_x, self._geometry.pos_y, self._geometry.scale
        )

    # --- layout helpers ----------------------------------------------

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt override
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt override
        """Keep the stage near 16:9 so the video is not letterboxed twice."""
        return int(max(200, min(340, width * 9 / 16)))

    def content_rect(self) -> QRectF:
        """Letterboxed video area inside the widget (1 px inset)."""
        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        return fit_aspect(outer, self._screen_aspect)

    def camera_rect(self) -> QRectF:
        if not self._camera_visible:
            return QRectF()
        return camera_rect_for(
            self.content_rect(),
            self._geometry.pos_x,
            self._geometry.pos_y,
            self._geometry.scale,
            self._camera_aspect,
        )

    def _resize_grip_rect(self) -> QRectF:
        rect = self.camera_rect()
        if rect.isEmpty():
            return QRectF()
        return QRectF(
            rect.right() - _GRIP_SIZE,
            rect.bottom() - _GRIP_SIZE,
            _GRIP_SIZE,
            _GRIP_SIZE,
        )

    # --- painting ----------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHints(
            QPainter.Antialiasing | QPainter.SmoothPixmapTransform
        )
        stage = QPainterPath()
        stage.addRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            _STAGE_RADIUS,
            _STAGE_RADIUS,
        )
        p.fillPath(stage, QColor("#0B0B0D"))

        content = self.content_rect()
        p.save()
        p.setClipPath(stage)
        p.fillRect(content, QColor("#000000"))
        if not self._screen.isNull():
            p.drawImage(content, self._screen)
        elif self._placeholder:
            p.setPen(QColor(255, 255, 255, 78))
            font = p.font()
            font.setPixelSize(11)
            p.setFont(font)
            p.drawText(
                content,
                Qt.AlignCenter | Qt.TextWordWrap,
                self._placeholder,
            )
        p.restore()

        p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.drawRect(content.adjusted(0.5, 0.5, -0.5, -0.5))
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.drawPath(stage)

        if self._camera_visible:
            self._paint_camera(p)

    def _paint_camera(self, p: QPainter) -> None:
        rect = self.camera_rect()
        if rect.isEmpty():
            return
        active = self._drag_mode != "" or self._hover

        path = QPainterPath()
        path.addRoundedRect(rect, _CAMERA_RADIUS, _CAMERA_RADIUS)
        p.save()
        p.setClipPath(path)
        p.fillRect(rect, QColor("#141519"))
        if not self._camera.isNull():
            p.drawImage(rect, self._camera)
        else:
            p.setPen(QColor(255, 255, 255, 90))
            font = p.font()
            font.setPixelSize(10)
            font.setBold(True)
            p.setFont(font)
            p.drawText(rect, Qt.AlignCenter, "CAM")
        p.restore()

        pen = QPen(
            QColor(255, 255, 255, 220 if active else 120),
            2.0 if active else 1.0,
        )
        p.setPen(pen)
        p.drawPath(path)

        # Bottom-right resize grip: three short diagonals.
        grip = self._resize_grip_rect()
        if grip.isEmpty():
            return
        p.setPen(QPen(QColor(255, 255, 255, 170), 1.4))
        for offset in (2.0, 6.0, 10.0):
            p.drawLine(
                QPointF(grip.right() - offset, grip.bottom() - 1.0),
                QPointF(grip.right() - 1.0, grip.bottom() - offset),
            )

    # --- mouse interaction -------------------------------------------

    def _hit(self, point: QPointF) -> str:
        rect = self.camera_rect()
        if rect.isEmpty():
            return ""
        grip = self._resize_grip_rect()
        if grip.adjusted(-2, -2, 2, 2).contains(point):
            return "resize"
        if rect.adjusted(-2, -2, 2, 2).contains(point):
            return "move"
        return ""

    def _apply_cursor(self, mode: str) -> None:
        if mode == "resize":
            self.setCursor(Qt.SizeFDiagCursor)
        elif mode == "move":
            self.setCursor(
                Qt.ClosedHandCursor
                if self._drag_mode == "move"
                else Qt.OpenHandCursor
            )
        else:
            self.unsetCursor()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            self._interactive
            and self._camera_visible
            and event.button() == Qt.LeftButton
        ):
            mode = self._hit(event.position())
            if mode:
                self._drag_mode = mode
                self._drag_offset = (
                    event.position() - self.camera_rect().topLeft()
                )
                self._apply_cursor(mode)
                self.update()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._interactive or not self._camera_visible:
            super().mouseMoveEvent(event)
            return
        pos = event.position()
        if self._drag_mode == "move":
            rect = self.camera_rect()
            content = self.content_rect()
            target_x = pos.x() - self._drag_offset.x()
            target_y = pos.y() - self._drag_offset.y()
            self._geometry.pos_x, self._geometry.pos_y = position_from_rect(
                content,
                QRectF(target_x, target_y, rect.width(), rect.height()),
            )
            self._snap_to_edges()
            self.update()
            event.accept()
            return
        if self._drag_mode == "resize":
            content = self.content_rect()
            rect = self.camera_rect()
            min_width = content.width() * CAMERA_SCALE_MIN
            max_width = content.width() * CAMERA_SCALE_MAX
            new_width = max(
                min_width, min(max_width, pos.x() - rect.x())
            )
            self._geometry.scale = clamp_camera_scale(
                new_width / content.width()
            )
            # Keep the top-left corner pinned while the grip is dragged.
            new_rect = self.camera_rect()
            self._geometry.pos_x, self._geometry.pos_y = position_from_rect(
                content,
                QRectF(rect.topLeft(), new_rect.size()),
            )
            self.update()
            event.accept()
            return
        self._apply_cursor(self._hit(pos))
        hover = self._hit(pos) != ""
        if hover != self._hover:
            self._hover = hover
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode and event.button() == Qt.LeftButton:
            self._drag_mode = ""
            self._apply_cursor(self._hit(event.position()))
            self._hover = self._hit(event.position()) != ""
            self.update()
            self._emit_geometry()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if (
            self._interactive
            and self._camera_visible
            and event.button() == Qt.LeftButton
            and self.camera_rect().contains(event.position())
        ):
            self.reset_camera()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._interactive or not self._camera_visible:
            event.ignore()
            return
        steps = event.angleDelta().y() / 120.0
        if not steps:
            event.ignore()
            return
        content = self.content_rect()
        old_rect = self.camera_rect()
        center = old_rect.center()
        self._geometry.scale = clamp_camera_scale(
            self._geometry.scale + steps * _WHEEL_STEP
        )
        new_rect = self.camera_rect()
        pinned = QRectF(
            center.x() - new_rect.width() / 2.0,
            center.y() - new_rect.height() / 2.0,
            new_rect.width(),
            new_rect.height(),
        )
        self._geometry.pos_x, self._geometry.pos_y = position_from_rect(
            content, pinned
        )
        self.update()
        self._emit_geometry()
        event.accept()

    def leaveEvent(self, event) -> None:
        if self._hover:
            self._hover = False
            self.update()
        super().leaveEvent(event)

    def _snap_to_edges(self) -> None:
        """Pull the PiP flush to the stage border when close (OBS feel)."""
        content = self.content_rect()
        rect = self.camera_rect()
        if rect.isEmpty():
            return
        pos_x = self._geometry.pos_x
        pos_y = self._geometry.pos_y
        if abs(rect.x() - content.x()) <= _EDGE_SNAP_PX:
            pos_x = 0.0
        elif abs(rect.right() - content.right()) <= _EDGE_SNAP_PX:
            pos_x = 1.0
        if abs(rect.y() - content.y()) <= _EDGE_SNAP_PX:
            pos_y = 0.0
        elif abs(rect.bottom() - content.bottom()) <= _EDGE_SNAP_PX:
            pos_y = 1.0
        self._geometry.pos_x = clamp_camera_position(pos_x)
        self._geometry.pos_y = clamp_camera_position(pos_y)
