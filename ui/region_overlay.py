# -*- coding: utf-8 -*-
"""
NexaTrans - Region Overlay  (UI v2.0 "Aurora")

Resident, click-through frame that shows where the translation region is.
Animated marching-ants border, corner brackets and a live size chip.
"""

import logging

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QFont, QFontMetrics, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ui.theme import Palette, qc, ui_font

logger = logging.getLogger("NexaTrans.RegionOverlay")


class RegionOverlay(QWidget):
    """Resident region test frame (transparent, always on top, click-through)."""

    MARGIN = 6          # transparent padding that hosts the outer glow

    def __init__(self):
        super().__init__()
        self._region = {"x": 0, "y": 0, "width": 0, "height": 0}
        self._visible = False
        self._phase = 0.0
        self._pulse = 0.0
        self._pulse_dir = 1

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------

    def _tick(self):
        self._phase = (self._phase + 1.0) % 1000.0
        self._pulse += 0.045 * self._pulse_dir
        if self._pulse >= 1.0:
            self._pulse, self._pulse_dir = 1.0, -1
        elif self._pulse <= 0.0:
            self._pulse, self._pulse_dir = 0.0, 1
        self.update()

    def update_region(self, region: dict):
        """Update the region and resize/reposition the window."""
        self._region = region
        x = region.get("x", 0)
        y = region.get("y", 0)
        w = region.get("width", 0)
        h = region.get("height", 0)

        if w > 0 and h > 0:
            self.setGeometry(x - self.MARGIN, y - self.MARGIN,
                             w + self.MARGIN * 2, h + self.MARGIN * 2)
            logger.debug(f"Region overlay updated: ({x},{y}) {w}x{h}")
            self.update()
            if self._visible and not self.isVisible():
                self.show()
                self.raise_()
        else:
            self.hide()

    def set_test_visible(self, visible: bool):
        self._visible = visible
        region = self._region
        if visible and region.get("width", 0) > 0 and region.get("height", 0) > 0:
            self.show()
            self.raise_()
            self._timer.start()
            logger.info("Region overlay shown")
        else:
            self._timer.stop()
            self.hide()
            logger.info("Region overlay hidden")

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        rect = QRectF(self.rect()).adjusted(self.MARGIN - 1.5,
                                            self.MARGIN - 1.5,
                                            -(self.MARGIN - 1.5),
                                            -(self.MARGIN - 1.5))
        if rect.width() <= 4 or rect.height() <= 4:
            return
        radius = 6.0
        glow_alpha = int(30 + 45 * self._pulse)

        # outer glow drawn as strokes so the interior stays transparent
        painter.setBrush(Qt.NoBrush)
        for i in range(4, 0, -1):
            painter.setPen(QPen(qc(Palette.CYAN, int(glow_alpha / (i * 2.2))),
                                i * 1.6))
            painter.drawRoundedRect(rect.adjusted(-i, -i, i, i),
                                    radius + i, radius + i)

        # gradient frame
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, qc(Palette.CYAN))
        grad.setColorAt(1.0, qc(Palette.VIOLET))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(grad, 2.0))
        painter.drawRoundedRect(rect, radius, radius)

        # marching ants
        ants = QPen(qc("#FFFFFF", 170), 1.1, Qt.CustomDashLine)
        ants.setDashPattern([5, 5])
        ants.setDashOffset(self._phase * 0.5)
        painter.setPen(ants)
        painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), radius, radius)

        # corner brackets
        painter.setPen(QPen(qc(Palette.CYAN), 3.0, Qt.SolidLine, Qt.RoundCap))
        arm = 14.0
        for cx, cy, dx, dy in (
            (rect.left(), rect.top(), 1, 1),
            (rect.right(), rect.top(), -1, 1),
            (rect.left(), rect.bottom(), 1, -1),
            (rect.right(), rect.bottom(), -1, -1),
        ):
            painter.drawLine(int(cx), int(cy), int(cx + arm * dx), int(cy))
            painter.drawLine(int(cx), int(cy), int(cx), int(cy + arm * dy))

        self._draw_chip(painter, rect)

    def _draw_chip(self, painter, rect: QRectF):
        region = self._region
        text = (f"\u7ffb\u8bd1\u533a\u57df  {region.get('width', 0)}"
                f" \u00d7 {region.get('height', 0)}")
        font = ui_font(11, QFont.DemiBold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        bw = fm.horizontalAdvance(text) + 26
        bh = 24

        if rect.width() < bw + 12 or rect.height() < bh + 12:
            return

        chip = QRectF(rect.left() + 8, rect.top() + 8, bw, bh)
        painter.setPen(Qt.NoPen)
        painter.setBrush(qc("#070C15", 215))
        painter.drawRoundedRect(chip, 7, 7)
        painter.setPen(QPen(qc(Palette.CYAN, 150), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(chip.adjusted(0.5, 0.5, -0.5, -0.5), 7, 7)

        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(Palette.CYAN))
        painter.drawEllipse(QRectF(chip.left() + 9, chip.center().y() - 2.5,
                                   5, 5))

        painter.setPen(qc(Palette.TEXT))
        painter.drawText(chip.adjusted(18, 0, -8, 0),
                         Qt.AlignVCenter | Qt.AlignLeft, text)

    def closeEvent(self, event):
        self._timer.stop()
        logger.debug("Region overlay closed")
        super().closeEvent(event)
