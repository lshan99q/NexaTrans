"""
NexaTrans - Text Detection Overlay (Stage 5)
Displays green detection boxes, mask fills, and OCR recognized text.
"""

import logging
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QPolygonF, QFont, QPixmap, QImage,
)

logger = logging.getLogger("NexaTrans.TextOverlay")


class TextOverlay(QWidget):
    """Overlay widget showing detection boxes, masks, and OCR text."""

    def __init__(self):
        super().__init__()
        self._boxes = []
        self._mask_colors = None
        self._ocr_results = {}
        self._show_ocr = False
        self._show_boxes = True

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setGeometry(0, 0, 0, 0)
        self._region = {"x": 0, "y": 0, "width": 0, "height": 0}

    def update_region(self, region: dict):
        x = int(region.get("x", 0))
        y = int(region.get("y", 0))
        w = int(region.get("width", 0))
        h = int(region.get("height", 0))
        if w <= 0 or h <= 0:
            return
        self._region = {"x": x, "y": y, "width": w, "height": h}
        self.setGeometry(x, y, w, h)

    def set_data(self, boxes: list, mask, colors: list):
        self._boxes = boxes
        self._mask_colors = (
            [(c[2], c[1], c[0]) for c in colors] if colors else None
        )
        if boxes and not self.isVisible():
            self.show()
        self.update()

    def set_ocr_results(self, results: list):
        self._ocr_results = {}
        for r in results:
            rid = r.get("id")
            if rid is not None:
                self._ocr_results[rid] = r
        if self._show_ocr and self.isVisible():
            self.update()

    @property
    def show_ocr(self) -> bool:
        return self._show_ocr

    @show_ocr.setter
    def show_ocr(self, v: bool):
        self._show_ocr = v
        self.update()

    @property
    def show_boxes(self) -> bool:
        return self._show_boxes

    @show_boxes.setter
    def show_boxes(self, v: bool):
        self._show_boxes = v
        self.update()

    def show_overlay(self):
        if self._region.get("width", 0) > 0:
            self.show()

    def hide_overlay(self):
        self.hide()
        self._boxes = []
        self._mask_colors = None
        self._ocr_results = {}

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw mask fills (opaque colored rectangles)
        if self._mask_colors and self._boxes:
            for i, (box, (r_val, g_val, b_val)) in enumerate(
                zip(self._boxes, self._mask_colors)
            ):
                if len(box) < 8:
                    continue
                xs = [box[j] for j in range(0, len(box), 2)]
                ys = [box[j + 1] for j in range(0, len(box), 2)]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                if x2 <= x1 or y2 <= y1:
                    continue
                painter.setBrush(QColor(r_val, g_val, b_val, 255))
                painter.setPen(Qt.NoPen)
                painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

        # Draw green detection boxes
        if self._show_boxes:
            for box in self._boxes:
                if len(box) < 8:
                    continue
                poly = QPolygonF()
                for i in range(0, len(box), 2):
                    if i + 1 < len(box):
                        poly.append(QPointF(float(box[i]), float(box[i + 1])))
                if poly.isEmpty():
                    continue
                painter.setBrush(QColor(0, 255, 100, 20))
                painter.setPen(QPen(QColor(0, 255, 100, 200), 2))
                painter.drawPolygon(poly)

        # Draw OCR text (no background, just white text with thin outline)
        if self._show_ocr and self._ocr_results and self._boxes:
            for i, box in enumerate(self._boxes):
                rid = i + 1
                result = self._ocr_results.get(rid)
                if not result:
                    continue
                text = result.get("text", "")
                if not text:
                    continue

                if len(box) < 8:
                    continue
                xs = [box[j] for j in range(0, len(box), 2)]
                ys = [box[j + 1] for j in range(0, len(box), 2)]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                bw = x2 - x1
                bh = y2 - y1

                font = QFont("Microsoft YaHei", max(10, min(18, int(bh * 0.7))))
                painter.setFont(font)

                fm = painter.fontMetrics()
                text_width = fm.horizontalAdvance(text)
                text_height = fm.height()

                tx = x1 + max(0, (bw - text_width) // 2)
                ty = y1 + max(0, (bh - text_height) // 2) + fm.ascent()

                # Draw outline effect (dark shadow under text for readability)
                painter.setPen(QColor(0, 0, 0, 160))
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                    painter.drawText(int(tx + dx), int(ty + dy), text)

                # Draw white text on top
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(int(tx), int(ty), text)

        painter.end()

    def closeEvent(self, event):
        super().closeEvent(event)
