"""
NexaTrans - Selector Window
Full-screen transparent region selection window with mouse drag interaction.
"""

import logging
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, Signal, QRect, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QFontMetrics

logger = logging.getLogger("NexaTrans.Selector")


class SelectorWindow(QWidget):
    """Full-screen transparent overlay for mouse region selection."""

    region_selected = Signal(dict)
    cancelled = Signal()

    def __init__(self, overlay_config: dict = None):
        super().__init__()
        self.overlay_config = overlay_config or {"opacity": 0.5, "border": True}

        self._start_point = None
        self._end_point = None
        self._is_selecting = False

        self._setup_window()
        self._show_fullscreen()

        QTimer.singleShot(50, self._force_topmost)

        logger.info("Selection window created and fullscreen")

    def _setup_window(self):
        """Configure window attributes."""
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    def _show_fullscreen(self):
        """Show fullscreen on primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.setGeometry(geo)
            logger.info(f"Fullscreen: {geo.width()}x{geo.height()}")
        else:
            self.setGeometry(0, 0, 1920, 1080)

        self.show()
        self.raise_()
        self.activateWindow()

    def _force_topmost(self):
        """Force window to top after event loop starts."""
        self.raise_()
        self.activateWindow()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    # ---- Mouse events ----

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            self._start_point = pos
            self._end_point = pos
            self._is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._end_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_selecting:
            self._is_selecting = False
            self._end_point = event.position().toPoint()

            if self._start_point is None:
                return

            x = min(self._start_point.x(), self._end_point.x())
            y = min(self._start_point.y(), self._end_point.y())
            w = abs(self._start_point.x() - self._end_point.x())
            h = abs(self._start_point.y() - self._end_point.y())

            if w < 10 or h < 10:
                logger.warning(f"Region too small: {w}x{h}")
                self._start_point = None
                self._end_point = None
                self.update()
                return

            region = {"x": x, "y": y, "width": w, "height": h}
            logger.info(f"Region selected: {region}")
            self.region_selected.emit(region)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            logger.info("ESC - cancelled")
            self._start_point = None
            self._end_point = None
            self._is_selecting = False
            self.cancelled.emit()
            self.close()

    # ---- Paint ----

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        win_w = self.width()
        win_h = self.height()

        if self._start_point is not None and self._end_point is not None:
            x1 = min(self._start_point.x(), self._end_point.x())
            y1 = min(self._start_point.y(), self._end_point.y())
            x2 = max(self._start_point.x(), self._end_point.x())
            y2 = max(self._start_point.y(), self._end_point.y())

            if x2 > x1 and y2 > y1:
                # Dark overlay around selection
                painter.fillRect(0, 0, win_w, y1, QColor(0, 0, 0, 140))
                painter.fillRect(0, y2, win_w, win_h - y2, QColor(0, 0, 0, 140))
                painter.fillRect(0, y1, x1, y2 - y1, QColor(0, 0, 0, 140))
                painter.fillRect(x2, y1, win_w - x2, y2 - y1, QColor(0, 0, 0, 140))

                # Red border
                pen = QPen(QColor(220, 40, 40), 2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(x1, y1, x2 - x1, y2 - y1)

                # Corner markers
                cs = 6
                hcs = cs // 2
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(220, 40, 40))
                painter.drawRect(x1 - hcs, y1 - hcs, cs, cs)
                painter.drawRect(x2 - hcs, y1 - hcs, cs, cs)
                painter.drawRect(x1 - hcs, y2 - hcs, cs, cs)
                painter.drawRect(x2 - hcs, y2 - hcs, cs, cs)

                # Size label
                self._draw_size_tag(painter, x1, y1, x2 - x1, y2 - y1)
            else:
                painter.fillRect(0, 0, win_w, win_h, QColor(0, 0, 0, 140))
                self._draw_instructions(painter, win_w, win_h)
        else:
            painter.fillRect(0, 0, win_w, win_h, QColor(0, 0, 0, 140))
            self._draw_instructions(painter, win_w, win_h)

    def _draw_size_tag(self, painter, x, y, w, h):
        """Draw size label near selection."""
        font = QFont("Microsoft YaHei", 13, QFont.Bold)
        painter.setFont(font)
        text = f"{w} x {h}"
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        lx = x
        ly = y - 12
        if ly - th < 0:
            ly = y + 12 + th

        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(lx - 6, ly - th + 2, tw + 12, th + 6, 3, 3)

        painter.setPen(QColor(255, 255, 255))
        painter.drawText(lx, ly, text)

    def _draw_instructions(self, painter, win_w, win_h):
        """Draw operation hints at screen center."""
        font = QFont("Microsoft YaHei", 20, QFont.Bold)
        painter.setFont(font)

        lines = [
            "拖动鼠标框选翻译区域",
            "按 ESC 取消",
        ]
        fm = QFontMetrics(font)
        cx = win_w // 2
        cy = win_h // 2

        for i, line in enumerate(lines):
            tw = fm.horizontalAdvance(line)
            tx = cx - tw // 2
            ty = cy + i * 50

            painter.setBrush(QColor(0, 0, 0, 130))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(
                tx - 20, ty - fm.ascent() - 10,
                tw + 40, fm.height() + 20, 10, 10
            )

            if i == 0:
                painter.setPen(QColor(255, 255, 255))
            else:
                painter.setPen(QColor(200, 200, 200))

            painter.drawText(tx, ty + fm.ascent() // 2, line)

    def closeEvent(self, event):
        logger.info("Selection window closed")
        super().closeEvent(event)
