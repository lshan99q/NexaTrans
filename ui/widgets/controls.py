# -*- coding: utf-8 -*-
"""
NexaTrans - animated input controls.

``ToggleSwitch`` subclasses ``QCheckBox`` and ``NeonSlider`` subclasses
``QSlider`` on purpose: they keep the exact public API used by the rest of
the application (``isChecked`` / ``setChecked`` / ``toggled`` / ``value`` /
``valueChanged``) while painting a completely different, animated widget.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QSlider

from ui.theme import Motion, Palette, mix, qc, ui_font
from ui.widgets.anim import animate, stop_animation


class ToggleSwitch(QCheckBox):
    """iOS-style animated switch (drop-in replacement for a checkbox)."""

    WIDTH = 46
    HEIGHT = 26
    MARGIN = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._p = 0.0
        self._hover = 0.0
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFont(ui_font(12))
        self.toggled.connect(self._on_toggled)

    def setChecked(self, checked: bool) -> None:      # noqa: N802
        """
        Keep the drawn state in sync with the real state.

        When a window loads its config the checkbox is set while signals are
        blocked (or while the page is still hidden), so ``toggled`` never
        fires - without this the switch would draw the wrong state.
        """
        super().setChecked(checked)
        if self.signalsBlocked() or not self.isVisible():
            stop_animation(self, "pos")
            self._p = 1.0 if checked else 0.0
            self.update()

    # -- animation ---------------------------------------------------------

    def _on_toggled(self, checked: bool) -> None:
        target = 1.0 if checked else 0.0
        if not self.isVisible():
            self._p = target
            self.update()
            return
        animate(self, "pos", self._p, target,
                lambda v: (setattr(self, "_p", float(v)), self.update()),
                duration=200, easing=QEasingCurve.OutBack)

    def enterEvent(self, event):
        animate(self, "hover", self._hover, 1.0,
                lambda v: (setattr(self, "_hover", float(v)), self.update()),
                duration=Motion.FAST)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate(self, "hover", self._hover, 0.0,
                lambda v: (setattr(self, "_hover", float(v)), self.update()),
                duration=Motion.FAST)
        super().leaveEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w, h = self.width(), self.height()
        track = QRectF(0.5, 0.5, w - 1, h - 1)
        radius = track.height() / 2
        p = max(0.0, min(1.0, self._p))
        enabled = self.isEnabled()

        # outer glow when on
        if p > 0.01 and enabled:
            glow_alpha = int(70 * p * (0.55 + 0.45 * self._hover))
            painter.setPen(Qt.NoPen)
            painter.setBrush(qc(Palette.CYAN, glow_alpha))
            painter.drawRoundedRect(track.adjusted(-2, -2, 2, 2),
                                    radius + 2, radius + 2)

        # track
        if not enabled:
            painter.setBrush(qc(Palette.INSET))
            painter.setPen(QPen(qc(Palette.BORDER), 1))
            painter.drawRoundedRect(track, radius, radius)
        else:
            off_fill = mix(Palette.INSET, Palette.HOVER, 0.35 + 0.4 * self._hover)
            on_fill = QLinearGradient(track.topLeft(), track.bottomRight())
            on_fill.setColorAt(0.0, mix(Palette.CYAN, "#FFFFFF", 0.12 * self._hover))
            on_fill.setColorAt(1.0, mix(Palette.INDIGO, "#FFFFFF", 0.08 * self._hover))
            painter.setPen(Qt.NoPen)
            painter.setBrush(off_fill)
            painter.drawRoundedRect(track, radius, radius)
            if p > 0.0:
                painter.save()
                painter.setClipRect(QRectF(0, 0, w * p, h))
                painter.setBrush(on_fill)
                painter.drawRoundedRect(track, radius, radius)
                painter.restore()

            border = mix(Palette.BORDER_HI, Palette.CYAN, p)
            painter.setPen(QPen(border, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(track.adjusted(0.5, 0.5, -0.5, -0.5),
                                    radius, radius)

        # knob
        knob_d = h - self.MARGIN * 2
        travel = w - knob_d - self.MARGIN * 2
        kx = self.MARGIN + travel * p
        knob = QRectF(kx, self.MARGIN, knob_d, knob_d)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 60))
        painter.drawEllipse(knob.adjusted(0, 1.5, 0, 1.5))

        knob_color = QColor("#FFFFFF") if enabled else qc(Palette.TEXT_DIM)
        painter.setBrush(knob_color)
        painter.drawEllipse(knob)


class NeonSlider(QSlider):
    """Slim slider with a gradient fill and a growing hover/press handle."""

    HEIGHT = 26
    GROOVE = 6
    HANDLE = 14
    HANDLE_HOVER = 17

    def __init__(self, minimum: int = 0, maximum: int = 100,
                 value: int = 0, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setRange(minimum, maximum)
        self.setValue(value)
        self.setFixedHeight(self.HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self._hover = 0.0
        self._press = 0.0

    def sizeHint(self) -> QSize:
        return QSize(150, self.HEIGHT)

    def minimumSizeHint(self) -> QSize:
        return QSize(60, self.HEIGHT)

    # -- animation ---------------------------------------------------------

    def enterEvent(self, event):
        animate(self, "hover", self._hover, 1.0,
                lambda v: (setattr(self, "_hover", float(v)), self.update()),
                duration=Motion.FAST)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate(self, "hover", self._hover, 0.0,
                lambda v: (setattr(self, "_hover", float(v)), self.update()),
                duration=Motion.FAST)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        animate(self, "press", self._press, 1.0,
                lambda v: (setattr(self, "_press", float(v)), self.update()),
                duration=90)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        animate(self, "press", self._press, 0.0,
                lambda v: (setattr(self, "_press", float(v)), self.update()),
                duration=160)
        super().mouseReleaseEvent(event)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        span = max(1, self.maximum() - self.minimum())
        ratio = (self.sliderPosition() - self.minimum()) / span
        ratio = max(0.0, min(1.0, ratio))

        pad = self.HANDLE_HOVER / 2 + 1
        cy = self.height() / 2.0
        x0, x1 = pad, self.width() - pad
        if x1 <= x0:
            x1 = x0 + 1

        groove = QRectF(x0, cy - self.GROOVE / 2.0, x1 - x0, self.GROOVE)
        g_radius = self.GROOVE / 2.0

        enabled = self.isEnabled()

        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(Palette.INSET) if enabled else qc(Palette.SURFACE_2))
        painter.drawRoundedRect(groove, g_radius, g_radius)

        hx = x0 + (x1 - x0) * ratio
        if enabled and hx > x0:
            fill = QRectF(x0, groove.top(), hx - x0, self.GROOVE)
            grad = QLinearGradient(fill.topLeft(), fill.topRight())
            grad.setColorAt(0.0, mix(Palette.CYAN, "#FFFFFF", 0.2 * self._hover))
            grad.setColorAt(1.0, mix(Palette.INDIGO, "#FFFFFF", 0.1 * self._hover))
            painter.setBrush(grad)
            painter.drawRoundedRect(fill, g_radius, g_radius)

        d = self.HANDLE + (self.HANDLE_HOVER - self.HANDLE) * max(self._hover,
                                                                  self._press)
        handle = QRectF(hx - d / 2.0, cy - d / 2.0, d, d)

        if enabled and (self._hover > 0.01 or self._press > 0.01):
            painter.setBrush(qc(Palette.CYAN, int(55 * max(self._hover, self._press))))
            painter.drawEllipse(handle.adjusted(-4, -4, 4, 4))

        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawEllipse(handle.adjusted(0, 1, 0, 1))

        painter.setBrush(QColor("#FFFFFF") if enabled else qc(Palette.TEXT_DIM))
        painter.drawEllipse(handle)

        if enabled:
            painter.setPen(QPen(mix(Palette.SKY, "#FFFFFF", 0.4 * self._hover), 1.6))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(handle.adjusted(1.2, 1.2, -1.2, -1.2))
