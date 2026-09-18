# -*- coding: utf-8 -*-
"""
NexaTrans - Region Overlay  (Windows 11 Fluent)

Resident, click-through frame marking the active translation region: a 2px
accent outline with resize-style handles and a small size chip, matching the
Windows 11 Snipping Tool / screen-capture indicators.
"""

import logging

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ui.theme import Radius, qc, rounded_path, theme, ui_font

logger = logging.getLogger("NexaTrans.RegionOverlay")


class RegionOverlay(QWidget):
    """Resident region frame (transparent, always on top, click-through)."""

    MARGIN = 5          # transparent padding that hosts the outer glow

    def __init__(self):
        super().__init__()
        self._region = {"x": 0, "y": 0, "width": 0, "height": 0}
        self._visible = False
        self._pulse = 0.0
        self._dir = 1

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
        self._pulse += 0.035 * self._dir
        if self._pulse >= 1.0:
            self._pulse, self._dir = 1.0, -1
        elif self._pulse <= 0.0:
            self._pulse, self._dir = 0.0, 1
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
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        inset = self.MARGIN - 1.0
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        if rect.width() <= 4 or rect.height() <= 4:
            return

        accent = qc(t.accent)

        # soft accent halo so the marker stays noticeable over bright content
        halo = QColor(accent)
        halo.setAlpha(int(22 + 26 * self._pulse))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(halo, 3.0))
        painter.drawRect(rect.adjusted(-2, -2, 2, 2))

        # accent frame
        painter.setPen(QPen(accent, 2.0))
        painter.drawRect(rect)

        # corner handles
        size = 9.0
        half = size / 2.0
        painter.setPen(QPen(accent, 1.0))
        painter.setBrush(QColor(255, 255, 255))
        for px, py in ((rect.left(), rect.top()), (rect.right(), rect.top()),
                       (rect.left(), rect.bottom()), (rect.right(), rect.bottom())):
            painter.drawRect(QRectF(px - half, py - half, size, size))

        self._draw_chip(painter, rect)

    def _draw_chip(self, painter, rect: QRectF):
        t = theme()
        region = self._region
        text = (f"{region.get('width', 0)} \u00d7 {region.get('height', 0)}")
        font = ui_font(12, QFont.DemiBold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        bw, bh = fm.horizontalAdvance(text) + 20, 24

        if rect.width() < bw + 12 or rect.height() < bh + 12:
            return

        chip = QRectF(rect.left() + 6, rect.top() + 6, bw, bh)
        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(t.flyout, 235))
        painter.drawPath(rounded_path(chip, Radius.CONTROL))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(qc(t.card_stroke), 1.0))
        painter.drawPath(rounded_path(chip.adjusted(0.5, 0.5, -0.5, -0.5),
                                      Radius.CONTROL - 0.5))
        painter.setPen(qc(t.text))
        painter.drawText(chip, Qt.AlignCenter, text)

    def closeEvent(self, event):
        self._timer.stop()
        logger.debug("Region overlay closed")
        super().closeEvent(event)
