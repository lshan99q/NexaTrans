# -*- coding: utf-8 -*-
"""
NexaTrans - Windows 11 Fluent Design system.

Single source of truth for colour, type, geometry and motion.  Colours follow
the WinUI 3 theme resources (ControlFill / TextFill / CardStroke / AccentFill
families) closely enough that the app sits comfortably next to real Windows 11
surfaces, and both **light and dark** themes are implemented.

The active theme is chosen by :func:`apply_app_theme`:

* ``system`` (default) - follow ``AppsUseLightTheme`` from the registry
* ``light`` / ``dark`` - explicit override, selectable in the Settings page

The user's real Windows accent colour is read from
``HKCU\\Software\\Microsoft\\Windows\\DWM\\AccentColor`` and lightened /
darkened into the WinUI ``AccentFillColorDefault`` variants.

Colours are stored as ``#AARRGGBB`` strings: ``QColor`` parses them directly,
and :func:`qss` converts them to ``rgba(...)`` for Qt style sheets.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontDatabase, QImage, QPainter, QPainterPath, QPixmap,
)
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene

# --------------------------------------------------------------------------
# Theme modes
# --------------------------------------------------------------------------

MODE_SYSTEM = "system"
MODE_LIGHT = "light"
MODE_DARK = "dark"

MODE_LABELS = {
    MODE_SYSTEM: "\u8ddf\u968f\u7cfb\u7edf",
    MODE_LIGHT: "\u6d45\u8272",
    MODE_DARK: "\u6df1\u8272",
}

DEFAULT_ACCENT = "#FF0078D4"          # Windows 11 default blue (#0078D4)


# --------------------------------------------------------------------------
# Colour helpers
# --------------------------------------------------------------------------


def qc(value, alpha: int | None = None) -> QColor:
    """QColor from ``#AARRGGBB`` / ``#RRGGBB`` / QColor, optional alpha override."""
    c = QColor(value) if not isinstance(value, QColor) else QColor(value)
    if alpha is not None:
        c.setAlpha(max(0, min(255, int(alpha))))
    return c


def qss(value) -> str:
    """``rgba(r, g, b, a)`` text for use inside a Qt style sheet."""
    c = qc(value)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()})"


def hexa(rgb_hex: str, alpha: int = 255) -> str:
    """``#RRGGBB`` + alpha -> ``#AARRGGBB``."""
    c = QColor(rgb_hex)
    return f"#{alpha:02X}{c.red():02X}{c.green():02X}{c.blue():02X}"


def mix(a, b, t: float) -> QColor:
    """Linear blend, ``t=0`` -> a, ``t=1`` -> b."""
    ca, cb = qc(a), qc(b)
    t = max(0.0, min(1.0, t))
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * t),
        round(ca.green() + (cb.green() - ca.green()) * t),
        round(ca.blue() + (cb.blue() - ca.blue()) * t),
        round(ca.alpha() + (cb.alpha() - ca.alpha()) * t),
    )


def lighten(color, amount: float) -> QColor:
    return mix(color, "#FFFFFFFF", amount)


def darken(color, amount: float) -> QColor:
    return mix(color, "#FF000000", amount)


def on_accent(accent) -> QColor:
    """WinUI picks black or white text for the accent button by luminance."""
    c = qc(accent)
    luma = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255.0
    return QColor("#FF000000") if luma > 0.55 else QColor("#FFFFFFFF")


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


# --------------------------------------------------------------------------
# Geometry / motion  (Fluent uses a 4px grid and 167/250/333 ms durations)
# --------------------------------------------------------------------------


class Radius:
    WINDOW = 8          # Win11 window corner
    CARD = 8            # card / layer
    CONTROL = 4         # buttons, inputs
    OVERLAY = 8
    FLYOUT = 8
    PILL = 999


class Space:
    XXS = 2
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24


class Motion:
    FAST = 167          # hover / press
    BASE = 250          # control state change
    SLOW = 333          # page transition
    PAGE = 250
    WINDOW = 250


# --------------------------------------------------------------------------
# Typography  (Segoe UI Variable, with Win10 / CJK fallbacks)
# --------------------------------------------------------------------------

TEXT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI",
                 "Microsoft YaHei UI", "Microsoft YaHei", "Arial"]
DISPLAY_FAMILIES = ["Segoe UI Variable Display", "Segoe UI Variable",
                    "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "Arial"]
MONO_FAMILIES = ["Cascadia Mono", "Consolas", "Courier New", "monospace"]


def available_family(preferred: list[str]) -> str:
    try:
        installed = set(QFontDatabase.families())
    except Exception:
        installed = set()
    for name in preferred:
        if name in installed:
            return name
    return preferred[-1] if preferred else "sans-serif"


def ui_font(size: int = 14, weight: QFont.Weight = QFont.Normal,
            mono: bool = False, display: bool = False,
            italic: bool = False) -> QFont:
    fams = MONO_FAMILIES if mono else (DISPLAY_FAMILIES if display
                                       else TEXT_FAMILIES)
    f = QFont(available_family(fams))
    f.setFamilies(fams)
    f.setPixelSize(size)
    f.setWeight(weight)
    f.setItalic(italic)
    return f


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Tokens:
    """One complete Fluent colour set."""

    name: str
    is_dark: bool

    # window / material ----------------------------------------------------
    window: str            # Mica base
    window_alt: str        # bottom of the subtle material gradient
    tint_a: str            # soft material blob (top-left)
    tint_b: str            # soft material blob (bottom-right)
    layer: str             # card background
    layer_alt: str
    layer_hover: str
    flyout: str            # menus, tooltips
    smoke: str             # full-window dimming (region selector)

    # strokes --------------------------------------------------------------
    card_stroke: str
    control_stroke: str
    control_stroke_strong: str
    divider: str

    # text -----------------------------------------------------------------
    text: str
    text_secondary: str
    text_tertiary: str
    text_disabled: str
    text_on_accent: str
    accent_text: str       # hyperlink-ish accent text

    # accent ---------------------------------------------------------------
    accent: str
    accent_hover: str
    accent_press: str
    accent_disabled: str
    accent_subtle: str     # 10% accent wash
    accent_border: str

    # semantic -------------------------------------------------------------
    success: str
    caution: str
    critical: str
    critical_hover: str

    # control fills --------------------------------------------------------
    control: str
    control_hover: str
    control_press: str
    control_disabled: str
    subtle_hover: str
    subtle_press: str
    track: str             # slider / toggle rail

    # shadow ---------------------------------------------------------------
    shadow: str
    shadow_alpha: int


def _dark_tokens(accent: str) -> Tokens:
    accent_fill = lighten(accent, 0.42) if accent != DEFAULT_ACCENT \
        else "#FF60CDFF"
    return Tokens(
        name=MODE_DARK, is_dark=True,
        window="#FF202020", window_alt="#FF1B1B1B",
        tint_a="#14FFFFFF", tint_b="#0A6EA8FF",
        layer="#FF2C2C2C", layer_alt="#FF272727", layer_hover="#FF323232",
        flyout="#FF2C2C2C", smoke="#B3050505",
        card_stroke="#14FFFFFF", control_stroke="#17FFFFFF",
        control_stroke_strong="#2EFFFFFF", divider="#14FFFFFF",
        text="#FFFFFFFF", text_secondary="#C5FFFFFF", text_tertiary="#8BFFFFFF",
        text_disabled="#5DFFFFFF", text_on_accent=on_accent(accent_fill).name(),
        accent_text=accent_fill,
        accent=accent_fill, accent_hover=lighten(accent_fill, 0.09),
        accent_press=darken(accent_fill, 0.12),
        accent_disabled="#33FFFFFF",
        accent_subtle=hexa(accent_fill, 0x1F), accent_border=hexa(accent_fill, 0x66),
        success="#FF6CCB5F", caution="#FFFCE100", critical="#FFFF99A4",
        critical_hover="#FFFFB3BB",
        control="#0FFFFFFF", control_hover="#17FFFFFF", control_press="#0AFFFFFF",
        control_disabled="#0BFFFFFF",
        subtle_hover="#0FFFFFFF", subtle_press="#08FFFFFF",
        track="#17FFFFFF",
        shadow="#FF000000", shadow_alpha=150,
    )


def _light_tokens(accent: str) -> Tokens:
    accent_fill = darken(accent, 0.16) if accent != DEFAULT_ACCENT \
        else "#FF005FB8"
    return Tokens(
        name=MODE_LIGHT, is_dark=False,
        window="#FFF3F3F3", window_alt="#FFEDEDED",
        tint_a="#2EFFFFFF", tint_b="#146EA8FF",
        layer="#B3FFFFFF", layer_alt="#E6FBFBFB", layer_hover="#FFFFFFFF",
        flyout="#FFF9F9F9", smoke="#99000000",
        card_stroke="#0F000000", control_stroke="#1A000000",
        control_stroke_strong="#29000000", divider="#14000000",
        text="#E4000000", text_secondary="#9E000000", text_tertiary="#72000000",
        text_disabled="#5C000000", text_on_accent=on_accent(accent_fill).name(),
        accent_text=accent_fill,
        accent=accent_fill, accent_hover=darken(accent_fill, 0.08),
        accent_press=darken(accent_fill, 0.16),
        accent_disabled="#5C000000",
        accent_subtle=hexa(accent_fill, 0x1A), accent_border=hexa(accent_fill, 0x59),
        success="#FF0F7B0F", caution="#FF9D5D00", critical="#FFC42B1C",
        critical_hover="#FFB02418",
        control="#B3FFFFFF", control_hover="#FFFFFFFF", control_press="#80F9F9F9",
        control_disabled="#4DF9F9F9",
        subtle_hover="#0F000000", subtle_press="#0A000000",
        track="#1F000000",
        shadow="#FF000000", shadow_alpha=60,
    )


DARK = _dark_tokens(DEFAULT_ACCENT)
LIGHT = _light_tokens(DEFAULT_ACCENT)


# --------------------------------------------------------------------------
# Active theme
# --------------------------------------------------------------------------

_active: Tokens = LIGHT
_mode: str = MODE_SYSTEM
_accent: str = DEFAULT_ACCENT


def theme() -> Tokens:
    """The tokens currently in effect. Always call this at paint time."""
    return _active


def current_mode() -> str:
    return _mode


def is_dark() -> bool:
    return _active.is_dark


def _read_registry_dword(root, path: str, name: str):
    try:
        import winreg
        with winreg.OpenKey(root, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return int(value)
    except Exception:
        return None


def _hkey_current_user():
    try:
        import winreg
        return winreg.HKEY_CURRENT_USER
    except Exception:
        return None


def system_theme_mode() -> str:
    """``light`` or ``dark`` from the Windows personalisation settings."""
    root = _hkey_current_user()
    if root is None:
        return MODE_LIGHT
    value = _read_registry_dword(
        root,
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        "AppsUseLightTheme")
    if value is None:
        return MODE_LIGHT
    return MODE_LIGHT if value else MODE_DARK


def system_accent() -> str:
    """
    The user's Windows accent colour as ``#AARRGGBB``.

    ``AccentColor`` is stored as ``0xAABBGGRR``, so the byte order is flipped.
    """
    root = _hkey_current_user()
    if root is None:
        return DEFAULT_ACCENT
    value = _read_registry_dword(root, r"SOFTWARE\Microsoft\Windows\DWM",
                                 "AccentColor")
    if value is None:
        value = _read_registry_dword(root, r"SOFTWARE\Microsoft\Windows\DWM",
                                     "ColorizationColor")
    if not value:
        return DEFAULT_ACCENT
    r, g, b = value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF
    if (r, g, b) == (0, 0, 0):
        return DEFAULT_ACCENT
    return f"#FF{r:02X}{g:02X}{b:02X}"


def resolve_mode(mode: str) -> str:
    if mode == MODE_SYSTEM:
        return system_theme_mode()
    return mode if mode in (MODE_LIGHT, MODE_DARK) else MODE_LIGHT


def set_theme_mode(mode: str, app=None, accent: str | None = None) -> Tokens:
    """Switch theme (``system`` / ``light`` / ``dark``) and restyle the app."""
    global _active, _mode, _accent, DARK, LIGHT

    _mode = mode if mode in (MODE_SYSTEM, MODE_LIGHT, MODE_DARK) else MODE_SYSTEM
    _accent = accent or system_accent()
    DARK = _dark_tokens(_accent)
    LIGHT = _light_tokens(_accent)
    _active = DARK if resolve_mode(_mode) == MODE_DARK else LIGHT

    if app is not None:
        app.setStyleSheet(global_qss())
        repaint_all(app)
    return _active


def apply_app_theme(app, mode: str = MODE_SYSTEM,
                    accent: str | None = None) -> Tokens:
    """Install the Fluent font + style sheet and select the theme."""
    app.setFont(ui_font(14))
    return set_theme_mode(mode, app, accent)


def repaint_all(app) -> None:
    """Force custom-painted widgets to pick up the new tokens."""
    for widget in app.allWidgets():
        try:
            widget.update()
        except RuntimeError:
            pass


# --------------------------------------------------------------------------
# Soft shadows (cached - safe to repaint every frame)
# --------------------------------------------------------------------------

_shadow_cache: dict = {}


def shadow_pixmap(width: int, height: int, radius: int, blur: int,
                  color="#FF000000", alpha: int = 120,
                  offset_y: int = 8) -> QPixmap:
    """
    Cached gaussian shadow for a rounded rect of ``width`` x ``height``.
    The pixmap is padded by ``blur * 2`` on every side.

    Not used by the main window: padding a translucent window to host a shadow
    leaves an invisible band around the app that swallows desktop clicks.  It
    is kept for a click-through shadow overlay window (a separate, transparent
    window placed behind the app so the padding belongs to nobody).
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
    p.drawRoundedRect(QRectF(pad, pad + offset_y, width, height), radius, radius)
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
    if len(_shadow_cache) > 32:
        _shadow_cache.clear()
    _shadow_cache[key] = pix
    return pix


def material_gradient(rect: QRectF):
    """Subtle top-to-bottom material wash used behind the window."""
    from PySide6.QtGui import QLinearGradient
    t = theme()
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    g.setColorAt(0.0, qc(t.tint_a))
    g.setColorAt(0.45, QColor(255, 255, 255, 0) if not t.is_dark
                  else QColor(0, 0, 0, 0))
    g.setColorAt(1.0, qc(t.tint_b))
    return g


# --------------------------------------------------------------------------
# Global style sheet (menus, tooltips, scrollbars, inputs, labels, dialogs)
# --------------------------------------------------------------------------

# Semantic label roles - set with widget.setProperty("role", "...") so that a
# theme switch restyles everything through the app style sheet alone.
_ROLE_QSS = """
QLabel[role="caption"]   {{ color: {tertiary}; font-size: 12px; }}
QLabel[role="secondary"] {{ color: {secondary}; font-size: 12px; }}
QLabel[role="body"]      {{ color: {text}; font-size: 14px; }}
QLabel[role="strong"]    {{ color: {text}; font-size: 14px; font-weight: 600; }}
QLabel[role="subtitle"]  {{ color: {text}; font-size: 18px; font-weight: 600; }}
QLabel[role="title"]     {{ color: {text}; font-size: 24px; font-weight: 600; }}
QLabel[role="metric"]    {{ color: {text}; font-size: 20px; font-weight: 600; }}
QLabel[role="accent"]    {{ color: {accent_text}; font-size: 12px; font-weight: 600; }}
QLabel[role="mono"]      {{ color: {tertiary}; font-size: 12px; }}
QLabel[role="window-title"] {{ color: {text}; font-size: 12px; }}
"""


def global_qss() -> str:
    t = theme()

    return f"""
    /* NOTE: no font-family/font-size here - a blanket rule would override
       QWidget.setFont() on the custom-painted controls.  The base font comes
       from QApplication.setFont(); roles below define the type ramp. */
    QWidget {{
        color: {qss(t.text)};
    }}

    {_ROLE_QSS.format(text=qss(t.text), secondary=qss(t.text_secondary),
                      tertiary=qss(t.text_tertiary), accent_text=qss(t.accent_text))}

    /* ---- tooltips / menus (Win11 flyout) ---- */
    QToolTip {{
        background: {qss(t.flyout)};
        color: {qss(t.text)};
        border: 1px solid {qss(t.card_stroke)};
        border-radius: {Radius.FLYOUT}px;
        padding: 6px 10px;
        font-size: 12px;
    }}
    QMenu {{
        background: {qss(t.flyout)};
        color: {qss(t.text)};
        border: 1px solid {qss(t.card_stroke)};
        border-radius: {Radius.FLYOUT}px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 8px 26px 8px 12px;
        border-radius: 4px;
        font-size: 13px;
    }}
    QMenu::item:selected {{ background: {qss(t.subtle_hover)}; }}
    QMenu::item:disabled {{ color: {qss(t.text_disabled)}; }}
    QMenu::separator {{
        height: 1px; background: {qss(t.divider)}; margin: 4px 8px;
    }}

    /* ---- scrollbars (Win11: thin, pill thumb, no arrows) ---- */
    QScrollBar:vertical {{
        background: transparent; width: 14px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {qss(t.control_stroke_strong)};
        min-height: 28px; border-radius: 3px; margin: 2px 4px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {qss(t.text_tertiary)}; }}
    QScrollBar::handle:vertical:pressed {{ background: {qss(t.text_secondary)}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    QScrollBar:horizontal {{ height: 0px; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}

    /* ---- inputs ---- */
    QLineEdit {{
        background: {qss(t.control)};
        color: {qss(t.text)};
        border: 1px solid {qss(t.control_stroke)};
        border-bottom: 1px solid {qss(t.control_stroke_strong)};
        border-radius: {Radius.CONTROL}px;
        padding: 8px 11px;
        font-size: 13px;
        selection-background-color: {qss(t.accent)};
    }}
    QLineEdit:hover {{ background: {qss(t.control_hover)}; }}
    QLineEdit:focus {{
        border-color: {qss(t.control_stroke_strong)};
        border-bottom: 2px solid {qss(t.accent)};
        padding-bottom: 7px;
    }}
    QLineEdit:disabled {{ color: {qss(t.text_disabled)}; }}

    QComboBox {{
        background: {qss(t.control)};
        color: {qss(t.text)};
        border: 1px solid {qss(t.control_stroke)};
        border-bottom: 1px solid {qss(t.control_stroke_strong)};
        border-radius: {Radius.CONTROL}px;
        padding: 5px 6px 5px 10px;
        font-size: 13px;
    }}
    QComboBox:hover {{ background: {qss(t.control_hover)}; }}
    QComboBox:on {{ background: {qss(t.control_press)}; }}
    QComboBox:disabled {{ color: {qss(t.text_disabled)}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox::down-arrow {{
        image: none;
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {qss(t.text_secondary)};
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        background: {qss(t.flyout)};
        color: {qss(t.text)};
        border: 1px solid {qss(t.card_stroke)};
        border-radius: {Radius.FLYOUT}px;
        padding: 4px;
        outline: none;
        selection-background-color: {qss(t.subtle_hover)};
    }}

    /* ---- dialogs ---- */
    QMessageBox {{ background: {qss(t.window)}; }}
    QMessageBox QLabel {{ color: {qss(t.text)}; font-size: 14px; }}
    QMessageBox QPushButton {{
        background: {qss(t.control)}; color: {qss(t.text)};
        border: 1px solid {qss(t.control_stroke)};
        border-radius: {Radius.CONTROL}px;
        padding: 6px 20px; min-width: 72px; font-size: 13px;
    }}
    QMessageBox QPushButton:hover {{ background: {qss(t.control_hover)}; }}
    """
