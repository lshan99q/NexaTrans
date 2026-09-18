# -*- coding: utf-8 -*-
"""
NexaTrans - layout containers: cards, logo, title bar and the animated
page stack used to slide between the "home" and "settings" views.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QPoint, QRectF, Qt, Signal,
)
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPen,
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from ui.theme import (
    Motion, Palette, Radius, Space, mix, qc, radial_highlight, rounded_path,
    ui_font,
)
from ui.widgets.anim import animate
from ui.widgets.buttons import IconButton


def paint_logo_mark(painter: QPainter, rect: QRectF) -> None:
    """Paint the Aurora gradient mark into ``rect`` (shared by widget + tray)."""
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = rounded_path(rect, rect.width() * 0.28)

    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, qc(Palette.CYAN))
    grad.setColorAt(0.55, qc(Palette.SKY))
    grad.setColorAt(1.0, qc(Palette.INDIGO))
    painter.setPen(Qt.NoPen)
    painter.setBrush(grad)
    painter.drawPath(path)

    sheen = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    sheen.setColorAt(0.0, QColor(255, 255, 255, 70))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.setBrush(sheen)
    painter.drawPath(path)

    f = ui_font(int(rect.width() * 0.62), QFont.Black)
    f.setItalic(True)
    painter.setFont(f)
    painter.setPen(qc("#04121C"))
    painter.drawText(rect, Qt.AlignCenter, "N")


class LogoMark(QWidget):
    """The gradient app mark."""

    def __init__(self, size: int = 26, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)

    def paint(self, painter: QPainter, rect: QRectF) -> None:
        paint_logo_mark(painter, rect)

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_logo_mark(painter, QRectF(self.rect()))


class Card(QFrame):
    """Rounded glass surface with an optional icon + title header."""

    def __init__(self, title: str = "", subtitle: str = "",
                 icon: str = "", accent: str | None = None, parent=None):
        super().__init__(parent)
        self._accent = accent
        self._radius = Radius.CARD
        self.setAttribute(Qt.WA_StyledBackground, False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(Space.LG, Space.LG - 2, Space.LG, Space.LG - 2)
        outer.setSpacing(Space.MD)

        if title:
            header = QHBoxLayout()
            header.setSpacing(Space.SM)
            if icon:
                glyph = QLabel(icon)
                glyph.setFont(ui_font(13))
                glyph.setStyleSheet(
                    f"color: {accent or Palette.SKY}; background: transparent;")
                glyph.setFixedWidth(18)
                glyph.setAlignment(Qt.AlignCenter)
                header.addWidget(glyph, 0, Qt.AlignTop)
            text_col = QVBoxLayout()
            text_col.setSpacing(1)
            t = QLabel(title)
            t.setFont(ui_font(13, QFont.DemiBold))
            t.setStyleSheet(f"color: {Palette.TEXT}; background: transparent;")
            text_col.addWidget(t)
            if subtitle:
                s = QLabel(subtitle)
                s.setFont(ui_font(11))
                s.setStyleSheet(
                    f"color: {Palette.TEXT_DIM}; background: transparent;")
                text_col.addWidget(s)
            header.addLayout(text_col, 1)
            self.header = header
            outer.addLayout(header)
        else:
            self.header = None

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(Space.SM)
        outer.addLayout(self.body)

    def add(self, item) -> None:
        if isinstance(item, QWidget):
            self.body.addWidget(item)
        else:
            self.body.addLayout(item)

    def set_accent(self, accent: str | None) -> None:
        self._accent = accent
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, self._radius)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, qc(Palette.SURFACE))
        grad.setColorAt(1.0, qc(Palette.SURFACE_2))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawPath(path)

        painter.save()
        painter.setClipPath(path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(radial_highlight(rect, Palette.SKY, 26))
        painter.drawPath(path)
        # top hairline highlight
        hl = QLinearGradient(rect.topLeft(), rect.topRight())
        hl.setColorAt(0.0, QColor(255, 255, 255, 0))
        hl.setColorAt(0.35, QColor(255, 255, 255, 26))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(hl)
        painter.drawRect(QRectF(rect.left(), rect.top(), rect.width(), 1.0))
        painter.restore()

        border = qc(self._accent) if self._accent else qc(Palette.BORDER)
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(rounded_path(rect.adjusted(0.5, 0.5, -0.5, -0.5),
                                      self._radius - 1))


class TitleBar(QWidget):
    """Frameless-window title bar: logo, wordmark, version chip, controls."""

    minimize_requested = Signal()
    close_requested = Signal()

    def __init__(self, title: str = "NexaTrans", version: str = "v2.0",
                 parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.LG, Space.SM, Space.MD, 0)
        layout.setSpacing(Space.SM)

        layout.addWidget(LogoMark(26))
        self.title_label = QLabel(title)
        self.title_label.setFont(ui_font(15, QFont.Bold))
        self.title_label.setStyleSheet(
            f"color: {Palette.TEXT}; background: transparent;")
        layout.addWidget(self.title_label)

        self.version_chip = QLabel(version)
        self.version_chip.setFont(ui_font(10, QFont.DemiBold))
        self.version_chip.setStyleSheet(
            f"color: {Palette.SKY}; background: {qc(Palette.SKY, 26).name(QColor.HexArgb)};"
            f" border: 1px solid {qc(Palette.SKY, 60).name(QColor.HexArgb)};"
            f" border-radius: 7px; padding: 2px 7px;")
        layout.addWidget(self.version_chip, 0, Qt.AlignVCenter)

        layout.addStretch(1)

        self.min_btn = IconButton("\u2013", 28)
        self.min_btn.setToolTip("\u6700\u5c0f\u5316\u5230\u6258\u76d8")
        self.min_btn.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self.min_btn)

        self.close_btn = IconButton("\u2715", 28, tone="danger")
        self.close_btn.set_hover_color(Palette.DANGER_2)
        self.close_btn.setToolTip("\u5173\u95ed")
        self.close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.close_btn)

    # -- window dragging ---------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            window = self.window()
            self._drag_offset = event.globalPosition().toPoint() - \
                window.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(
                event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)


class SlideStack(QWidget):
    """Tiny carousel: pages slide horizontally with an eased transition."""

    page_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: list[QWidget] = []
        self._index = -1
        self._animating = False

    def addWidget(self, widget: QWidget) -> QWidget:
        widget.setParent(self)
        widget.setGeometry(0, 0, self.width(), self.height())
        widget.hide()
        self._pages.append(widget)
        if self._index < 0:
            self._index = 0
            widget.show()
        return widget

    def count(self) -> int:
        return len(self._pages)

    def currentIndex(self) -> int:
        return self._index

    def currentWidget(self) -> QWidget | None:
        if 0 <= self._index < len(self._pages):
            return self._pages[self._index]
        return None

    def resizeEvent(self, event):
        for page in self._pages:
            page.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def setCurrentIndex(self, index: int, animate_transition: bool = True) -> None:
        if not (0 <= index < len(self._pages)) or index == self._index:
            return
        previous = self.currentWidget()
        target = self._pages[index]
        self._index = index

        width = max(1, self.width())
        target.setGeometry(0, 0, width, self.height())
        target.move(width, 0)
        target.show()
        target.raise_()

        if previous is None or not animate_transition:
            if previous is not None:
                previous.hide()
                previous.move(0, 0)
            target.move(0, 0)
            self.page_changed.emit(index)
            return

        direction = 1 if index > self._pages.index(previous) else -1
        start_target = direction * width
        target.move(start_target, 0)

        self._animating = True

        def _finish():
            self._animating = False
            previous.hide()
            previous.move(0, 0)
            target.move(0, 0)
            self.page_changed.emit(index)

        animate(self, "page_in", start_target, 0,
                lambda v: target.move(int(v), 0),
                duration=Motion.PAGE, easing=QEasingCurve.OutCubic,
                finished=_finish)
        animate(self, "page_out", 0, -start_target,
                lambda v: previous.move(int(v), 0),
                duration=Motion.PAGE, easing=QEasingCurve.OutCubic)
