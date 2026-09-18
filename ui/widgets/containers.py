# -*- coding: utf-8 -*-
"""
NexaTrans - Fluent (Windows 11) containers.

* ``Card``         - Win11 "settings card": layer fill, 1px stroke, 8px corners
* ``LogoMark``     - flat accent app tile
* ``TitleBar``     - Win11 caption bar (icon + title + caption buttons)
* ``FluentStack``  - WinUI page transition (slide up + fade, 250 ms)
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen, QRegion,
)
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from ui.theme import (
    Motion, Radius, Space, mix, qc, rounded_path, theme, ui_font,
)
from ui.widgets.anim import animate, stop_animation
from ui.widgets.buttons import CaptionButton


# --------------------------------------------------------------------------
# Logo
# --------------------------------------------------------------------------


def paint_logo_mark(painter: QPainter, rect: QRectF) -> None:
    """Flat accent app tile with a contrasting 'N' (shared with the tray)."""
    t = theme()
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = rounded_path(rect, rect.width() * 0.22)
    painter.setPen(Qt.NoPen)
    painter.setBrush(qc(t.accent))
    painter.drawPath(path)

    f = ui_font(int(rect.width() * 0.66), QFont.Bold, display=True)
    painter.setFont(f)
    painter.setPen(qc(t.text_on_accent))
    painter.drawText(rect, Qt.AlignCenter, "N")


class LogoMark(QWidget):
    def __init__(self, size: int = 20, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_logo_mark(painter, QRectF(self.rect()))


# --------------------------------------------------------------------------
# Card
# --------------------------------------------------------------------------


class Card(QFrame):
    """Win11 settings card: optional header row plus a body layout."""

    def __init__(self, title: str = "", subtitle: str = "",
                 parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(Space.LG, Space.MD + 2, Space.LG, Space.MD + 2)
        outer.setSpacing(Space.MD)

        self.header: QHBoxLayout | None = None
        if title:
            header = QHBoxLayout()
            header.setSpacing(Space.MD)
            column = QVBoxLayout()
            column.setSpacing(1)
            t = QLabel(title)
            t.setProperty("role", "strong")
            column.addWidget(t)
            if subtitle:
                s = QLabel(subtitle)
                s.setProperty("role", "caption")
                s.setWordWrap(True)
                column.addWidget(s)
            header.addLayout(column, 1)
            self.header = header
            outer.addLayout(header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(Space.SM)
        outer.addLayout(self.body)

    def add(self, item) -> None:
        if isinstance(item, QWidget):
            self.body.addWidget(item)
        else:
            self.body.addLayout(item)

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = Radius.CARD

        painter.setPen(Qt.NoPen)
        painter.setBrush(qc(t.layer))
        painter.drawPath(rounded_path(rect, radius))

        # very subtle material sheen so the card is not perfectly flat
        painter.save()
        painter.setClipPath(rounded_path(rect, radius))
        sheen = QColor(255, 255, 255, 10 if t.is_dark else 120)
        painter.setBrush(sheen)
        painter.drawRect(QRectF(rect.left(), rect.top(), rect.width(),
                                rect.height() * 0.5))
        painter.restore()

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(qc(t.card_stroke), 1.0))
        painter.drawPath(rounded_path(rect.adjusted(0.5, 0.5, -0.5, -0.5),
                                      radius - 0.5))


class SettingsRow(QWidget):
    """A Win11 settings row: title + description on the left, control right."""

    def __init__(self, title: str, description: str = "", control: QWidget | None = None,
                 parent=None):
        super().__init__(parent)
        self.setMinimumHeight(56)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, Space.SM, 0, Space.SM)
        layout.setSpacing(Space.LG)

        column = QVBoxLayout()
        column.setSpacing(1)
        label = QLabel(title)
        label.setProperty("role", "body")
        column.addWidget(label)
        if description:
            desc = QLabel(description)
            desc.setProperty("role", "caption")
            desc.setWordWrap(True)
            column.addWidget(desc)
        layout.addLayout(column, 1)

        if control is not None:
            layout.addWidget(control, 0, Qt.AlignVCenter)

        self.title_label = label
        self.control = control


class Divider(QFrame):
    """1px Win11 divider line."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), qc(theme().divider))


# --------------------------------------------------------------------------
# Title bar
# --------------------------------------------------------------------------


class TitleBar(QWidget):
    """Windows 11 caption bar: app icon, title, caption buttons."""

    minimize_requested = Signal()
    close_requested = Signal()

    HEIGHT = 32

    def __init__(self, title: str = "NexaTrans", subtitle: str = "",
                 parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        self._drag_offset: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(Space.MD, 0, 0, 0)
        layout.setSpacing(Space.SM)

        layout.addWidget(LogoMark(16), 0, Qt.AlignVCenter)

        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "window-title")
        layout.addWidget(self.title_label, 0, Qt.AlignVCenter)

        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setProperty("role", "caption")
            layout.addWidget(self.subtitle_label, 0, Qt.AlignVCenter)

        layout.addStretch(1)

        self.min_btn = CaptionButton(CaptionButton.MINIMIZE)
        self.min_btn.setToolTip("\u6700\u5c0f\u5316\u5230\u6258\u76d8")
        self.min_btn.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self.min_btn)

        self.close_btn = CaptionButton(CaptionButton.CLOSE)
        self.close_btn.setToolTip("\u5173\u95ed")
        self.close_btn.set_top_right_round(0)
        self.close_btn.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.close_btn)

    # -- window dragging ---------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            window = self.window()
            self._drag_offset = (event.globalPosition().toPoint()
                                 - window.frameGeometry().topLeft())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint()
                               - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # fixed-size utility window: nothing to maximise
        event.accept()


# --------------------------------------------------------------------------
# Page stack
# --------------------------------------------------------------------------


class FluentStack(QWidget):
    """
    WinUI page host: the incoming page fades in while sliding up slightly,
    the outgoing page fades out.  Matches the Fluent "page transition".
    """

    page_changed = Signal(int)

    OFFSET = 22          # px the new page rises from

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: list[QWidget] = []
        self._index = -1

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

    @staticmethod
    def _opacity_effect(widget: QWidget, value: float) -> QGraphicsOpacityEffect:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(value)
        return effect

    def setCurrentIndex(self, index: int, animate_transition: bool = True) -> None:
        if not (0 <= index < len(self._pages)) or index == self._index:
            return
        previous = self.currentWidget()
        target = self._pages[index]
        self._index = index

        target.setGeometry(0, 0, self.width(), self.height())
        target.show()
        target.raise_()

        if previous is None or not animate_transition:
            if previous is not None:
                previous.hide()
                previous.setGraphicsEffect(None)
            target.move(0, 0)
            target.setGraphicsEffect(None)
            self.page_changed.emit(index)
            return

        # incoming: fade in + slide up
        effect = self._opacity_effect(target, 0.0)
        target.move(0, self.OFFSET)
        animate(self, "page_in_y", float(self.OFFSET), 0.0,
                lambda v: target.move(0, int(v)),
                duration=Motion.PAGE, easing=QEasingCurve.OutCubic)
        animate(self, "page_in_a", 0.0, 1.0,
                lambda v: effect.setOpacity(float(v)),
                duration=Motion.PAGE, easing=QEasingCurve.OutCubic,
                finished=lambda: target.setGraphicsEffect(None))

        # outgoing: fade out
        out = self._opacity_effect(previous, 1.0)
        animate(self, "page_out_a", 1.0, 0.0,
                lambda v: out.setOpacity(float(v)),
                duration=Motion.FAST, easing=QEasingCurve.InCubic,
                finished=lambda: (previous.hide(),
                                  previous.setGraphicsEffect(None),
                                  previous.move(0, 0)))

        self.page_changed.emit(index)
