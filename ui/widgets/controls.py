# -*- coding: utf-8 -*-
"""
NexaTrans - Fluent (Windows 11) input controls.

``ToggleSwitch`` and ``FluentSlider`` subclass ``QCheckBox`` / ``QSlider`` so
the rest of the application keeps using the plain Qt API (``isChecked``,
``setChecked``, ``toggled``, ``value``, ``valueChanged``).

Both reproduce the WinUI 3 visuals:

* toggle - 40x20 pill, grey knob when off, accent fill + contrasting knob when
  on, knob tint/scale feedback on hover and press
* slider - 4px rail, accent fill to the left of the handle, **no visible
  handle at rest**, a 20px circle on hover and a 12px accent dot while dragging
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QSlider

from ui.theme import Motion, mix, qc, scale_alpha, theme, ui_font
from ui.widgets.anim import animate, stop_animation


class ToggleSwitch(QCheckBox):
    """WinUI 3 style toggle switch (drop-in replacement for a checkbox)."""

    #: marks this control as row-toggleable for SettingsRow
    toggleable = True

    WIDTH = 40
    HEIGHT = 20
    KNOB = 12
    INSET = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._p = 0.0            # 0 = off, 1 = on
        self._hover = 0.0
        self._press = 0.0
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFont(ui_font(14))
        self.toggled.connect(self._on_toggled)

    # -- state -------------------------------------------------------------

    def setChecked(self, checked: bool) -> None:      # noqa: N802
        """
        Keep the drawn state in sync when the value is set programmatically
        (config load blocks signals, so ``toggled`` never fires).
        """
        super().setChecked(checked)
        if self.signalsBlocked() or not self.isVisible():
            stop_animation(self, "pos")
            self._p = 1.0 if checked else 0.0
            self.update()

    def _on_toggled(self, checked: bool) -> None:
        target = 1.0 if checked else 0.0
        if not self.isVisible():
            self._p = target
            self.update()
            return
        animate(self, "pos", self._p, target,
                lambda v: (setattr(self, "_p", float(v)), self.update()),
                duration=Motion.BASE, easing=QEasingCurve.OutCubic)

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
                duration=Motion.FAST)
        super().mouseReleaseEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(self.WIDTH, self.HEIGHT)

    def hitButton(self, pos) -> bool:          # noqa: N802
        """
        The whole pill is clickable.

        ``QCheckBox.hitButton()`` only accepts the rect of the style's checkbox
        *indicator* - for this custom-painted switch that is roughly the left
        third of the widget, so clicking the right half silently did nothing.
        """
        return self.rect().contains(pos)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w, h = self.width(), self.height()
        radius = h / 2.0
        rail = QRectF(0.5, 0.5, w - 1, h - 1)
        p = max(0.0, min(1.0, self._p))
        enabled = self.isEnabled()

        # --- rail ---------------------------------------------------------
        if not enabled:
            painter.setPen(QPen(qc(t.control_stroke), 1.0))
            painter.setBrush(scale_alpha(t.control_disabled, 0.8))
            painter.drawRoundedRect(rail, radius, radius)
        elif p <= 0.01:
            # off: transparent with a strong stroke
            stroke = mix(t.control_stroke_strong, t.text_tertiary,
                         0.5 + 0.4 * self._hover)
            painter.setPen(QPen(qc(stroke), 1.0))
            painter.setBrush(QColor(0, 0, 0, 0))
            painter.drawRoundedRect(rail, radius, radius)
        else:
            fill = mix(t.control_stroke_strong, t.accent, p)
            if self._hover > 0.01:
                fill = mix(fill, t.accent_hover if p > 0.99 else t.accent,
                           self._hover)
            if self._press > 0.01:
                fill = mix(fill, t.accent_press, 0.6 * self._press)
            painter.setPen(Qt.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(rail, radius, radius)

        # --- knob ---------------------------------------------------------
        knob_d = self.KNOB
        knob_d -= 1.5 * self._press
        travel = w - self.KNOB - self.INSET * 2
        kx = self.INSET + travel * p + (self.KNOB - knob_d) / 2.0
        ky = (h - knob_d) / 2.0
        knob = QRectF(kx, ky, knob_d, knob_d)

        if not enabled:
            knob_color = qc(t.text_disabled)
        elif p > 0.5:
            knob_color = mix(t.text_on_accent, t.text_secondary,
                             0.25 * (1.0 - p))
        else:
            # off: grey knob that darkens on hover
            knob_color = mix(t.text_secondary, t.text, 0.25 * self._hover)
            knob_color = mix(knob_color, t.text, 0.25 * self._press)
        painter.setPen(Qt.NoPen)
        painter.setBrush(knob_color)
        painter.drawEllipse(knob)


class FluentSlider(QSlider):
    """WinUI 3 style slider."""

    HEIGHT = 32
    RAIL = 4
    THUMB = 20
    DOT = 12

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
        return QSize(160, self.HEIGHT)

    def minimumSizeHint(self) -> QSize:
        return QSize(64, self.HEIGHT)

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
                duration=Motion.FAST)
        super().mouseReleaseEvent(event)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        enabled = self.isEnabled()

        span = max(1, self.maximum() - self.minimum())
        ratio = (self.sliderPosition() - self.minimum()) / span
        ratio = max(0.0, min(1.0, ratio))

        pad = self.THUMB / 2.0 + 1
        cy = self.height() / 2.0
        x0, x1 = pad, max(pad + 1.0, self.width() - pad)
        rail_h = self.RAIL
        rail = QRectF(x0, cy - rail_h / 2.0, x1 - x0, rail_h)
        r = rail_h / 2.0

        # rail background
        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(t.control_disabled if not enabled else t.track))
        painter.drawRoundedRect(rail, r, r)

        hx = x0 + (x1 - x0) * ratio

        # accent fill
        if enabled and hx > x0:
            fill = QRectF(x0, rail.top(), hx - x0, rail_h)
            color = qc(t.accent)
            if self._hover > 0.01:
                color = mix(color, t.accent_hover, self._hover)
            if self._press > 0.01:
                color = mix(color, t.accent_press, self._press)
            painter.setBrush(color)
            painter.drawRoundedRect(fill, r, r)

        # thumb appears on hover, and shows an inner dot while dragging
        level = max(self._hover, self._press)
        if enabled and level > 0.01:
            d = self.THUMB * level
            thumb = QRectF(hx - d / 2.0, cy - d / 2.0, d, d)
            if self._press > 0.01:
                painter.setPen(Qt.NoPen)
                painter.setBrush(qc(t.accent))
                painter.drawEllipse(thumb.adjusted(-6, -6, 6, 6))
                painter.setBrush(qc(t.text_on_accent))
                painter.drawEllipse(thumb)
            else:
                painter.setPen(QPen(qc(t.control_stroke_strong), 1.0))
                painter.setBrush(qc(t.control_hover))
                painter.drawEllipse(thumb)

        if self.hasFocus():
            outer = QColor(255, 255, 255) if t.is_dark else QColor(0, 0, 0)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(outer, 1.5))
            painter.drawRoundedRect(QRectF(x0 - 3, cy - 9, x1 - x0 + 6, 18),
                                    4, 4)
