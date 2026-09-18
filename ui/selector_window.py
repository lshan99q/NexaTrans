# -*- coding: utf-8 -*-
"""
NexaTrans - Region Selector  (Windows 11 Fluent)

Full-screen dimmed overlay used to pick the translation region, styled after
the Windows 11 Snipping Tool: crosshair, accent selection frame with resize
handles, live size chip and a Fluent hint card.

Interaction is unchanged: drag with the left mouse button, ESC to cancel.
"""

import logging

from PySide6.QtCore import QEasingCurve, QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

from ui.theme import (
    Radius, qc, rounded_path, scale_alpha, theme, ui_font,
)

logger = logging.getLogger("NexaTrans.Selector")

MIN_SIZE = 10


class SelectorWindow(QWidget):
    """Full-screen overlay for mouse region selection."""

    region_selected = Signal(dict)
    cancelled = Signal()

    def __init__(self, overlay_config: dict = None):
        super().__init__()
        self.overlay_config = overlay_config or {"opacity": 0.5, "border": True}

        self._start_point: QPoint | None = None
        self._end_point: QPoint | None = None
        self._is_selecting = False
        self._cursor_pos = QPoint(0, 0)
        self._intro = 0.0
        self._handles = 0.0
        self._too_small = 0.0

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._tick)

        self._setup_window()
        self._show_fullscreen()

        QTimer.singleShot(50, self._force_topmost)
        self._anim_timer.start()
        logger.info("Selection window created and fullscreen")

    # ------------------------------------------------------------------
    # window plumbing (unchanged behaviour)
    # ------------------------------------------------------------------

    def _setup_window(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    def _show_fullscreen(self):
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
        self.raise_()
        self.activateWindow()

    def showEvent(self, event):
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # animation
    # ------------------------------------------------------------------

    def _tick(self):
        if self._intro < 1.0:
            self._intro = min(1.0, self._intro + 0.10)
        target = 1.0 if self._is_selecting else 0.0
        if abs(self._handles - target) > 0.01:
            self._handles += (target - self._handles) * 0.30
        if self._too_small > 0.0:
            self._too_small = max(0.0, self._too_small - 0.035)
        self.update()

    # ------------------------------------------------------------------
    # mouse / keyboard
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            self._start_point = pos
            self._end_point = pos
            self._cursor_pos = pos
            self._is_selecting = True
            self._too_small = 0.0
            self.update()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        self._cursor_pos = pos
        if self._is_selecting:
            self._end_point = pos
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self._is_selecting:
            return
        self._is_selecting = False
        self._end_point = event.position().toPoint()

        if self._start_point is None:
            return

        rect = self._selection_rect()
        if rect.width() < MIN_SIZE or rect.height() < MIN_SIZE:
            logger.warning(f"Region too small: {rect.width()}x{rect.height()}")
            self._start_point = None
            self._end_point = None
            self._too_small = 1.0
            self.update()
            return

        # ints only: the region is fed straight into QWidget.setGeometry()
        region = {"x": int(round(rect.x())), "y": int(round(rect.y())),
                  "width": int(round(rect.width())),
                  "height": int(round(rect.height()))}
        logger.info(f"Region selected: {region}")
        self._anim_timer.stop()
        self.region_selected.emit(region)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            logger.info("ESC - cancelled")
            self._start_point = None
            self._end_point = None
            self._is_selecting = False
            self._anim_timer.stop()
            self.cancelled.emit()
            self.close()

    def _selection_rect(self):
        if self._start_point is None or self._end_point is None:
            return None
        x1 = min(self._start_point.x(), self._end_point.x())
        y1 = min(self._start_point.y(), self._end_point.y())
        x2 = max(self._start_point.x(), self._end_point.x())
        y2 = max(self._start_point.y(), self._end_point.y())
        return QRectF(x1, y1, x2 - x1, y2 - y1)

    # ------------------------------------------------------------------
    # painting
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        win_w, win_h = self.width(), self.height()
        rect = self._selection_rect()
        active = rect is not None and rect.width() > 0 and rect.height() > 0

        # ---- backdrop -------------------------------------------------
        if active:
            path = QPainterPath()
            path.setFillRule(Qt.OddEvenFill)
            path.addRect(QRectF(0, 0, win_w, win_h))
            path.addRect(rect)
            painter.setPen(Qt.NoPen)
            painter.setBrush(qc(t.smoke, int(qc(t.smoke).alpha() * self._intro)))
            painter.drawPath(path)
            self._draw_selection(painter, rect)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(qc(t.smoke, int(qc(t.smoke).alpha() * self._intro)))
            painter.drawRect(0, 0, win_w, win_h)
            self._draw_crosshair(painter, win_w, win_h)
            self._draw_hint_card(painter, win_w, win_h)

        if self._too_small > 0.0:
            self._draw_too_small(painter, win_w, win_h)

    # -- idle -----------------------------------------------------------

    def _draw_crosshair(self, painter, win_w, win_h):
        t = theme()
        x, y = self._cursor_pos.x(), self._cursor_pos.y()
        if x <= 0 and y <= 0:
            return
        pen = QPen(qc(t.text, int(90 * self._intro)), 1.0, Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(0, y, win_w, y)
        painter.drawLine(x, 0, x, win_h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(t.text, int(200 * self._intro)))
        painter.drawEllipse(QPoint(x, y), 2.5, 2.5)

    def _draw_hint_card(self, painter, win_w, win_h):
        t = theme()
        title = "\u62d6\u52a8\u9f20\u6807\u6846\u9009\u7ffb\u8bd1\u533a\u57df"
        sub = "ESC \u53d6\u6d88   \u00b7   \u677e\u5f00\u9f20\u6807\u786e\u8ba4"

        title_font = ui_font(18, QFont.DemiBold, display=True)
        sub_font = ui_font(13)
        painter.setFont(title_font)
        t_w = QFontMetrics(title_font).horizontalAdvance(title)
        painter.setFont(sub_font)
        s_w = QFontMetrics(sub_font).horizontalAdvance(sub)

        card_w = max(t_w, s_w) + 64
        card_h = 92
        cx = (win_w - card_w) / 2.0
        cy = win_h / 2.0 - card_h / 2.0 - 30 - (1.0 - self._intro) * 20

        card = QRectF(cx, cy, card_w, card_h)
        alpha = self._intro

        painter.setPen(Qt.NoPen)
        painter.setBrush(scale_alpha(t.flyout, alpha))
        painter.drawPath(rounded_path(card, Radius.CARD))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(qc(t.card_stroke), 1.0))
        painter.drawPath(rounded_path(card.adjusted(0.5, 0.5, -0.5, -0.5),
                                      Radius.CARD - 0.5))

        painter.setPen(scale_alpha(t.text, alpha))
        painter.setFont(title_font)
        painter.drawText(QRectF(card.left(), card.top() + 20, card.width(), 26),
                         Qt.AlignCenter, title)

        painter.setPen(scale_alpha(t.text_secondary, alpha))
        painter.setFont(sub_font)
        painter.drawText(QRectF(card.left(), card.top() + 52, card.width(), 20),
                         Qt.AlignCenter, sub)

    # -- selecting ------------------------------------------------------

    def _draw_selection(self, painter, rect: QRectF):
        t = theme()
        accent = qc(t.accent)

        # accent frame (Snipping Tool uses a 2px accent outline)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(accent, 2.0))
        painter.drawRect(rect.adjusted(1, 1, -1, -1))

        # resize handles fade in while dragging
        if self._handles > 0.05:
            size = 9.0 * self._handles
            half = size / 2.0
            points = [
                (rect.left(), rect.top()), (rect.center().x(), rect.top()),
                (rect.right(), rect.top()), (rect.right(), rect.center().y()),
                (rect.right(), rect.bottom()), (rect.center().x(), rect.bottom()),
                (rect.left(), rect.bottom()), (rect.left(), rect.center().y()),
            ]
            for px, py in points:
                box = QRectF(px - half, py - half, size, size)
                painter.setPen(QPen(accent, 1.0))
                painter.setBrush(QColor(255, 255, 255))
                painter.drawRect(box)

        self._draw_size_chip(painter, rect)

    def _draw_size_chip(self, painter, rect: QRectF):
        t = theme()
        text = f"{int(rect.width())} \u00d7 {int(rect.height())}"
        font = ui_font(13, QFont.DemiBold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        bw, bh = fm.horizontalAdvance(text) + 22, 28

        bx = rect.left()
        by = rect.bottom() + 8
        if by + bh > self.height() - 6:
            by = rect.top() - bh - 8
        if by < 6:
            by = rect.bottom() + 8
        bx = min(bx, self.width() - bw - 6)
        bx = max(bx, 6)

        chip = QRectF(bx, by, bw, bh)
        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(t.flyout, 240))
        painter.drawPath(rounded_path(chip, Radius.CONTROL))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(qc(t.card_stroke), 1.0))
        painter.drawPath(rounded_path(chip.adjusted(0.5, 0.5, -0.5, -0.5),
                                      Radius.CONTROL - 0.5))
        painter.setPen(qc(t.text))
        painter.drawText(chip, Qt.AlignCenter, text)

    def _draw_too_small(self, painter, win_w, win_h):
        t = theme()
        level = self._too_small          # 0..1 fade factor
        text = "\u533a\u57df\u592a\u5c0f\uff0c\u8bf7\u91cd\u65b0\u6846\u9009"
        font = ui_font(14, QFont.DemiBold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        bw = fm.horizontalAdvance(text) + 44
        badge = QRectF((win_w - bw) / 2, win_h / 2 - 24, bw, 48)

        painter.setPen(Qt.NoPen)
        painter.setBrush(scale_alpha(t.flyout, level))
        painter.drawPath(rounded_path(badge, Radius.CARD))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(scale_alpha(t.critical, level), 1.0))
        painter.drawPath(rounded_path(badge.adjusted(0.5, 0.5, -0.5, -0.5),
                                      Radius.CARD - 0.5))
        painter.setPen(scale_alpha(t.text, level))
        painter.drawText(badge, Qt.AlignCenter, text)

    def closeEvent(self, event):
        try:
            self._anim_timer.stop()
        except RuntimeError:
            pass
        logger.info("Selection window closed")
        super().closeEvent(event)
