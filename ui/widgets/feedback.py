# -*- coding: utf-8 -*-
"""
NexaTrans - feedback & form-row widgets.

Spinner, StatusPill, StatChip, Toast (transient in-window notification),
ToggleRow and SliderRow.
"""

from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve, QPoint, QRectF, Qt, QTimer,
)
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout,
    QWidget,
)

from ui.theme import (
    Motion, Palette, Space, mix, qc, rounded_path, ui_font,
)
from ui.widgets.anim import animate
from ui.widgets.controls import NeonSlider, ToggleSwitch

# --------------------------------------------------------------------------
# Spinner
# --------------------------------------------------------------------------


class Spinner(QWidget):
    """Rotating gradient arc - used while models / requests are loading."""

    def __init__(self, size: int = 22, parent=None):
        super().__init__(parent)
        self._size = size
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._angle = (self._angle + 8) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        r = self._size / 2.0
        rect = QRectF(1, 1, self._size - 2, self._size - 2)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(qc(Palette.BORDER_HI), 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 0, 360 * 16)

        painter.setPen(QPen(qc(Palette.CYAN), 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, int(-self._angle * 16), int(100 * 16))
        painter.setPen(QPen(qc(Palette.INDIGO), 2.2, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, int((-self._angle + 110) * 16), int(60 * 16))


# --------------------------------------------------------------------------
# Status pill
# --------------------------------------------------------------------------

_STATES = {
    "idle": (Palette.TEXT_DIM, "\u25cf"),
    "ready": (Palette.TEXT_MUTED, "\u25cf"),
    "running": (Palette.SUCCESS, "\u25cf"),
    "busy": (Palette.WARN, "\u25cf"),
    "ok": (Palette.SUCCESS, "\u25cf"),
    "error": (Palette.DANGER, "\u25cf"),
}


class StatusPill(QWidget):
    """Rounded pill with a pulsing status dot and a short message."""

    def __init__(self, text: str = "\u5c31\u7eea", state: str = "idle",
                 parent=None):
        super().__init__(parent)
        self._text = text
        self._state = state
        self._pulse = 0.0
        self._pulse_dir = 1
        self.setFont(ui_font(11, QFont.DemiBold))
        self._timer = QTimer(self)
        self._timer.setInterval(28)
        self._timer.timeout.connect(self._tick)
        self._recalc()

    # -- api ---------------------------------------------------------------

    def set_state(self, text: str, state: str = "idle") -> None:
        self._state = state
        self._text = text
        self._recalc()
        if state in ("running", "busy"):
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self._pulse = 0.0
        self.update()

    def _recalc(self) -> None:
        fm = self.fontMetrics()
        width = fm.horizontalAdvance(self._text) + 40
        self.setFixedSize(width, 26)
        self.updateGeometry()

    def _tick(self) -> None:
        self._pulse += 0.05 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse = 1.0
            self._pulse_dir = -1
        elif self._pulse <= 0.0:
            self._pulse = 0.0
            self._pulse_dir = 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        color_hex, _ = _STATES.get(self._state, _STATES["idle"])
        color = qc(color_hex)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        painter.setPen(QPen(qc(color_hex, 70), 1))
        painter.setBrush(qc(Palette.INSET, 160))
        painter.drawRoundedRect(rect, radius, radius)

        cx = rect.left() + 14
        cy = rect.center().y()

        if self._timer.isActive():
            halo = 4.0 + 3.0 * self._pulse
            grad = QRadialGradient(cx, cy, halo + 2)
            grad.setColorAt(0.0, qc(color_hex, int(120 * (1 - self._pulse))))
            grad.setColorAt(1.0, qc(color_hex, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(grad)
            painter.drawEllipse(QRectF(cx - halo - 2, cy - halo - 2,
                                       (halo + 2) * 2, (halo + 2) * 2))

        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(cx - 3, cy - 3, 6, 6))

        painter.setPen(mix(color, "#FFFFFF", 0.55))
        painter.setFont(self.font())
        painter.drawText(QRectF(rect.left() + 24, rect.top(), rect.width() - 30,
                                rect.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, self._text)


# --------------------------------------------------------------------------
# Stat chip
# --------------------------------------------------------------------------


class StatChip(QWidget):
    """Small metric tile: animated value + caption."""

    def __init__(self, caption: str, value: str = "0",
                 accent: str = Palette.SKY, parent=None):
        super().__init__(parent)
        self._caption = caption
        self._value = value
        self._display = 0.0
        self._accent = accent
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value: int | float, animate_change: bool = True) -> None:
        try:
            target = float(value)
        except (TypeError, ValueError):
            return
        if not animate_change or not self.isVisible():
            self._display = target
            self._value = self._format(target)
            self.update()
            return
        start = self._display
        self._value = self._format(target)
        animate(self, "value", start, target, self._on_value,
                duration=420, easing=QEasingCurve.OutCubic)

    def _on_value(self, v):
        self._display = float(v)
        self._value = self._format(self._display)
        self.update()

    @staticmethod
    def _format(v: float) -> str:
        return str(int(round(v)))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, 11)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, qc(Palette.SURFACE))
        grad.setColorAt(1.0, qc(Palette.SURFACE_2))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawPath(path)

        painter.save()
        painter.setClipPath(path)
        painter.setBrush(qc(self._accent, 16))
        painter.drawPath(path)
        glow = QRadialGradient(rect.left() + rect.width() * 0.2,
                               rect.top(), rect.width() * 0.8)
        glow.setColorAt(0.0, qc(self._accent, 46))
        glow.setColorAt(1.0, qc(self._accent, 0))
        painter.setBrush(glow)
        painter.drawPath(path)
        painter.restore()

        painter.setPen(QPen(qc(Palette.BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(rounded_path(rect.adjusted(0.5, 0.5, -0.5, -0.5), 10))

        painter.setPen(qc(self._accent))
        painter.setFont(ui_font(19, QFont.Bold))
        painter.drawText(QRectF(rect.left() + 12, rect.top() + 7,
                                rect.width() - 20, 24),
                         Qt.AlignLeft | Qt.AlignVCenter, self._value)

        painter.setPen(qc(Palette.TEXT_DIM))
        painter.setFont(ui_font(10, QFont.Medium))
        painter.drawText(QRectF(rect.left() + 12, rect.bottom() - 22,
                                rect.width() - 20, 18),
                         Qt.AlignLeft | Qt.AlignVCenter, self._caption)


# --------------------------------------------------------------------------
# Toast
# --------------------------------------------------------------------------

_TOAST_TONES = {
    "info": Palette.SKY,
    "success": Palette.SUCCESS,
    "warn": Palette.WARN,
    "error": Palette.DANGER,
}


class Toast(QWidget):
    """Transient notification that slides up from the bottom of the window."""

    _active: "Toast | None" = None

    def __init__(self, parent: QWidget, text: str, tone: str = "info",
                 duration: int = 2400, offset_bottom: int = 14):
        super().__init__(parent)
        self._text = text
        self._tone = tone
        self._duration = duration
        self._offset_bottom = offset_bottom
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFont(ui_font(12, QFont.DemiBold))

        fm = self.fontMetrics()
        width = min(parent.width() - 40, fm.horizontalAdvance(text) + 58)
        width = max(width, 150)
        self.setFixedSize(width, 40)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def push(cls, parent: QWidget, text: str, tone: str = "info",
             duration: int = 2400, offset_bottom: int = 14) -> "Toast":
        previous = Toast._active
        if previous is not None:
            try:
                previous.close()
            except RuntimeError:
                pass
        toast = cls(parent, text, tone, duration, offset_bottom)
        Toast._active = toast
        toast.start()
        return toast

    def start(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.width()) // 2
        end_y = parent.height() - self.height() - self._offset_bottom
        self._end_pos = QPoint(x, end_y)
        self.move(x, end_y + 22)
        self.show()
        self.raise_()

        animate(self, "slide", float(end_y + 22), float(end_y),
                lambda v: self.move(self._end_pos.x(), int(v)),
                duration=Motion.SLOW, easing=QEasingCurve.OutCubic)
        animate(self, "fade", 0.0, 1.0,
                lambda v: self._effect.setOpacity(float(v)),
                duration=Motion.BASE, easing=QEasingCurve.OutCubic)
        self._hide_timer.start(self._duration)

    def dismiss(self) -> None:
        if not self.isVisible():
            return
        self._hide_timer.stop()
        animate(self, "fade", self._effect.opacity(), 0.0,
                lambda v: self._effect.setOpacity(float(v)),
                duration=Motion.BASE, easing=QEasingCurve.InCubic,
                finished=self.close)
        current_y = self.y()
        animate(self, "slide_out", float(current_y), float(current_y + 14),
                lambda v: self.move(self.x(), int(v)),
                duration=Motion.BASE, easing=QEasingCurve.InCubic)

    def closeEvent(self, event):
        if Toast._active is self:
            Toast._active = None
        super().closeEvent(event)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        accent = qc(_TOAST_TONES.get(self._tone, Palette.SKY))

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, 12)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, qc("#141C2C"))
        grad.setColorAt(1.0, qc("#0D1421"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawPath(path)

        painter.save()
        painter.setClipPath(path)
        painter.setBrush(qc(accent, 26))
        painter.drawRect(QRectF(rect.left(), rect.top(), 3.5, rect.height()))
        painter.setBrush(qc(accent, 12))
        painter.drawPath(path)
        painter.restore()

        painter.setPen(QPen(qc(accent, 130), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(rounded_path(rect.adjusted(0.5, 0.5, -0.5, -0.5), 11))

        painter.setPen(accent)
        painter.setFont(ui_font(13))
        painter.drawText(QRectF(rect.left(), rect.top(), 32, rect.height()),
                         Qt.AlignCenter, "\u25cf")

        painter.setPen(qc(Palette.TEXT))
        painter.setFont(self.font())
        painter.drawText(QRectF(rect.left() + 34, rect.top(),
                                rect.width() - 44, rect.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, self._text)


# --------------------------------------------------------------------------
# Form rows
# --------------------------------------------------------------------------


class ToggleRow(QWidget):
    """Label (+ optional hint) on the left, animated switch on the right."""

    def __init__(self, title: str, hint: str = "", checked: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setMinimumHeight(42)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.MD)

        column = QVBoxLayout()
        column.setSpacing(1)
        label = QLabel(title)
        label.setFont(ui_font(12, QFont.Medium))
        label.setStyleSheet(f"color: {Palette.TEXT}; background: transparent;")
        column.addWidget(label)
        if hint:
            sub = QLabel(hint)
            sub.setFont(ui_font(10))
            sub.setStyleSheet(
                f"color: {Palette.TEXT_DIM}; background: transparent;")
            column.addWidget(sub)
        layout.addLayout(column, 1)

        self.toggle = ToggleSwitch()
        self.toggle.setChecked(checked)
        layout.addWidget(self.toggle, 0, Qt.AlignVCenter)

    def isChecked(self) -> bool:
        return self.toggle.isChecked()

    def setChecked(self, value: bool) -> None:
        self.toggle.setChecked(value)


class SliderRow(QWidget):
    """Title + slider + live value chip."""

    def __init__(self, title: str, minimum: int, maximum: int, value: int,
                 fmt: str = "{:.2f}", scale: float = 100.0, parent=None):
        super().__init__(parent)
        self._fmt = fmt
        self._scale = scale
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        head = QHBoxLayout()
        head.setSpacing(Space.SM)
        label = QLabel(title)
        label.setFont(ui_font(11, QFont.Medium))
        label.setStyleSheet(f"color: {Palette.TEXT_MUTED}; background: transparent;")
        head.addWidget(label, 1)

        self.value_label = QLabel(fmt.format(value / scale))
        self.value_label.setFont(ui_font(11, QFont.DemiBold, mono=True))
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setFixedHeight(20)
        self.value_label.setMinimumWidth(52)
        self.value_label.setStyleSheet(
            f"color: {Palette.CYAN}; background: {Palette.INSET};"
            f" border: 1px solid {Palette.BORDER}; border-radius: 6px;"
            f" padding: 1px 6px;")
        head.addWidget(self.value_label, 0, Qt.AlignVCenter)
        layout.addLayout(head)

        self.slider = NeonSlider(minimum, maximum, value)
        layout.addWidget(self.slider)

    def set_text(self, text: str) -> None:
        self.value_label.setText(text)
