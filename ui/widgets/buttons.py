# -*- coding: utf-8 -*-
"""
NexaTrans - animated button widgets.

* ``GlowButton``  - gradient pill button with hover lift, animated glow,
                    press feedback, click ripple and a built-in busy spinner.
* ``IconButton``  - small round glyph button used by the custom title bar.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPen, QRadialGradient,
)
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QPushButton, QSizePolicy

from ui.theme import Motion, Palette, Radius, mix, qc, rounded_path, ui_font
from ui.widgets.anim import animate

# --------------------------------------------------------------------------
# Variant definitions
# --------------------------------------------------------------------------
# grad    : (start, end) colors of the background gradient (or None for flat)
# fill    : flat fill color when grad is None
# fg      : text color
# border  : border color (None = automatic)
# glow    : color of the outer glow

VARIANTS: dict[str, dict] = {
    "primary": dict(grad=(Palette.CYAN, Palette.INDIGO), fg=Palette.TEXT_ON_ACCENT,
                    border=(255, 255, 255, 60), glow=Palette.CYAN, glow_alpha=120),
    "accent": dict(grad=(Palette.SKY, Palette.VIOLET), fg="#FFFFFF",
                   border=(255, 255, 255, 55), glow=Palette.VIOLET, glow_alpha=110),
    "danger": dict(grad=(Palette.DANGER, Palette.DANGER_2), fg="#FFFFFF",
                   border=(255, 255, 255, 55), glow=Palette.DANGER_2, glow_alpha=120),
    "success": dict(grad=(Palette.SUCCESS, "#0EA5A0"), fg="#04140E",
                    border=(255, 255, 255, 50), glow=Palette.SUCCESS, glow_alpha=110),
    "ghost": dict(grad=None, fill=Palette.SURFACE_2, fg=Palette.TEXT_MUTED,
                  border=Palette.BORDER_HI, glow=None, glow_alpha=0),
    "subtle": dict(grad=None, fill=Palette.HOVER, fg=Palette.SKY,
                   border=None, glow=None, glow_alpha=0),
}


class GlowButton(QPushButton):
    """A modern, fully custom-painted action button."""

    def __init__(self, text: str = "", variant: str = "primary",
                 radius: int = Radius.BUTTON, font_size: int = 14,
                 bold: bool = True, parent=None):
        super().__init__(text, parent)
        self._variant = variant
        self._radius = radius
        self._font_size = font_size
        self._bold = bold
        self._hover = 0.0
        self._press = 0.0
        self._ripple = 0.0
        self._ripple_pos = QPointF(0, 0)
        self._busy = False
        self._busy_angle = 0

        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(font_size + 22)
        self.setFont(ui_font(font_size, QFont.DemiBold if bold else QFont.Normal))

        self._glow = QGraphicsDropShadowEffect(self)
        spec = VARIANTS.get(variant, VARIANTS["primary"])
        self._glow.setOffset(0, 4)
        self._glow.setBlurRadius(18)
        self._glow.setColor(qc(spec.get("glow") or Palette.CYAN,
                               spec.get("glow_alpha", 90)))
        self.setGraphicsEffect(self._glow)

        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(16)
        self._busy_timer.timeout.connect(self._tick_busy)

    # -- api ---------------------------------------------------------------

    def set_variant(self, variant: str) -> None:
        if variant == self._variant:
            return
        self._variant = variant
        spec = VARIANTS.get(variant, VARIANTS["primary"])
        self._glow.setColor(qc(spec.get("glow") or Palette.CYAN,
                               spec.get("glow_alpha", 90)))
        self.update()

    def variant(self) -> str:
        return self._variant

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        if self._busy:
            self._busy_timer.start()
        else:
            self._busy_timer.stop()
        self.update()

    def is_busy(self) -> bool:
        return self._busy

    def set_radius(self, radius: int) -> None:
        self._radius = radius
        self.update()

    # -- animation ---------------------------------------------------------

    def _tick_busy(self) -> None:
        self._busy_angle = (self._busy_angle + 9) % 360
        self.update()

    def enterEvent(self, event):
        self._animate_glow(1.0, 26, 46)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_glow(0.0, 18, 24)
        super().leaveEvent(event)

    def _animate_glow(self, hover: float, blur: int, alpha_scale: int) -> None:
        animate(self, "hover", self._hover, hover,
                lambda v: (setattr(self, "_hover", float(v)), self.update()),
                duration=Motion.FAST, easing=QEasingCurve.OutCubic)
        if self._variant not in ("ghost", "subtle"):
            spec = VARIANTS.get(self._variant, VARIANTS["primary"])
            base = spec.get("glow_alpha", 90)
            animate(self, "glow", self._glow.blurRadius(), float(blur),
                    lambda v: self._glow.setBlurRadius(float(v)),
                    duration=Motion.BASE, easing=QEasingCurve.OutCubic)
            animate(self, "glow_alpha",
                    self._glow.color().alpha(),
                    float(min(255, base + alpha_scale * hover)),
                    lambda v: self._glow.setColor(
                        qc(spec.get("glow") or Palette.CYAN, int(v))),
                    duration=Motion.BASE, easing=QEasingCurve.OutCubic)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._ripple_pos = event.position()
            animate(self, "press", self._press, 1.0,
                    lambda v: (setattr(self, "_press", float(v)), self.update()),
                    duration=90, easing=QEasingCurve.OutCubic)
            animate(self, "ripple", 0.0, 1.0,
                    lambda v: (setattr(self, "_ripple", float(v)), self.update()),
                    duration=420, easing=QEasingCurve.OutCubic,
                    finished=lambda: setattr(self, "_ripple", 0.0))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        animate(self, "press", self._press, 0.0,
                lambda v: (setattr(self, "_press", float(v)), self.update()),
                duration=140, easing=QEasingCurve.OutCubic)
        super().mouseReleaseEvent(event)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        spec = VARIANTS.get(self._variant, VARIANTS["primary"])
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        enabled = self.isEnabled()
        inset = 1.4 * self._press
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        radius = min(float(self._radius), rect.height() / 2.0)
        path = rounded_path(rect, radius)

        # --- background ---------------------------------------------------
        if not enabled:
            painter.setPen(Qt.NoPen)
            painter.setBrush(qc(Palette.INSET))
            painter.drawPath(path)
        elif spec.get("grad"):
            start, end = spec["grad"]
            start = mix(start, "#FFFFFF", 0.16 * self._hover)
            end = mix(end, "#FFFFFF", 0.10 * self._hover)
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, start)
            grad.setColorAt(1.0, end)
            painter.setPen(Qt.NoPen)
            painter.setBrush(grad)
            painter.drawPath(path)
        else:
            fill = qc(spec.get("fill", Palette.SURFACE))
            fill = mix(fill, Palette.SKY, 0.16 * self._hover)
            painter.setPen(Qt.NoPen)
            painter.setBrush(fill)
            painter.drawPath(path)

        # --- clipping layer: sheen + ripple -------------------------------
        painter.save()
        painter.setClipPath(path)

        if enabled:
            sheen = QLinearGradient(rect.topLeft(),
                                    QPointF(rect.left(), rect.center().y()))
            sheen.setColorAt(0.0, QColor(255, 255, 255, 42 if spec.get("grad") else 16))
            sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(sheen)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)

        if self._ripple > 0.0:
            radius_px = math.hypot(rect.width(), rect.height()) * self._ripple
            rgrad = QRadialGradient(self._ripple_pos, max(radius_px, 1.0))
            alpha = int(90 * (1.0 - self._ripple))
            rgrad.setColorAt(0.0, QColor(255, 255, 255, alpha))
            rgrad.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(rgrad)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)

        if not enabled:
            painter.fillPath(path, qc("#000000", 40))

        painter.restore()

        # --- border -------------------------------------------------------
        if not enabled:
            border = qc(Palette.BORDER)
        elif spec.get("border") is None:
            border = qc(Palette.BORDER_HI) if spec.get("grad") is None else None
        elif isinstance(spec["border"], tuple):
            border = QColor(*spec["border"])
            border = mix(border, "#FFFFFF", 0.3 * self._hover)
        else:
            border = mix(spec["border"], Palette.SKY, 0.5 * self._hover)
        if border is not None:
            painter.setPen(QPen(border, 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(rounded_path(rect.adjusted(0.5, 0.5, -0.5, -0.5),
                                          radius))

        # --- content ------------------------------------------------------
        fg = qc(spec.get("fg", Palette.TEXT)) if enabled else qc(Palette.TEXT_DIM)
        self._draw_content(painter, rect, fg)

    def _draw_content(self, painter: QPainter, rect: QRectF, fg: QColor) -> None:
        text = self.text()
        text_rect = QRectF(rect)
        if self._busy:
            text_rect = text_rect.adjusted(14, 0, 14, 0)

        if text:
            painter.setPen(fg)
            painter.setFont(self.font())
            painter.drawText(text_rect, Qt.AlignCenter, text)

        if self._busy:
            self._draw_spinner(painter, QPointF(rect.center().x() -
                                                text_rect.width() / 2 + 4,
                                                rect.center().y()), fg)

    def _draw_spinner(self, painter: QPainter, center: QPointF, fg: QColor) -> None:
        r = 6.0
        painter.save()
        painter.setBrush(Qt.NoBrush)
        track = QColor(fg)
        track.setAlpha(50)
        painter.setPen(QPen(track, 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(center.x() - r, center.y() - r, r * 2, r * 2),
                        0, 360 * 16)
        painter.setPen(QPen(fg, 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(center.x() - r, center.y() - r, r * 2, r * 2),
                        int(-self._busy_angle * 16), int(110 * 16))
        painter.restore()


class IconButton(QPushButton):
    """Compact round glyph button (window controls, back, gear)."""

    def __init__(self, glyph: str = "\u2715", size: int = 28,
                 tone: str = "muted", parent=None):
        super().__init__(glyph, parent)
        self._glyph = glyph
        self._tone = tone
        self._hover = 0.0
        self._hover_color = Palette.HOVER
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFont(ui_font(int(size * 0.46)))
        self.setToolTip("")

    def set_hover_color(self, color: str) -> None:
        self._hover_color = color

    def set_tone(self, tone: str) -> None:
        self._tone = tone
        self.update()

    def set_glyph(self, glyph: str) -> None:
        self._glyph = glyph
        self.update()

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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        if self._hover > 0.01 and self.isEnabled():
            painter.setPen(Qt.NoPen)
            painter.setBrush(mix(Palette.SURFACE, self._hover_color, self._hover))
            painter.drawEllipse(rect)

        if self._tone == "danger" and self._hover > 0.01:
            color = mix(qc(Palette.TEXT_MUTED), "#FFFFFF", self._hover)
        elif self._tone == "danger":
            color = qc(Palette.TEXT_MUTED)
        else:
            color = mix(qc(Palette.TEXT_MUTED), qc(Palette.TEXT), self._hover)

        painter.setPen(color)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignCenter, self._glyph)
