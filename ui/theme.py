# -*- coding: utf-8 -*-
"""
NexaTrans - Design System  (UI v2.0 "Aurora")

Single source of truth for the application look & feel:
colors, typography, radii, spacing, shared QSS and small painting helpers.

Nothing in here touches business logic - it is pure presentation.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter,
    QPainterPath, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------


class Palette:
    """Dark "aurora" palette - deep navy surfaces with cyan/indigo accents."""

    # window / surfaces -----------------------------------------------------
    WINDOW = "#070A11"          # outermost rounded panel
    WINDOW_2 = "#0B111D"        # panel gradient end
    SURFACE = "#111827"         # card background
    SURFACE_2 = "#0D1420"       # card background (gradient end)
    SURFACE_HI = "#16203400"    # card highlight (transparent)
    INSET = "#0A0F19"           # inputs / wells
    HOVER = "#182238"

    # strokes ---------------------------------------------------------------
    BORDER = "#1E2A3E"
    BORDER_SOFT = "#182130"
    BORDER_HI = "#2B3B57"

    # text ------------------------------------------------------------------
    TEXT = "#E8EFFA"
    TEXT_MUTED = "#93A4C0"
    TEXT_DIM = "#5D6C86"
    TEXT_ON_ACCENT = "#04121C"

    # accents ---------------------------------------------------------------
    CYAN = "#22D3EE"
    SKY = "#38BDF8"
    INDIGO = "#6366F1"
    VIOLET = "#8B5CF6"
    SUCCESS = "#34D399"
    WARN = "#FBBF24"
    DANGER = "#FB7185"
    DANGER_2 = "#F43F5E"

    # semantic aliases ------------------------------------------------------
    ACCENT = CYAN
    ACCENT_2 = INDIGO


# --------------------------------------------------------------------------
# Typography
# --------------------------------------------------------------------------

UI_FAMILIES = ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI",
               "Segoe UI Symbol", "Arial"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "Courier New", "monospace"]


def available_family(preferred: list[str]) -> str:
    """Return the first font family actually installed on this machine."""
    try:
        installed = set(QFontDatabase.families())
    except Exception:
        installed = set()
    for name in preferred:
        if name in installed:
            return name
    return preferred[-1] if preferred else "sans-serif"


def ui_font(size: int = 13, weight: QFont.Weight = QFont.Normal,
            mono: bool = False, italic: bool = False) -> QFont:
    fam = MONO_FAMILIES if mono else UI_FAMILIES
    f = QFont(available_family(fam))
    f.setFamilies(fam)
    f.setPixelSize(size)
    f.setWeight(weight)
    f.setItalic(italic)
    try:
        f.setHintingPreference(QFont.PreferFullHinting)
    except Exception:
        pass
    return f


# --------------------------------------------------------------------------
# Geometry / motion
# --------------------------------------------------------------------------

class Radius:
    WINDOW = 16
    CARD = 14
    BUTTON = 12
    PILL = 999
    INPUT = 10


class Space:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 22


class Motion:
    """Durations (ms) and easing presets used across the app."""
    FAST = 140
    BASE = 220
    SLOW = 320
    PAGE = 300
    WINDOW = 300


# --------------------------------------------------------------------------
# Color helpers
# --------------------------------------------------------------------------


def qc(value, alpha: int | None = None) -> QColor:
    """Build a QColor from a hex string / QColor, optionally overriding alpha."""
    c = QColor(value) if not isinstance(value, QColor) else QColor(value)
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def mix(a, b, t: float) -> QColor:
    """Linear interpolation between two colors (t in 0..1)."""
    ca, cb = qc(a), qc(b)
    return QColor(
        int(ca.red() + (cb.red() - ca.red()) * t),
        int(ca.green() + (cb.green() - ca.green()) * t),
        int(ca.blue() + (cb.blue() - ca.blue()) * t),
        int(ca.alpha() + (cb.alpha() - ca.alpha()) * t),
    )


def linear_gradient(rect: QRectF, start, end, angle: str = "h") -> QLinearGradient:
    if angle == "h":
        g = QLinearGradient(rect.topLeft(), rect.topRight())
    elif angle == "v":
        g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    else:  # diagonal
        g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    g.setColorAt(0.0, qc(start))
    g.setColorAt(1.0, qc(end))
    return g


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


# --------------------------------------------------------------------------
# Soft shadows (cached blurred pixmaps - cheap enough to repaint every frame)
# --------------------------------------------------------------------------

_shadow_cache: dict = {}


def shadow_pixmap(width: int, height: int, radius: int, blur: int,
                  color=Palette.WINDOW, alpha: int = 170,
                  offset_y: int = 8) -> QPixmap:
    """
    Render a cached, gaussian-blurred drop shadow for a rounded rect of
    ``width`` x ``height``.  The returned pixmap is padded by ``blur*2`` on
    every side so the shadow has room to fade out.
    """
    key = (width, height, radius, blur, str(color), alpha, offset_y)
    cached = _shadow_cache.get(key)
    if cached is not None:
        return cached

    pad = blur * 2
    w, h = width + pad * 2, height + pad * 2

    src = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    src.fill(Qt.transparent)
    p = QPainter(src)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(qc(color, alpha))
    p.drawRoundedRect(
        QRectF(pad, pad + offset_y, width, height), radius, radius
    )
    p.end()

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(src))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(blur)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    out = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p2 = QPainter(out)
    p2.setRenderHint(QPainter.Antialiasing, True)
    scene.render(p2, QRectF(out.rect()), QRectF(src.rect()))
    p2.end()

    pix = QPixmap.fromImage(out)
    if len(_shadow_cache) > 24:          # keep the cache bounded
        _shadow_cache.clear()
    _shadow_cache[key] = pix
    return pix


def glow_pixmap(size: int, color, alpha: int = 120, blur: int = 18) -> QPixmap:
    """Circular soft glow, e.g. behind the primary action button."""
    key = ("glow", size, str(color), alpha, blur)
    cached = _shadow_cache.get(key)
    if cached is not None:
        return cached

    pad = blur * 2
    w = size + pad * 2
    src = QImage(w, w, QImage.Format_ARGB32_Premultiplied)
    src.fill(Qt.transparent)
    p = QPainter(src)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(qc(color, alpha))
    p.drawEllipse(QRectF(pad, pad, size, size))
    p.end()

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(src))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(blur)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    out = QImage(w, w, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    p2 = QPainter(out)
    p2.setRenderHint(QPainter.Antialiasing, True)
    scene.render(p2, QRectF(out.rect()), QRectF(src.rect()))
    p2.end()

    pix = QPixmap.fromImage(out)
    _shadow_cache[key] = pix
    return pix


def radial_highlight(rect: QRectF, color, alpha: int = 60) -> QRadialGradient:
    """Top-left radial sheen used on cards and the hero panel."""
    center = QPointF(rect.left() + rect.width() * 0.18,
                     rect.top() + rect.height() * 0.05)
    g = QRadialGradient(center, max(rect.width(), rect.height()) * 0.95)
    g.setColorAt(0.0, qc(color, alpha))
    g.setColorAt(1.0, qc(color, 0))
    return g


# --------------------------------------------------------------------------
# Global stylesheet (menus, tooltips, scrollbars, inputs, dialogs)
# --------------------------------------------------------------------------

def global_qss() -> str:
    fam = ", ".join(f'"{f}"' for f in UI_FAMILIES[:3])
    return f"""
    QToolTip {{
        background: {Palette.SURFACE};
        color: {Palette.TEXT};
        border: 1px solid {Palette.BORDER_HI};
        border-radius: 6px;
        padding: 5px 8px;
    }}

    QMenu {{
        background: {Palette.SURFACE};
        color: {Palette.TEXT};
        border: 1px solid {Palette.BORDER};
        border-radius: 10px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 22px 7px 14px;
        border-radius: 7px;
        font-family: {fam};
        font-size: 12px;
    }}
    QMenu::item:selected {{ background: {Palette.HOVER}; color: #FFFFFF; }}
    QMenu::item:disabled {{ color: {Palette.TEXT_DIM}; }}
    QMenu::separator {{
        height: 1px; background: {Palette.BORDER};
        margin: 5px 8px;
    }}

    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px 0 2px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {Palette.BORDER_HI}; min-height: 30px;
        border-radius: 4px; margin: 0 2px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {Palette.SKY}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{ height: 0px; }}

    QLineEdit {{
        background: {Palette.INSET};
        color: {Palette.TEXT};
        border: 1px solid {Palette.BORDER};
        border-radius: {Radius.INPUT}px;
        padding: 9px 12px;
        font-family: {fam};
        font-size: 12px;
        selection-background-color: {Palette.INDIGO};
    }}
    QLineEdit:hover {{ border-color: {Palette.BORDER_HI}; }}
    QLineEdit:focus {{
        border-color: {Palette.CYAN};
        background: #0C1421;
    }}
    QLineEdit::placeholder {{ color: {Palette.TEXT_DIM}; }}

    QComboBox {{
        background: {Palette.INSET};
        color: {Palette.SKY};
        border: 1px solid {Palette.BORDER};
        border-radius: 8px;
        padding: 4px 6px 4px 8px;
        font-family: {fam};
        font-size: 11px;
    }}
    QComboBox:hover {{ border-color: {Palette.BORDER_HI}; color: {Palette.CYAN}; }}
    QComboBox::drop-down {{ border: none; width: 16px; }}
    QComboBox::down-arrow {{
        image: none;
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {Palette.TEXT_MUTED};
        margin-right: 5px;
    }}
    QComboBox:hover::down-arrow {{
        border-top: 5px solid {Palette.CYAN};
    }}
    QComboBox QAbstractItemView {{
        background: {Palette.SURFACE};
        color: {Palette.TEXT};
        border: 1px solid {Palette.BORDER};
        border-radius: 8px;
        padding: 4px;
        outline: none;
        selection-background-color: {Palette.HOVER};
    }}

    QMessageBox {{ background: {Palette.SURFACE}; }}
    QMessageBox QLabel {{
        color: {Palette.TEXT}; font-family: {fam}; font-size: 13px;
    }}
    QMessageBox QPushButton {{
        background: {Palette.HOVER}; color: {Palette.TEXT};
        border: 1px solid {Palette.BORDER_HI}; border-radius: 8px;
        padding: 6px 18px; min-width: 64px;
        font-family: {fam}; font-size: 12px;
    }}
    QMessageBox QPushButton:hover {{
        background: {Palette.INDIGO}; border-color: {Palette.SKY};
    }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    """


def apply_app_theme(app) -> None:
    """Install the global font + stylesheet on a QApplication instance."""
    app.setFont(ui_font(13))
    app.setStyleSheet(global_qss())
