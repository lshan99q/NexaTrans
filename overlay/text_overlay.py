"""
NexaTrans - Text Detection Overlay
"""

import logging
import numpy as np
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF

logger = logging.getLogger("NexaTrans.TextOverlay")


class TextOverlay(QWidget):

    def __init__(self):
        super().__init__()
        self._boxes = []
        self._mask_colors = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setGeometry(0, 0, 0, 0)
        self._region = {"x": 0, "y": 0, "width": 0, "height": 0}

    def update_region(self, region: dict):
        x = int(region.get("x", 0)); y = int(region.get("y", 0))
        w = int(region.get("width", 0)); h = int(region.get("height", 0))
        if w <= 0 or h <= 0: return
        self._region = {"x": x, "y": y, "width": w, "height": h}
        self.setGeometry(x, y, w, h)

    def set_data(self, boxes: list, mask, colors: list):
        self._boxes = boxes
        self._mask_colors = [(c[2], c[1], c[0]) for c in colors] if colors else None

        if boxes and not self.isVisible():
            self.show()
        self.update()

    def show_overlay(self):
        if self._region.get("width", 0) > 0:
            self.show()

    def hide_overlay(self):
        self.hide(); self._boxes = []; self._mask_colors = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._mask_colors and self._boxes:
            for box, (r_val, g_val, b_val) in zip(self._boxes, self._mask_colors):
                if len(box) < 8: continue
                xs = [box[i] for i in range(0, len(box), 2)]
                ys = [box[i + 1] for i in range(0, len(box), 2)]
                x1, y1 = min(xs), min(ys); x2, y2 = max(xs), max(ys)
                if x2 <= x1 or y2 <= y1: continue
                painter.setBrush(QColor(r_val, g_val, b_val, 255))
                painter.setPen(Qt.NoPen)
                painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

        for box in self._boxes:
            if len(box) < 8: continue
            poly = QPolygonF()
            for i in range(0, len(box), 2):
                if i + 1 < len(box):
                    poly.append(QPointF(float(box[i]), float(box[i + 1])))
            if poly.isEmpty(): continue
            painter.setBrush(QColor(0, 255, 100, 30))
            painter.setPen(QPen(QColor(0, 255, 100, 200), 2))
            painter.drawPolygon(poly)

        painter.end()

    def closeEvent(self, event):
        super().closeEvent(event)
