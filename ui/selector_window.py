"""
NexaTrans - Selector Window
透明覆盖区域选择窗口：全屏鼠标框选交互
使用分区域绘制法替代合成模式，兼容性更好
"""

import logging
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, Signal, QRect, QTimer
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QFontMetrics

logger = logging.getLogger("NexaTrans.Selector")


class SelectorWindow(QWidget):
    """全屏透明覆盖窗口，用于鼠标框选翻译区域"""

    region_selected = Signal(dict)
    cancelled = Signal()

    def __init__(self, overlay_config: dict = None):
        super().__init__()
        self.overlay_config = overlay_config or {"opacity": 0.5, "border": True}

        # 鼠标状态
        self._start_point = None
        self._end_point = None
        self._is_selecting = False

        self._setup_window()
        self._show_fullscreen()

        # 延迟强制置顶（等待事件循环启动）
        QTimer.singleShot(50, self._force_topmost)

        logger.info("选择窗口已创建并全屏显示")

    def _setup_window(self):
        """设置窗口属性"""
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        # 确保接收鼠标事件
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    def _show_fullscreen(self):
        """获取主屏幕并全屏显示"""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.setGeometry(geo)
            logger.info(f"全屏覆盖区域: {geo.x()}, {geo.y()}, {geo.width()}x{geo.height()}")
        else:
            self.setGeometry(0, 0, 1920, 1080)
            logger.warning("使用默认分辨率 1920x1080")

        self.show()
        self.raise_()
        self.activateWindow()
        logger.debug("窗口已显示并置顶")

    def _force_topmost(self):
        """强制窗口置顶"""
        self.raise_()
        self.activateWindow()
        logger.debug("延迟置顶完成")

    def showEvent(self, event):
        """窗口显示时置顶"""
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    # ---- 鼠标事件 ----

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            self._start_point = pos
            self._end_point = pos
            self._is_selecting = True
            logger.debug(f"鼠标按下: ({pos.x()}, {pos.y()})")
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._end_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_selecting:
            self._is_selecting = False
            self._end_point = event.position().toPoint()
            logger.debug(f"鼠标释放: ({self._end_point.x()}, {self._end_point.y()})")

            if self._start_point is None:
                return

            # 归一化坐标
            x = min(self._start_point.x(), self._end_point.x())
            y = min(self._start_point.y(), self._end_point.y())
            w = abs(self._start_point.x() - self._end_point.x())
            h = abs(self._start_point.y() - self._end_point.y())

            if w < 10 or h < 10:
                logger.warning(f"区域过小: {w}x{h}")
                self._start_point = None
                self._end_point = None
                self.update()
                return

            region = {"x": x, "y": y, "width": w, "height": h}
            logger.info(f"区域选择完成: {region}")
            self.region_selected.emit(region)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            logger.info("ESC 取消")
            self._start_point = None
            self._end_point = None
            self._is_selecting = False
            self.cancelled.emit()
            self.close()

    # ---- 绘制 ----

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        win_w = self.width()
        win_h = self.height()

        if self._start_point is not None and self._end_point is not None:
            # 有选择矩形 → 绘制四块遮罩（避开选中区域）
            x1 = min(self._start_point.x(), self._end_point.x())
            y1 = min(self._start_point.y(), self._end_point.y())
            x2 = max(self._start_point.x(), self._end_point.x())
            y2 = max(self._start_point.y(), self._end_point.y())

            # 只绘制有面积的矩形
            if x2 > x1 and y2 > y1:
                # 顶部遮罩
                painter.fillRect(0, 0, win_w, y1, QColor(0, 0, 0, 140))
                # 底部遮罩
                painter.fillRect(0, y2, win_w, win_h - y2, QColor(0, 0, 0, 140))
                # 左侧遮罩
                painter.fillRect(0, y1, x1, y2 - y1, QColor(0, 0, 0, 140))
                # 右侧遮罩
                painter.fillRect(x2, y1, win_w - x2, y2 - y1, QColor(0, 0, 0, 140))

                # 红色边框
                pen = QPen(QColor(220, 40, 40), 2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(x1, y1, x2 - x1, y2 - y1)

                # 四角标记
                cs = 6
                hcs = cs // 2
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(220, 40, 40))
                painter.drawRect(x1 - hcs, y1 - hcs, cs, cs)
                painter.drawRect(x2 - hcs, y1 - hcs, cs, cs)
                painter.drawRect(x1 - hcs, y2 - hcs, cs, cs)
                painter.drawRect(x2 - hcs, y2 - hcs, cs, cs)

                # 尺寸标签
                self._draw_size_tag(painter, x1, y1, x2 - x1, y2 - y1)

                logger.debug(f"绘制选择框: ({x1},{y1})-({x2},{y2})")
            else:
                # 矩形无效 → 全屏遮罩 + 提示
                painter.fillRect(0, 0, win_w, win_h, QColor(0, 0, 0, 140))
                self._draw_instructions(painter, win_w, win_h)
        else:
            # 全屏遮罩 + 提示
            painter.fillRect(0, 0, win_w, win_h, QColor(0, 0, 0, 140))
            self._draw_instructions(painter, win_w, win_h)

    def _draw_size_tag(self, painter, x, y, w, h):
        """在选框旁绘制尺寸标签"""
        font = QFont("Arial", 13, QFont.Bold)
        painter.setFont(font)
        text = f"{w} × {h}"
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        # 标签放在矩形左上角上方；如果超出屏幕则放在内部
        lx = x
        ly = y - 12
        if ly - th < 0:
            ly = y + 12 + th

        # 半透明黑底
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(lx - 6, ly - th + 2, tw + 12, th + 6, 3, 3)

        # 白色文字
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(lx, ly, text)

    def _draw_instructions(self, painter, win_w, win_h):
        """在屏幕中央绘制操作提示"""
        font = QFont("Microsoft YaHei", 20, QFont.Bold)
        painter.setFont(font)

        lines = ["请拖动鼠标选择翻译区域", "按 ESC 取消"]
        fm = QFontMetrics(font)
        cx = win_w // 2
        cy = win_h // 2

        for i, line in enumerate(lines):
            tw = fm.horizontalAdvance(line)
            tx = cx - tw // 2
            ty = cy + i * 50

            # 半透明黑底
            painter.setBrush(QColor(0, 0, 0, 130))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(tx - 20, ty - fm.ascent() - 10, tw + 40, fm.height() + 20, 10, 10)

            # 文字
            if i == 0:
                painter.setPen(QColor(255, 255, 255))
            else:
                painter.setPen(QColor(200, 200, 200))

            painter.drawText(tx, ty + fm.ascent() // 2, line)

    def closeEvent(self, event):
        logger.info("选择窗口关闭")
        super().closeEvent(event)