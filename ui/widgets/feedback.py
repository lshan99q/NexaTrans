# -*- coding: utf-8 -*-
"""
NexaTrans - Fluent (Windows 11) feedback widgets.

``InfoBar``     - Win11 InfoBar notification (slides down from the top)
``ProgressRing``- WinUI indeterminate progress ring
``StatusBadge`` - small pill with a state dot
``MetricTile``  - caption + animated value tile used for live statistics
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect, QSizePolicy, QWidget,
)

from ui.theme import (
    Motion, Radius, darken, mix, qc, rounded_path, theme, ui_font,
)
from ui.widgets.anim import animate


class ProgressRing(QWidget):
    """WinUI progress ring: accent arc rotating on a faint track."""

    def __init__(self, size: int = 20, parent=None):
        super().__init__(parent)
        self._size = size
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._angle = (self._angle + 6) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        inset = 2.0
        box = QRectF(inset, inset, self._size - inset * 2, self._size - inset * 2)

        painter.setBrush(Qt.NoBrush)
        track = qc(t.text)
        track.setAlpha(38)
        painter.setPen(QPen(track, 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawEllipse(box)

        painter.setPen(QPen(qc(t.accent), 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(box, int(-self._angle * 16), int(90 * 16))


# --------------------------------------------------------------------------
# Status badge
# --------------------------------------------------------------------------

_BADGE_COLORS = {
    "idle": ("text_tertiary", 1.0),
    "ready": ("text_tertiary", 1.0),
    "running": ("success", 0.9),
    "busy": ("caution", 0.9),
    "ok": ("success", 1.0),
    "error": ("critical", 1.0),
}


class StatusBadge(QWidget):
    """Small pill: coloured state dot + label (Win11 InfoBadge feel)."""

    def __init__(self, text: str = "", state: str = "idle", parent=None):
        super().__init__(parent)
        self._text = text
        self._state = state
        self._pulse = 0.0
        self._dir = 1
        self.setFont(ui_font(12))
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._recalc()

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
        self.setFixedSize(fm.horizontalAdvance(self._text) + 34, 26)
        self.updateGeometry()

    def _tick(self) -> None:
        self._pulse += 0.05 * self._dir
        if self._pulse >= 1.0:
            self._pulse, self._dir = 1.0, -1
        elif self._pulse <= 0.0:
            self._pulse, self._dir = 0.0, 1
        self.update()

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        token, _ = _BADGE_COLORS.get(self._state, _BADGE_COLORS["idle"])
        color = qc(getattr(t, token))

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        painter.setPen(QPen(qc(t.card_stroke), 1.0))
        painter.setBrush(qc(t.layer))
        painter.drawRoundedRect(rect, radius, radius)

        cx, cy = rect.left() + 13, rect.center().y()
        if self._timer.isActive():
            halo = 4.0 + 2.5 * self._pulse
            glow = QColor(color)
            glow.setAlpha(int(70 * (1 - self._pulse)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QRectF(cx - halo, cy - halo, halo * 2, halo * 2))
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(cx - 3, cy - 3, 6, 6))

        painter.setPen(qc(t.text))
        painter.setFont(self.font())
        painter.drawText(QRectF(rect.left() + 23, rect.top(),
                                rect.width() - 28, rect.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, self._text)


# --------------------------------------------------------------------------
# Metric tile
# --------------------------------------------------------------------------


class MetricTile(QWidget):
    """Value + caption tile with an animated value change."""

    def __init__(self, caption: str, value: str = "0", parent=None):
        super().__init__(parent)
        self._caption = caption
        self._display = 0.0
        self._value = value
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value, animate_change: bool = True) -> None:
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
        animate(self, "value", start, target, self._on_value,
                duration=Motion.SLOW, easing=QEasingCurve.OutCubic)

    def _on_value(self, v):
        self._display = float(v)
        self._value = self._format(self._display)
        self.update()

    @staticmethod
    def _format(v: float) -> str:
        return str(int(round(v)))

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(t.layer))
        painter.drawPath(rounded_path(rect, Radius.CARD))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(qc(t.card_stroke), 1.0))
        painter.drawPath(rounded_path(rect.adjusted(0.5, 0.5, -0.5, -0.5),
                                      Radius.CARD - 0.5))

        painter.setPen(qc(t.text))
        painter.setFont(ui_font(20, QFont.DemiBold, display=True))
        painter.drawText(QRectF(rect.left() + 14, rect.top() + 8,
                                rect.width() - 22, 26),
                         Qt.AlignLeft | Qt.AlignVCenter, self._value)

        painter.setPen(qc(t.text_tertiary))
        painter.setFont(ui_font(12))
        painter.drawText(QRectF(rect.left() + 14, rect.bottom() - 24,
                                rect.width() - 22, 18),
                         Qt.AlignLeft | Qt.AlignVCenter, self._caption)


# --------------------------------------------------------------------------
# InfoBar (Win11 notification)
# --------------------------------------------------------------------------

_INFO_TONES = {
    "info": "accent",
    "success": "success",
    "warn": "caution",
    "error": "critical",
}
_INFO_GLYPHS = {
    "info": "i",
    "success": "\u2713",
    "warn": "!",
    "error": "\u2715",
}


class InfoBar(QWidget):
    """
    WinUI InfoBar: full-width card under the title bar with a severity icon.
    Slides down on show and slides away after ``duration``.
    """

    _active: "InfoBar | None" = None
    TOP_MARGIN = 38        # below the 32px Win11 caption bar

    def __init__(self, parent: QWidget, text: str, tone: str = "info",
                 duration: int = 2600):
        super().__init__(parent)
        self._text = text
        self._tone = tone
        self._duration = duration
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFont(ui_font(13))

        width = max(180, parent.width() - 32)
        self.setFixedSize(width, 44)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)

    @classmethod
    def push(cls, parent: QWidget, text: str, tone: str = "info",
             duration: int = 2600) -> "InfoBar":
        previous = InfoBar._active
        if previous is not None:
            try:
                previous.close()
            except RuntimeError:
                pass
        bar = cls(parent, text, tone, duration)
        InfoBar._active = bar
        bar.start()
        return bar

    def start(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.width()) // 2
        self._end_y = self.TOP_MARGIN
        self.move(x, self._end_y - 18)
        self.show()
        self.raise_()

        animate(self, "slide", float(self._end_y - 18), float(self._end_y),
                lambda v: self.move(x, int(v)),
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
                duration=Motion.FAST, easing=QEasingCurve.InCubic,
                finished=self.close)
        animate(self, "slide_out", float(self.y()), float(self.y() - 12),
                lambda v: self.move(self.x(), int(v)),
                duration=Motion.FAST, easing=QEasingCurve.InCubic)

    def closeEvent(self, event):
        if InfoBar._active is self:
            InfoBar._active = None
        super().closeEvent(event)

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        accent = qc(getattr(t, _INFO_TONES.get(self._tone, "accent")))

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(t.flyout))
        painter.drawPath(rounded_path(rect, Radius.CARD))

        # severity icon
        icon_box = QRectF(rect.left() + 12, rect.center().y() - 9, 18, 18)
        painter.setBrush(accent)
        painter.drawEllipse(icon_box)
        painter.setPen(qc(t.text_on_accent) if self._tone in ("success",)
                       else QColor(255, 255, 255))
        painter.setFont(ui_font(11, QFont.Bold))
        painter.drawText(icon_box, Qt.AlignCenter,
                         _INFO_GLYPHS.get(self._tone, "i"))

        painter.setPen(qc(t.text))
        painter.setFont(self.font())
        painter.drawText(QRectF(rect.left() + 40, rect.top(),
                                rect.width() - 52, rect.height()),
                         Qt.AlignVCenter | Qt.AlignLeft, self._text)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(qc(t.card_stroke), 1.0))
        painter.drawPath(rounded_path(rect.adjusted(0.5, 0.5, -0.5, -0.5),
                                      Radius.CARD - 0.5))
