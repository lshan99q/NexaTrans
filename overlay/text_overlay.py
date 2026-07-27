"""
NexaTrans - Text Detection Overlay
Transparent always-on-top window positioned at the region,
drawing detection boxes in LOCAL coordinates (just like RegionOverlay).
"""

import logging
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF

logger = logging.getLogger("NexaTrans.TextOverlay")


class TextOverlay(QWidget):
    """
    Always-on-top transparent overlay showing detected text boxes.
    Positioned at the region location, draws boxes in local coordinates.
    """

    def __init__(self):
        super().__init__()
        self._boxes = []  # local coordinates relative to region

        # Same flags as RegionOverlay (proven to work)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # Start hidden with zero size
        self.setGeometry(0, 0, 0, 0)
        self._region = {"x": 0, "y": 0, "width": 0, "height": 0}

    def update_region(self, region: dict):
        """Reposition the overlay to match the detection region."""
        x = int(region.get("x", 0))
        y = int(region.get("y", 0))
        w = int(region.get("width", 0))
        h = int(region.get("height", 0))

        if w <= 0 or h <= 0:
            return

        self._region = {"x": x, "y": y, "width": w, "height": h}
        self.setGeometry(x, y, w, h)

    def update_boxes(self, boxes: list):
        """
        Update boxes and repaint.

        Args:
            boxes: List of polygons in LOCAL coordinates (relative to region).
        """
        self._boxes = boxes
        if boxes:
            if not self.isVisible():
                self.show()
                self.raise_()
            self.update()
        else:
            self.update()

    def show_overlay(self):
        """Show and raise."""
        if self._region.get("width", 0) > 0 and self._region.get("height", 0) > 0:
            self.show()
            self.raise_()
            logger.info(
                f"TextOverlay shown at ({self._region['x']},{self._region['y']}) "
                f"{self._region['width']}x{self._region['height']}"
            )

    def hide_overlay(self):
        """Hide overlay."""
        self.hide()
        self._boxes = []

    def paintEvent(self, event):
        """Draw detection boxes in local coordinates."""
        if not self._boxes:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        for box in self._boxes:
            if len(box) < 8:
                continue

            poly = QPolygonF()
            for i in range(0, len(box), 2):
                if i + 1 < len(box):
                    poly.append(QPointF(float(box[i]), float(box[i + 1])))

            if poly.isEmpty():
                continue

            # Green semi-transparent fill
            painter.setBrush(QColor(0, 255, 100, 35))
            pen = QPen(QColor(0, 255, 100, 200), 2)
            painter.setPen(pen)
            painter.drawPolygon(poly)

            # Corner markers
            cs = 5
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 255, 100, 220))
            for i in range(0, min(len(box), 8), 2):
                if i + 1 < len(box):
                    painter.drawRect(
                        int(box[i]) - cs // 2,
                        int(box[i + 1]) - cs // 2,
                        cs, cs
                    )

    def closeEvent(self, event):
        logger.debug("Text detection overlay closed")
        super().closeEvent(event)
