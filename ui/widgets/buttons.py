# -*- coding: utf-8 -*-
"""
NexaTrans - Fluent (Windows 11) buttons.

``FluentButton`` reproduces the WinUI 3 button: 4px corners, a control fill
with a darker bottom edge, a crossfaded hover, dimmed text while pressed and
the two-tone keyboard focus rectangle.

``IconButton`` and ``CaptionButton`` cover the small round/square controls,
including the Win11 caption buttons (minimise / maximise / close) whose
glyphs are drawn as vectors so they never depend on an icon font.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QPushButton

from ui.theme import (
    Motion, Radius, darken, lighten, mix, qc, rounded_path, theme, ui_font,
)
from ui.widgets.anim import animate

# token attribute lookups resolved at paint time so theme switches are live
VARIANTS: dict[str, dict] = {
    # filled accent button
    "accent": dict(fill="accent", hover="accent_hover", press="accent_press",
                   border="accent", bottom=0.0, fg="text_on_accent"),
    # the default Win11 button
    "standard": dict(fill="control", hover="control_hover", press="control_press",
                     border="control_stroke", bottom=1.0, fg="text"),
    # transparent button, fill only on hover
    "subtle": dict(fill=None, hover="subtle_hover", press="subtle_press",
                   border=None, bottom=0.0, fg="text"),
    # destructive - Win11 keeps the standard chrome, the label turns red
    "critical": dict(fill="control", hover="control_hover", press="control_press",
                     border="control_stroke", bottom=1.0, fg="critical"),
    "success": dict(fill="control", hover="control_hover", press="control_press",
                    border="control_stroke", bottom=1.0, fg="success"),
}


class FluentButton(QPushButton):
    """A WinUI 3 style push button."""

    def __init__(self, text: str = "", variant: str = "standard",
                 radius: int = Radius.CONTROL, font_size: int = 14,
                 bold: bool = False, parent=None):
        super().__init__(text, parent)
        self._variant = variant
        self._radius = radius
        self._font_size = font_size
        self._hover = 0.0
        self._press = 0.0
        self._busy = False
        self._busy_angle = 0

        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(max(32, font_size + 18))
        self.setFont(ui_font(font_size, QFont.DemiBold if bold else QFont.Normal))

        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(16)
        self._busy_timer.timeout.connect(self._tick_busy)

    # -- api ---------------------------------------------------------------

    def set_variant(self, variant: str) -> None:
        if variant != self._variant:
            self._variant = variant
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

    def set_text(self, text: str) -> None:
        self.setText(text)

    # -- animation ---------------------------------------------------------

    def _tick_busy(self) -> None:
        self._busy_angle = (self._busy_angle + 8) % 360
        self.update()

    def enterEvent(self, event):
        animate(self, "hover", self._hover, 1.0,
                lambda v: (setattr(self, "_hover", float(v)), self.update()),
                duration=Motion.FAST, easing=QEasingCurve.OutCubic)
        super().enterEvent(event)

    def leaveEvent(self, event):
        animate(self, "hover", self._hover, 0.0,
                lambda v: (setattr(self, "_hover", float(v)), self.update()),
                duration=Motion.FAST, easing=QEasingCurve.OutCubic)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            animate(self, "press", self._press, 1.0,
                    lambda v: (setattr(self, "_press", float(v)), self.update()),
                    duration=90, easing=QEasingCurve.OutCubic)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        animate(self, "press", self._press, 0.0,
                lambda v: (setattr(self, "_press", float(v)), self.update()),
                duration=Motion.FAST, easing=QEasingCurve.OutCubic)
        super().mouseReleaseEvent(event)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        spec = VARIANTS.get(self._variant, VARIANTS["standard"])
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        enabled = self.isEnabled()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = min(float(self._radius), rect.height() / 2.0)
        path = rounded_path(rect, radius)

        # ---- fill ---------------------------------------------------------
        fill_token = spec.get("fill")
        hover_color = qc(getattr(t, spec["hover"])) if spec.get("hover") else None
        press_color = qc(getattr(t, spec["press"])) if spec.get("press") else None

        if not enabled:
            base = qc(t.control_disabled) if fill_token else QColor(0, 0, 0, 0)
        elif fill_token is None:
            base = QColor(0, 0, 0, 0)
        else:
            base = qc(getattr(t, fill_token))

        color = base
        if enabled and hover_color is not None:
            color = mix(base, hover_color, self._hover)
        if enabled and press_color is not None:
            color = mix(color, press_color, self._press)
        if not enabled and fill_token is None:
            color = QColor(0, 0, 0, 0)

        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)

        # ---- border / bottom edge ----------------------------------------
        if spec.get("border"):
            border = qc(getattr(t, spec["border"]))
            if not enabled:
                border = qc(t.control_stroke)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(border, 1.0))
            painter.drawPath(rounded_path(rect.adjusted(0.5, 0.5, -0.5, -0.5),
                                          max(0.0, radius - 0.5)))
            if spec.get("bottom"):
                # WinUI: a slightly stronger 1px line along the bottom edge
                bottom = (qc(getattr(t, spec["border"])) if spec["border"]
                          != "accent" else darken(t.accent, 0.14))
                if not enabled:
                    bottom = qc(t.control_stroke)
                painter.setPen(QPen(bottom, 1.0))
                painter.drawLine(
                    QPointF(rect.left() + radius * 0.6, rect.bottom() - 0.5),
                    QPointF(rect.right() - radius * 0.6, rect.bottom() - 0.5))

        # ---- content ------------------------------------------------------
        fg = qc(getattr(t, spec.get("fg", "text")))
        if not enabled:
            fg = qc(t.text_disabled)
        elif self._press > 0.01:
            # WinUI dims the label while the button is held down
            surf = color if color.alpha() > 0 else qc(t.window)
            fg = mix(fg, surf, 0.45 * self._press)

        text_rect = QRectF(rect)
        if self._busy:
            text_rect = text_rect.adjusted(14, 0, 14, 0)
        if self.text():
            painter.setPen(fg)
            painter.setFont(self.font())
            painter.drawText(text_rect, Qt.AlignCenter, self.text())

        if self._busy:
            center = QPointF(rect.center().x() - text_rect.width() / 2 + 3,
                             rect.center().y())
            self._draw_spinner(painter, center, fg)

        if self.hasFocus():
            self._draw_focus_rect(painter, rect, radius)

    def _draw_spinner(self, painter: QPainter, center: QPointF, fg: QColor) -> None:
        r = 6.0
        box = QRectF(center.x() - r, center.y() - r, r * 2, r * 2)
        painter.save()
        painter.setBrush(Qt.NoBrush)
        track = QColor(fg)
        track.setAlpha(60)
        painter.setPen(QPen(track, 1.8, Qt.SolidLine, Qt.RoundCap))
        painter.drawEllipse(box)
        painter.setPen(QPen(fg, 1.8, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(box, int(-self._busy_angle * 16), int(100 * 16))
        painter.restore()

    def _draw_focus_rect(self, painter: QPainter, rect: QRectF,
                         radius: float) -> None:
        """WinUI's two-tone focus rectangle."""
        t = theme()
        outer = QColor(255, 255, 255) if t.is_dark else QColor(0, 0, 0)
        inner = QColor(0, 0, 0) if t.is_dark else QColor(255, 255, 255)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(outer, 2.0))
        painter.drawPath(rounded_path(rect.adjusted(-1, -1, 1, 1), radius + 1))
        painter.setPen(QPen(inner, 1.0))
        painter.drawPath(rounded_path(rect.adjusted(-1, -1, 1, 1), radius + 1))


class IconButton(QPushButton):
    """Small square Fluent icon button (hover = subtle fill)."""

    def __init__(self, glyph: str = "", size: int = 32, tone: str = "text",
                 parent=None):
        super().__init__(glyph, parent)
        self._glyph = glyph
        self._tone = tone
        self._hover = 0.0
        self._press = 0.0
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFont(ui_font(int(size * 0.45)))

    def set_glyph(self, glyph: str) -> None:
        self._glyph = glyph
        self.update()

    def set_tone(self, tone: str) -> None:
        self._tone = tone
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

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, Radius.CONTROL)

        level = max(self._hover, self._press)
        if level > 0.01 and self.isEnabled():
            painter.setPen(Qt.NoPen)
            painter.setBrush(qc(t.subtle_hover, int(255 * level)))
            painter.drawPath(path)

        fg = qc(getattr(t, self._tone, t.text)) if self.isEnabled() \
            else qc(t.text_disabled)
        if self._press > 0.01:
            fg = mix(fg, qc(t.text_tertiary), 0.5 * self._press)
        painter.setPen(fg)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignCenter, self._glyph)


class CaptionButton(QPushButton):
    """
    Windows 11 caption button: 46x32, no corner radius, subtle hover fill and
    the red ``#C42B1C`` close-button state.  Glyphs are vector-drawn.
    """

    MINIMIZE, MAXIMIZE, RESTORE, CLOSE = range(4)

    WIDTH = 46
    HEIGHT = 32
    CLOSE_HOVER = "#FFC42B1C"
    CLOSE_PRESS = "#FFB02418"

    def __init__(self, kind: int, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._hover = 0.0
        self._tr_radius = 0        # round the top-right corner (window corner)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.ArrowCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFocusPolicy(Qt.NoFocus)

    def set_top_right_round(self, radius: int) -> None:
        """Clip the button so it follows the rounded window corner."""
        self._tr_radius = max(0, int(radius))
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
        painter.setRenderHint(QPainter.Antialiasing, False)
        t = theme()
        rect = QRectF(self.rect())

        if self._tr_radius > 0:
            # keep the hover fill inside the rounded window corner
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            r = float(self._tr_radius)
            path.moveTo(rect.left(), rect.top())
            path.lineTo(rect.right() - r, rect.top())
            path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + r)
            path.lineTo(rect.right(), rect.bottom())
            path.lineTo(rect.left(), rect.bottom())
            path.closeSubpath()
            painter.setClipPath(path)

        if self._hover > 0.01:
            if self._kind == self.CLOSE:
                color = mix(qc(t.window), self.CLOSE_HOVER, self._hover)
            else:
                color = qc(t.subtle_hover, int(255 * self._hover))
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRect(rect)

        closing = self._kind == self.CLOSE and self._hover > 0.3
        pen = QColor(255, 255, 255) if closing else qc(t.text)
        painter.setPen(QPen(pen, 1.0, Qt.SolidLine, Qt.SquareCap))

        cx, cy = rect.center().x(), rect.center().y()
        if self._kind == self.MINIMIZE:
            painter.drawLine(QPointF(cx - 5, cy + 4.5), QPointF(cx + 5, cy + 4.5))
        elif self._kind == self.MAXIMIZE:
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(cx - 5, cy - 5, 10, 10))
        elif self._kind == self.RESTORE:
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(cx - 5, cy - 3, 8, 8))
            painter.drawLine(QPointF(cx - 3, cy - 5), QPointF(cx + 5, cy - 5))
            painter.drawLine(QPointF(cx + 5, cy - 5), QPointF(cx + 5, cy + 3))
        else:  # CLOSE
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.drawLine(QPointF(cx - 5, cy - 5), QPointF(cx + 5, cy + 5))
            painter.drawLine(QPointF(cx + 5, cy - 5), QPointF(cx - 5, cy + 5))
