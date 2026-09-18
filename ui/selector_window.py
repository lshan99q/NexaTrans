# -*- coding: utf-8 -*-
"""
NexaTrans - Region Selector  (UI v2.0 "Aurora")

Full-screen translucent overlay used to pick the translation region.

Interaction is unchanged: drag with the left mouse button to select, ESC to
cancel.  The presentation is new - animated marching-ants border, corner
brackets, live size badge, cursor crosshair and an animated hint card.
"""

import logging

from PySide6.QtCore import QEasingCurve, QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath,
    QPen, QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QWidget

from ui.theme import Palette, qc, rounded_path, ui_font

logger = logging.getLogger("NexaTrans.Selector")

MIN_SIZE = 10


class SelectorWindow(QWidget):
    """Full-screen transparent overlay for mouse region selection."""

    region_selected = Signal(dict)
    cancelled = Signal()

    def __init__(self, overlay_config: dict = None):
        super().__init__()
        self.overlay_config = overlay_config or {"opacity": 0.5, "border": True}

        self._start_point: QPoint | None = None
        self._end_point: QPoint | None = None
        self._is_selecting = False
        self._cursor_pos = QPoint(0, 0)
        self._phase = 0.0
        self._intro = 0.0
        self._too_small = 0.0

        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
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
        self._phase = (self._phase + 1.1) % 1000.0
        if self._intro < 1.0:
            self._intro = min(1.0, self._intro + 0.09)
        if self._too_small > 0.0:
            self._too_small = max(0.0, self._too_small - 0.05)
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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        win_w, win_h = self.width(), self.height()
        rect = self._selection_rect()
        active = rect is not None and rect.width() > 0 and rect.height() > 0
        dim = int(168 * self._intro)

        # ---- backdrop -------------------------------------------------
        if active:
            path = QPainterPath()
            path.setFillRule(Qt.OddEvenFill)
            path.addRect(QRectF(0, 0, win_w, win_h))
            path.addRoundedRect(rect, 8, 8)
            painter.setPen(Qt.NoPen)
            painter.setBrush(qc("#04070D", dim))
            painter.drawPath(path)
            self._draw_selection(painter, rect)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(qc("#04070D", dim))
            painter.drawRect(0, 0, win_w, win_h)
            self._draw_spotlight(painter)
            self._draw_crosshair(painter, win_w, win_h)
            self._draw_hint_card(painter, win_w, win_h)

        if self._too_small > 0.0:
            self._draw_too_small(painter, win_w, win_h)

    # -- idle state -----------------------------------------------------

    def _draw_spotlight(self, painter):
        radius = 260.0
        grad = QRadialGradient(self._cursor_pos, radius)
        grad.setColorAt(0.0, qc(Palette.CYAN, int(30 * self._intro)))
        grad.setColorAt(0.6, qc(Palette.CYAN, int(10 * self._intro)))
        grad.setColorAt(1.0, qc(Palette.CYAN, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawEllipse(self._cursor_pos, radius, radius)

    def _draw_crosshair(self, painter, win_w, win_h):
        x, y = self._cursor_pos.x(), self._cursor_pos.y()
        color = qc(Palette.CYAN, int(70 * self._intro))
        painter.setPen(QPen(color, 1, Qt.DashLine))
        painter.drawLine(0, y, win_w, y)
        painter.drawLine(x, 0, x, win_h)

        painter.setPen(QPen(qc(Palette.CYAN, int(200 * self._intro)), 1.4))
        painter.setBrush(qc(Palette.CYAN, int(120 * self._intro)))
        painter.drawEllipse(self._cursor_pos, 3.0, 3.0)

    def _draw_hint_card(self, painter, win_w, win_h):
        title = "\u62d6\u52a8\u9f20\u6807\u6846\u9009\u7ffb\u8bd1\u533a\u57df"
        sub = "ESC \u53d6\u6d88   \u00b7   \u677e\u5f00\u9f20\u6807\u786e\u8ba4"

        title_font = ui_font(18, QFont.Bold)
        sub_font = ui_font(12)
        painter.setFont(title_font)
        t_w = QFontMetrics(title_font).horizontalAdvance(title)
        painter.setFont(sub_font)
        s_w = QFontMetrics(sub_font).horizontalAdvance(sub)

        card_w = max(t_w, s_w) + 72
        card_h = 96
        cx = (win_w - card_w) / 2.0
        cy = win_h / 2.0 - card_h / 2.0 - 40 - (1.0 - self._intro) * 22

        card = QRectF(cx, cy, card_w, card_h)
        path = rounded_path(card, 16)

        grad = QLinearGradient(card.topLeft(), card.bottomRight())
        grad.setColorAt(0.0, qc("#101A28", int(238 * self._intro)))
        grad.setColorAt(1.0, qc("#0A111D", int(238 * self._intro)))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawPath(path)

        pulse = 0.55 + 0.45 * abs(((self._phase % 60) / 60.0) * 2 - 1)
        painter.setPen(QPen(qc(Palette.CYAN, int(150 * pulse * self._intro)), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(rounded_path(card.adjusted(0.6, 0.6, -0.6, -0.6), 15))

        painter.setPen(qc(Palette.TEXT, int(255 * self._intro)))
        painter.setFont(title_font)
        painter.drawText(QRectF(card.left(), card.top() + 20, card.width(), 28),
                         Qt.AlignCenter, title)

        painter.setPen(qc(Palette.TEXT_MUTED, int(255 * self._intro)))
        painter.setFont(sub_font)
        painter.drawText(QRectF(card.left(), card.top() + 52, card.width(), 20),
                         Qt.AlignCenter, sub)

        # animated "drag" indicator
        bar = QRectF(card.left() + 26, card.bottom() - 18, card.width() - 52, 3)
        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(Palette.BORDER_HI, int(180 * self._intro)))
        painter.drawRoundedRect(bar, 1.5, 1.5)
        travel = max(1.0, bar.width() - 54)
        bx = bar.left() + (self._phase % 120) / 120.0 * travel
        fill = QLinearGradient(bx, bar.top(), bx + 54, bar.top())
        fill.setColorAt(0.0, qc(Palette.CYAN, 0))
        fill.setColorAt(0.5, qc(Palette.CYAN, int(220 * self._intro)))
        fill.setColorAt(1.0, qc(Palette.VIOLET, 0))
        painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(bx, bar.top(), 54, bar.height()), 1.5, 1.5)

        # brand chip, top-left
        chip = QRectF(26, 24, 200, 36)
        painter.setPen(Qt.NoPen)
        painter.setBrush(qc("#0B1220", int(200 * self._intro)))
        painter.drawRoundedRect(chip, 10, 10)
        painter.setPen(QPen(qc(Palette.BORDER_HI, int(200 * self._intro)), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(chip.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        painter.setPen(qc(Palette.CYAN, int(255 * self._intro)))
        painter.setFont(ui_font(12, QFont.DemiBold))
        painter.drawText(chip, Qt.AlignCenter,
                         "NexaTrans  \u00b7  \u533a\u57df\u9009\u62e9")

    # -- selecting ------------------------------------------------------

    def _draw_selection(self, painter, rect: QRectF):
        radius = 8.0

        # outer glow: expanding rings drawn as strokes so the cut-out stays
        # fully transparent (filled rings would tint the selected area)
        painter.setBrush(Qt.NoBrush)
        for i in range(6, 0, -1):
            painter.setPen(QPen(qc(Palette.CYAN, int(5 * (7 - i))), i * 1.8))
            painter.drawRoundedRect(rect.adjusted(-i, -i, i, i),
                                    radius + i, radius + i)

        # solid gradient frame
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, qc(Palette.CYAN))
        grad.setColorAt(1.0, qc(Palette.VIOLET))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(grad, 2.0))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)

        # marching ants
        ants = QPen(qc("#FFFFFF", 190), 1.2, Qt.CustomDashLine)
        ants.setDashPattern([5, 5])
        ants.setDashOffset(self._phase * 0.5)
        painter.setPen(ants)
        painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), radius, radius)

        # corner brackets
        painter.setPen(QPen(qc(Palette.CYAN), 3.0, Qt.SolidLine, Qt.RoundCap))
        arm = 18.0
        corners = [
            (rect.left(), rect.top(), 1, 1),
            (rect.right(), rect.top(), -1, 1),
            (rect.left(), rect.bottom(), 1, -1),
            (rect.right(), rect.bottom(), -1, -1),
        ]
        for cx, cy, dx, dy in corners:
            painter.drawLine(int(cx), int(cy), int(cx + arm * dx), int(cy))
            painter.drawLine(int(cx), int(cy), int(cx), int(cy + arm * dy))

        # edge length labels
        self._draw_size_badge(painter, rect)

    def _draw_size_badge(self, painter, rect: QRectF):
        text = f"{int(rect.width())} \u00d7 {int(rect.height())}"
        font = ui_font(13, QFont.Bold, mono=True)
        painter.setFont(font)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        bw, bh = tw + 24, 28

        bx = rect.left()
        by = rect.top() - bh - 10
        if by < 8:
            by = rect.top() + 10

        badge = QRectF(bx, by, bw, bh)
        painter.setPen(Qt.NoPen)
        painter.setBrush(qc("#070C15", 235))
        painter.drawRoundedRect(badge, 8, 8)
        painter.setPen(QPen(qc(Palette.CYAN, 170), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(badge.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        painter.setPen(qc(Palette.CYAN))
        painter.drawText(badge, Qt.AlignCenter, text)

    def _draw_too_small(self, painter, win_w, win_h):
        alpha = int(235 * self._too_small)
        text = "\u533a\u57df\u592a\u5c0f\uff0c\u8bf7\u91cd\u65b0\u6846\u9009"
        font = ui_font(14, QFont.DemiBold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        bw = fm.horizontalAdvance(text) + 56
        badge = QRectF((win_w - bw) / 2, win_h / 2 - 24, bw, 48)

        painter.setPen(Qt.NoPen)
        painter.setBrush(qc("#1B0E14", alpha))
        painter.drawRoundedRect(badge, 12, 12)
        painter.setPen(QPen(qc(Palette.DANGER, alpha), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(badge.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        painter.setPen(qc(Palette.DANGER, alpha))
        painter.drawText(badge, Qt.AlignCenter, text)

    def closeEvent(self, event):
        try:
            self._anim_timer.stop()
        except RuntimeError:
            pass
        logger.info("Selection window closed")
        super().closeEvent(event)
