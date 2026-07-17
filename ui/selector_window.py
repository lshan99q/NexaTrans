"""
NexaTrans - Selector Window
透明覆盖区域选择窗口：全屏鼠标框选交互
"""

import logging
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont

logger = logging.getLogger("NexaTrans.Selector")


class SelectorWindow(QWidget):
    """全屏透明覆盖窗口，用于鼠标框选翻译区域"""

    # 区域选择完成信号
    region_selected = Signal(dict)
    # 取消选择信号
    cancelled = Signal()

    def __init__(self, overlay_config: dict = None):
        super().__init__()
        self.overlay_config = overlay_config or {"opacity": 0.5, "border": True}

        # 鼠标状态
        self._start_point = None  # 鼠标按下时的起点
        self._end_point = None    # 鼠标移动时的终点
        self._is_selecting = False

        # 区域筛选标志 - 用于检测区域过小
        self._selection_complete = False

        self._setup_window()
        self._show_fullscreen()

        logger.info("选择窗口已创建")

    def _setup_window(self):
        """设置窗口属性"""
        # 窗口标志：无边框、置顶、工具窗口（不在任务栏显示）
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        # 透明背景
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 启用鼠标追踪（不需要按下即可追踪移动）
        self.setMouseTracking(True)
        # 设置光标样式为十字准星
        self.setCursor(Qt.CrossCursor)

    def _show_fullscreen(self):
        """获取主屏幕并全屏显示"""
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
            logger.info(f"全屏覆盖: {screen.geometry().getRect()}")
        else:
            # 保底：使用 1920x1080
            self.setGeometry(0, 0, 1920, 1080)
            logger.warning("无法获取主屏幕信息，使用默认分辨率 1920x1080")
        self.show()

    def mousePressEvent(self, event):
        """鼠标按下事件：记录起点"""
        if event.button() == Qt.LeftButton:
            self._start_point = event.position().toPoint()
            self._end_point = self._start_point
            self._is_selecting = True
            self._selection_complete = False
            logger.debug(f"鼠标按下: ({self._start_point.x()}, {self._start_point.y()})")
            self.update()

    def mouseMoveEvent(self, event):
        """鼠标移动事件：实时更新终点并重绘"""
        if self._is_selecting:
            self._end_point = event.position().toPoint()
            self.update()  # 触发重绘

    def mouseReleaseEvent(self, event):
        """鼠标释放事件：计算并保存区域"""
        if event.button() == Qt.LeftButton and self._is_selecting:
            self._is_selecting = False
            self._end_point = event.position().toPoint()
            self._selection_complete = True

            logger.debug(f"鼠标释放: ({self._end_point.x()}, {self._end_point.y()})")

            # 检查是否有实际拖动
            if self._start_point is None:
                return

            # 归一化坐标（处理反向拖动）
            x = min(self._start_point.x(), self._end_point.x())
            y = min(self._start_point.y(), self._end_point.y())
            width = abs(self._start_point.x() - self._end_point.x())
            height = abs(self._start_point.y() - self._end_point.y())

            # 检测区域过小
            if width < 10 or height < 10:
                logger.warning(f"选择的区域过小: {width}x{height}")
                self._show_size_warning()
                self._start_point = None
                self._end_point = None
                self.update()
                return

            # 构建区域数据
            region = {
                "x": x,
                "y": y,
                "width": width,
                "height": height
            }

            logger.info(f"区域选择完成: {region}")
            self.region_selected.emit(region)
            self.close()

    def keyPressEvent(self, event):
        """键盘事件：ESC 取消选择"""
        if event.key() == Qt.Key_Escape:
            logger.info("用户按下 ESC 取消选择")
            self._start_point = None
            self._end_point = None
            self._is_selecting = False
            self.cancelled.emit()
            self.close()

    def paintEvent(self, event):
        """绘制事件：绘制半透明遮罩和选择框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 获取窗口尺寸
        window_rect = self.rect()

        # 绘制深色半透明遮罩（类似截图工具的暗化效果）
        mask_color = QColor(0, 0, 0, 140)  # 加深遮罩
        painter.fillRect(window_rect, mask_color)

        if self._start_point is not None and self._end_point is not None:
            # 计算选择矩形
            rect = QRect(
                min(self._start_point.x(), self._end_point.x()),
                min(self._start_point.y(), self._end_point.y()),
                abs(self._start_point.x() - self._end_point.x()),
                abs(self._start_point.y() - self._end_point.y())
            )

            if rect.width() > 0 and rect.height() > 0:
                # 清除选择区域内的遮罩（"挖洞"效果）
                clear_brush = QBrush(QColor(0, 0, 0, 0))
                painter.setCompositionMode(QPainter.CompositionMode_Source)
                painter.fillRect(rect, clear_brush)
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

                # 绘制红色选择边框（类似截图工具风格）
                border_opacity = 200 if self.overlay_config.get("border", True) else 0
                if border_opacity > 0:
                    # 外边框（亮红色）
                    pen = QPen(QColor(220, 40, 40, border_opacity), 3)
                    painter.setPen(pen)
                    painter.drawRect(rect)

                    # 在四个角绘制小方块（截图工具风格）
                    corner_size = 6
                    corners = [
                        (rect.topLeft(), 1, 1),
                        (rect.topRight(), -corner_size, 1),
                        (rect.bottomLeft(), 1, -corner_size),
                        (rect.bottomRight(), -corner_size, -corner_size)
                    ]
                    corner_brush = QBrush(QColor(220, 40, 40, 220))
                    for pos, dx, dy in corners:
                        painter.fillRect(
                            pos.x() + dx, pos.y() + dy,
                            corner_size, corner_size,
                            corner_brush
                        )

                # 在矩形中心或左上角显示尺寸信息
                self._draw_size_label(painter, rect)

    def _draw_size_label(self, painter: QPainter, rect: QRect):
        """在选择框上绘制尺寸信息"""
        size_text = f"{rect.width()} × {rect.height()}"
        font = QFont("Arial", 12)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 200))

        # 尺寸标签显示位置：矩形左上角上方，或内部
        text_rect = painter.fontMetrics().boundingRect(size_text)
        label_x = rect.x()
        label_y = rect.y() - 8

        # 如果标签会超出屏幕顶部，放在矩形内部
        if label_y < 0:
            label_y = rect.y() + 8

        # 绘制文字阴影
        shadow_brush = QBrush(QColor(0, 0, 0, 150))
        painter.fillRect(
            label_x - 4, label_y - text_rect.height() + 4,
            text_rect.width() + 8, text_rect.height() + 8,
            shadow_brush
        )

        painter.drawText(label_x, label_y, size_text)

    def _show_size_warning(self):
        """显示区域过小的提示（在覆盖层上绘制）"""
        # 简单处理：通过设置一个标志，在下次 paintEvent 时显示
        self._show_warning = True
        self.update()

    # 覆盖层提示文字（通过定时器清除）
    def showEvent(self, event):
        """窗口显示时初始化"""
        super().showEvent(event)
        self._show_warning = False

    def closeEvent(self, event):
        """窗口关闭时清理"""
        logger.info("选择窗口关闭")
        super().closeEvent(event)