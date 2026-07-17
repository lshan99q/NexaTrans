"""
NexaTrans - Region Overlay
常驻区域测试框：在屏幕指定位置显示红色边框，帮助用户确认所选区域
"""

import logging
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QBrush

logger = logging.getLogger("NexaTrans.RegionOverlay")


class RegionOverlay(QWidget):
    """常驻区域测试框（透明置顶窗口，只显示红色边框）"""

    def __init__(self):
        super().__init__()
        self._region = {"x": 0, "y": 0, "width": 0, "height": 0}
        self._visible = False

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # 鼠标穿透
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

    def update_region(self, region: dict):
        """更新区域并调整窗口位置和大小"""
        self._region = region
        x = region.get("x", 0)
        y = region.get("y", 0)
        w = region.get("width", 0)
        h = region.get("height", 0)

        if w > 0 and h > 0:
            # 窗口位置精确对应用户所选区域，不加偏移
            self.setGeometry(x, y, w, h)
            logger.debug(f"测试框更新: ({x},{y}) {w}x{h}")
            self.update()

            if self._visible and not self.isVisible():
                self.show()
                self.raise_()
        else:
            self.hide()

    def set_test_visible(self, visible: bool):
        """设置测试框可见性"""
        self._visible = visible
        region = self._region
        if visible and region.get("width", 0) > 0 and region.get("height", 0) > 0:
            self.show()
            self.raise_()
            logger.info("测试框已显示")
        else:
            self.hide()
            logger.info("测试框已隐藏")

    def paintEvent(self, event):
        """绘制红色边框（精确对齐窗口边缘）"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        w, h = rect.width(), rect.height()

        # 红色边框绘制在窗口外缘，标记精确的截图区域
        pen = QPen(QColor(220, 40, 40, 220), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, w - 1, h - 1)

        # 四角标记（1px 外扩，突出显示）
        cs = 5
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(220, 40, 40, 200))
        painter.drawRect(0, 0, cs, cs)
        painter.drawRect(w - cs, 0, cs, cs)
        painter.drawRect(0, h - cs, cs, cs)
        painter.drawRect(w - cs, h - cs, cs, cs)

    def closeEvent(self, event):
        logger.debug("测试框关闭")
        super().closeEvent(event)