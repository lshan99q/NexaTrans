# -*- coding: utf-8 -*-
"""
NexaTrans - Main Window  (UI v2.0 "Aurora")

Frameless translucent window with a custom title bar, an animated hero
action panel, live metric chips, toast notifications and a slide-in
settings page.

Business logic (pipeline control, hotkeys, tray, config persistence) is
unchanged from v1.2 - only the presentation layer was rebuilt.
"""

import ctypes
import logging
import os
import sys

from PySide6.QtCore import (
    QAbstractNativeEventFilter, QEasingCurve, QRectF, Qt, QTimer,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QMessageBox, QScrollArea, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from config.config_manager import ConfigManager
from ui.selector_window import SelectorWindow
from ui.region_overlay import RegionOverlay
from ui.theme import (
    Motion, Palette, Radius, Space, apply_app_theme, qc, rounded_path,
    shadow_pixmap, ui_font,
)
from ui.widgets.anim import animate
from ui.widgets.buttons import GlowButton, IconButton
from ui.widgets.containers import (
    Card, SlideStack, TitleBar, paint_logo_mark,
)
from ui.widgets.feedback import (
    SliderRow, StatChip, StatusPill, Toast, ToggleRow,
)

logger = logging.getLogger("NexaTrans.MainWindow")

_FROZEN = getattr(sys, "frozen", False)
ENV_PATH = os.path.join(
    os.path.dirname(sys.executable) if _FROZEN else os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))),
    ".env"
)

# ---- Windows API hotkey constants ----
MOD_ALT = 0x0001
MOD_CTRL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312


class _WinMSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_ulonglong),
        ("lParam", ctypes.c_longlong),
        ("time", ctypes.c_uint),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


DEFAULT_HOTKEY_MOD = "Ctrl+Shift"
DEFAULT_HOTKEY_KEY = "T"

MOD_MAP = {
    "Ctrl": MOD_CTRL,
    "Alt": MOD_ALT,
    "Shift": MOD_SHIFT,
    "Ctrl+Shift": MOD_CTRL | MOD_SHIFT,
    "Ctrl+Alt": MOD_CTRL | MOD_ALT,
    "Alt+Shift": MOD_ALT | MOD_SHIFT,
    "Ctrl+Alt+Shift": MOD_CTRL | MOD_ALT | MOD_SHIFT,
}

HOTKEY_KEYS = [chr(i) for i in range(ord("A"), ord("Z") + 1)] + \
              [chr(i) for i in range(ord("0"), ord("9") + 1)] + \
              ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9",
               "F10", "F11", "F12"]

# ---- window geometry ----
WINDOW_W = 452
HOME_H = 490
SHADOW_PAD = 20
APP_VERSION = "v1.2.1"


def _read_env_key():
    try:
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        return line.strip().split("=", 1)[1].strip().strip("\"'")
    except Exception:
        pass
    return ""


def _write_env_key(key: str):
    try:
        lines = []
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("DEEPSEEK_API_KEY="):
                lines[i] = f"DEEPSEEK_API_KEY={key}\n"
                found = True
                break
        if not found:
            lines.append(f"DEEPSEEK_API_KEY={key}\n")
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception:
        pass


def _make_tray_icon():
    """Multi-resolution tray icon built from the Aurora logo mark."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        paint_logo_mark(p, QRectF(0.5, 0.5, size - 1, size - 1))
        p.end()
        icon.addPixmap(pix)
    return icon


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, eventType, message):
        if eventType == "windows_generic_MSG":
            try:
                ptr = ctypes.c_void_p(int(message))
                msg = ctypes.cast(ptr, ctypes.POINTER(_WinMSG)).contents
                if msg.message == WM_HOTKEY:
                    self._callback()
                    return True, 0
            except Exception:
                pass
        return False, 0


class HeroCard(Card):
    """Primary action card; paints a sweeping light band while running."""

    def __init__(self, parent=None):
        super().__init__(accent=Palette.SKY, parent=parent)
        self._phase = 0.0
        self._active = False
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def set_active(self, active: bool) -> None:
        self._active = bool(active)
        if self._active:
            self._timer.start()
        else:
            self._timer.stop()
            self._phase = 0.0
        self.update()

    def _tick(self):
        self._phase = (self._phase + 0.007) % 1.0
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = rounded_path(rect, self._radius)
        painter.setClipPath(path)
        x = rect.width() * (self._phase * 1.7 - 0.35)
        band = QLinearGradient(x - 110, rect.top(), x + 110, rect.bottom())
        band.setColorAt(0.0, qc(Palette.CYAN, 0))
        band.setColorAt(0.5, qc(Palette.CYAN, 30))
        band.setColorAt(1.0, qc(Palette.CYAN, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(band)
        painter.drawPath(path)


class Capsule(QWidget):
    """Rounded translucent container used for the hotkey selectors."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(qc(Palette.BORDER), 1))
        painter.setBrush(qc(Palette.INSET, 190))
        painter.drawRoundedRect(rect, 10, 10)


class MainWindow(QWidget):

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self._selector = None
        self._overlay = RegionOverlay()
        self._pipeline = None
        self._fps_timer = QTimer()
        self._fps_timer.timeout.connect(self._update_status)
        self._settings_visible = False
        self._quitting = False
        self._hotkey_id = 1
        self._hotkey_registered = False
        self._once_busy = False
        self._once_display_timer = QTimer()
        self._once_display_timer.setSingleShot(True)
        self._once_display_timer.timeout.connect(self._clear_once_overlay)
        self._pipeline_inited = False
        self._once_was_running = False
        self._settings_built = False

        app = QApplication.instance()
        if app is not None:
            apply_app_theme(app)

        self._setup_ui()
        self._setup_tray()
        self._load_config()
        self._load_region()
        self._hotkey_filter = HotkeyFilter(self._on_once_translate)
        if app:
            app.installNativeEventFilter(self._hotkey_filter)
        QTimer.singleShot(500, self._register_hotkey)
        QTimer.singleShot(60, lambda: self._fade_in(self))
        logger.info("MainWindow v2.0 (Aurora UI) ready")

    # ==================================================================
    # window shell
    # ==================================================================

    def _setup_ui(self):
        self.setWindowTitle("NexaTrans")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(WINDOW_W + SHADOW_PAD * 2)
        self.setFixedHeight(HOME_H + SHADOW_PAD * 2)

        root = QVBoxLayout(self)
        root.setContentsMargins(SHADOW_PAD, SHADOW_PAD,
                                SHADOW_PAD, SHADOW_PAD)
        root.setSpacing(0)

        self.shell = QWidget(self)
        self.shell.setAttribute(Qt.WA_StyledBackground, False)
        root.addWidget(self.shell)

        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.title_bar = TitleBar("NexaTrans", APP_VERSION)
        self.title_bar.minimize_requested.connect(self._hide_to_tray)
        self.title_bar.close_requested.connect(self.close)
        shell_layout.addWidget(self.title_bar)

        self.stack = SlideStack()
        shell_layout.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_home_page())
        self.stack.addWidget(self._build_settings_page())
        self._settings_built = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        pad = SHADOW_PAD
        panel = QRectF(self.rect()).adjusted(pad, pad, -pad, -pad)
        radius = Radius.WINDOW

        # soft outer shadow (cached blurred pixmap)
        shadow = shadow_pixmap(int(panel.width()), int(panel.height()),
                               radius, 18, "#000000", 190, 10)
        painter.drawPixmap(int(panel.left()) - 36,
                           int(panel.top()) - 36, shadow)

        # panel body
        grad = QLinearGradient(panel.topLeft(), panel.bottomRight())
        grad.setColorAt(0.0, qc(Palette.WINDOW_2))
        grad.setColorAt(0.55, qc(Palette.WINDOW))
        grad.setColorAt(1.0, qc("#05080E"))
        path = rounded_path(panel, radius)
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawPath(path)

        # aurora glow in the top-left corner
        painter.save()
        painter.setClipPath(path)
        glow = QRadialGradient(panel.left() + panel.width() * 0.12,
                               panel.top() - panel.height() * 0.05,
                               panel.width() * 0.95)
        glow.setColorAt(0.0, qc(Palette.INDIGO, 60))
        glow.setColorAt(0.45, qc(Palette.CYAN, 18))
        glow.setColorAt(1.0, qc(Palette.CYAN, 0))
        painter.setBrush(glow)
        painter.drawPath(path)
        painter.restore()

        # border + inner top highlight
        painter.setPen(QPen(qc("#243248"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(rounded_path(panel.adjusted(0.5, 0.5, -0.5, -0.5),
                                      radius - 1))

        hl = QLinearGradient(panel.topLeft(), panel.topRight())
        hl.setColorAt(0.0, QColor(255, 255, 255, 0))
        hl.setColorAt(0.25, QColor(255, 255, 255, 34))
        hl.setColorAt(0.75, QColor(255, 255, 255, 12))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(hl, 1))
        painter.drawLine(panel.left() + radius, panel.top() + 0.5,
                         panel.right() - radius, panel.top() + 0.5)

    # ==================================================================
    # pages
    # ==================================================================

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Space.LG, Space.SM, Space.LG, Space.MD)
        layout.setSpacing(Space.MD - 2)

        # ---- hero -----------------------------------------------------
        self.hero = HeroCard()
        hero = self.hero

        head = QHBoxLayout()
        head.setSpacing(Space.SM)
        eyebrow = QLabel("\u5b9e\u65f6\u5c4f\u5e55\u7ffb\u8bd1\u5f15\u64ce")
        eyebrow.setFont(ui_font(11, QFont.DemiBold))
        eyebrow.setStyleSheet(
            f"color: {Palette.TEXT_DIM}; background: transparent;"
            " letter-spacing: 1px;")
        head.addWidget(eyebrow)
        head.addStretch(1)
        self.status_pill = StatusPill("\u5c31\u7eea", "idle")
        head.addWidget(self.status_pill)
        hero.add(head)

        self.start_btn = GlowButton("\u5f00\u59cb\u7ffb\u8bd1", "primary",
                                    radius=15, font_size=17)
        self.start_btn.setMinimumHeight(56)
        self.start_btn.setToolTip("\u542f\u52a8\u8fde\u7eed\u5b9e\u65f6\u7ffb\u8bd1")
        self.start_btn.clicked.connect(self._on_start)
        hero.add(self.start_btn)

        action_row = QHBoxLayout()
        action_row.setSpacing(Space.SM)

        self.once_btn = GlowButton("\u4e00\u6b21\u6027\u7ffb\u8bd1", "accent",
                                   radius=12, font_size=13)
        self.once_btn.setMinimumHeight(40)
        self.once_btn.setToolTip(
            "\u622a\u53d6\u5f53\u524d\u753b\u9762\u5e76\u7ffb\u8bd1\u4e00\u6b21")
        self.once_btn.clicked.connect(self._on_once_translate)
        action_row.addWidget(self.once_btn, 3)

        capsule = Capsule()
        cap_layout = QHBoxLayout(capsule)
        cap_layout.setContentsMargins(Space.SM, 4, Space.SM, 4)
        cap_layout.setSpacing(4)

        self._hotkey_mod_combo = self._make_combo(list(MOD_MAP.keys()), 74)
        self._hotkey_mod_combo.currentTextChanged.connect(self._on_hotkey_change)
        cap_layout.addWidget(self._hotkey_mod_combo)

        plus = QLabel("+")
        plus.setFont(ui_font(11, QFont.Bold))
        plus.setStyleSheet(f"color: {Palette.TEXT_DIM}; background: transparent;")
        cap_layout.addWidget(plus)

        self._hotkey_key_combo = self._make_combo(HOTKEY_KEYS, 46)
        self._hotkey_key_combo.currentTextChanged.connect(self._on_hotkey_change)
        cap_layout.addWidget(self._hotkey_key_combo)
        action_row.addWidget(capsule, 2)

        hero.add(action_row)

        self._hotkey_label = QLabel("")
        self._hotkey_label.setAlignment(Qt.AlignCenter)
        self._hotkey_label.setFont(ui_font(10))
        self._hotkey_label.setStyleSheet(
            f"color: {Palette.TEXT_DIM}; background: transparent;")
        hero.add(self._hotkey_label)

        layout.addWidget(hero)

        # ---- metrics --------------------------------------------------
        stats = QHBoxLayout()
        stats.setSpacing(Space.SM)
        self._chip_fps = StatChip("\u5e27\u7387 FPS", "0", Palette.SKY)
        self._chip_boxes = StatChip("\u8bc6\u522b\u6846", "0", Palette.CYAN)
        self._chip_trans = StatChip("\u7ffb\u8bd1\u6b21\u6570", "0", Palette.VIOLET)
        for chip in (self._chip_fps, self._chip_boxes, self._chip_trans):
            stats.addWidget(chip, 1)
        layout.addLayout(stats)

        # ---- region ---------------------------------------------------
        region_card = Card()
        region_row = QHBoxLayout()
        region_row.setSpacing(Space.MD)

        pin = QLabel("\u25c9")
        pin.setFont(ui_font(16))
        pin.setStyleSheet(f"color: {Palette.SKY}; background: transparent;")
        pin.setFixedWidth(20)
        pin.setAlignment(Qt.AlignCenter)
        region_row.addWidget(pin)

        region_col = QVBoxLayout()
        region_col.setSpacing(1)
        region_title = QLabel("\u7ffb\u8bd1\u533a\u57df")
        region_title.setFont(ui_font(12, QFont.DemiBold))
        region_title.setStyleSheet(
            f"color: {Palette.TEXT}; background: transparent;")
        region_col.addWidget(region_title)
        self.region_info = QLabel("\u533a\u57df: \u672a\u9009\u62e9")
        self.region_info.setFont(ui_font(10, mono=True))
        self.region_info.setStyleSheet(
            f"color: {Palette.TEXT_DIM}; background: transparent;")
        region_col.addWidget(self.region_info)
        region_row.addLayout(region_col, 1)

        self.region_btn = GlowButton("\u6846\u9009\u533a\u57df", "ghost",
                                     radius=10, font_size=12)
        self.region_btn.setMinimumHeight(36)
        self.region_btn.setMaximumWidth(106)
        self.region_btn.clicked.connect(self._on_select_region)
        region_row.addWidget(self.region_btn, 0)

        region_card.add(region_row)
        layout.addWidget(region_card)

        layout.addStretch(1)

        # ---- footer ---------------------------------------------------
        footer = QHBoxLayout()
        footer.setSpacing(Space.SM)
        self.settings_btn = GlowButton("\u2699  \u8bbe\u7f6e", "ghost",
                                       radius=10, font_size=12, bold=False)
        self.settings_btn.setMinimumHeight(38)
        self.settings_btn.clicked.connect(self._on_toggle_settings)
        footer.addWidget(self.settings_btn, 3)

        self.quit_btn = GlowButton("\u9000\u51fa", "ghost", radius=10,
                                   font_size=12, bold=False)
        self.quit_btn.setMinimumHeight(38)
        self.quit_btn.setToolTip("\u9000\u51fa NexaTrans")
        self.quit_btn.clicked.connect(self._quit_app)
        footer.addWidget(self.quit_btn, 2)
        layout.addLayout(footer)

        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Space.LG, 0, Space.LG, Space.MD)
        layout.setSpacing(Space.MD - 2)

        header = QHBoxLayout()
        header.setSpacing(Space.SM)
        back = IconButton("\u2039", 30)
        back.setToolTip("\u8fd4\u56de")
        back.clicked.connect(self._on_toggle_settings)
        header.addWidget(back)

        title = QLabel("\u8bbe\u7f6e")
        title.setFont(ui_font(16, QFont.Bold))
        title.setStyleSheet(f"color: {Palette.TEXT}; background: transparent;")
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setStyleSheet("background: transparent;")

        content = QWidget()
        content.setAttribute(Qt.WA_StyledBackground, False)
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 2, 6, 2)
        column.setSpacing(Space.MD - 2)

        self._settings_cards: list[QWidget] = []

        # ---- API card -------------------------------------------------
        api_card = Card("DeepSeek API", "\u7528\u4e8e AI \u7ffb\u8bd1\u7684\u5bc6\u94a5",
                        icon="\u25c8", accent=Palette.SKY)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setText(_read_env_key())
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setFont(ui_font(12, mono=True))
        self.api_key_input.textChanged.connect(self._on_api_key_change)
        api_card.add(self.api_key_input)

        api_row = QHBoxLayout()
        api_row.setSpacing(Space.SM)
        self.test_btn = GlowButton("\u68c0\u67e5\u8fde\u901a\u6027", "ghost",
                                   radius=10, font_size=12, bold=False)
        self.test_btn.setMinimumHeight(34)
        self.test_btn.clicked.connect(self._on_test_connection)
        api_row.addWidget(self.test_btn, 0)
        api_row.addStretch(1)
        api_card.add(api_row)
        column.addWidget(api_card)
        self._settings_cards.append(api_card)

        # ---- overlay card ---------------------------------------------
        overlay_card = Card("\u8986\u76d6\u5c42\u663e\u793a",
                            "\u63a7\u5236\u5c4f\u5e55\u4e0a\u7ed8\u5236\u7684\u5185\u5bb9",
                            icon="\u25a7", accent=Palette.CYAN)
        self.mask_check = None
        rows = [
            ("mask_check", "\u663e\u793a Mask \u906e\u7f69",
             "\u7528\u80cc\u666f\u8272\u76d6\u4f4f\u539f\u6587\u5b57"),
            ("boxes_check", "\u663e\u793a\u7eff\u6846",
             "\u6807\u51fa\u68c0\u6d4b\u5230\u7684\u6587\u5b57\u533a\u57df"),
            ("redbox_check", "\u663e\u793a\u7ea2\u6846",
             "\u6807\u51fa\u5f53\u524d\u7ffb\u8bd1\u533a\u57df\u8fb9\u754c"),
            ("ocr_check", "\u542f\u7528 OCR \u8bc6\u522b",
             "\u4ece\u622a\u56fe\u4e2d\u63d0\u53d6\u6587\u5b57"),
            ("trans_check", "\u542f\u7528 AI \u7ffb\u8bd1",
             "\u8c03\u7528 DeepSeek \u7ffb\u8bd1\u6587\u672c"),
        ]
        for attr, name, hint in rows:
            row = ToggleRow(name, hint)
            setattr(self, attr, row.toggle)
            overlay_card.add(row)
        column.addWidget(overlay_card)
        self._settings_cards.append(overlay_card)

        # ---- filter card ----------------------------------------------
        filter_card = Card("\u6587\u5b57\u8fc7\u6ee4\u53c2\u6570",
                           "\u8c03\u6574\u68c0\u6d4b\u7ed3\u679c\u7684\u7cbe\u7ec6\u5ea6",
                           icon="\u25d1", accent=Palette.VIOLET)
        self._s_min_conf, self._l_min_conf = self._add_slider(
            filter_card, "\u6700\u4f4e\u7f6e\u4fe1\u5ea6", 10, 90, 50,
            "{:.2f}", 100.0)
        self._s_min_asp, self._l_min_asp = self._add_slider(
            filter_card, "\u6587\u5b57\u957f\u5bbd\u6bd4", 12, 30, 18,
            "{:.1f}", 10.0)
        self._s_max_icon, self._l_max_icon = self._add_slider(
            filter_card, "\u56fe\u6807\u5bbd\u9ad8\u6bd4", 10, 18, 14,
            "{:.1f}", 10.0)
        self._s_min_area, self._l_min_area = self._add_slider(
            filter_card, "\u6700\u5c0f\u9762\u79ef\u6bd4", 1, 20, 5,
            "{:.3f}", 1000.0)
        column.addWidget(filter_card)
        self._settings_cards.append(filter_card)

        # ---- performance card -----------------------------------------
        perf_card = Card("\u6027\u80fd", "\u5237\u65b0\u7387\u4e0e\u663e\u793a\u65f6\u957f",
                         icon="\u26a1", accent=Palette.WARN)
        self._s_fps, self._l_fps = self._add_slider(
            perf_card, "\u5237\u65b0\u9891\u7387 (FPS)", 1, 30, 10,
            "{:.0f}", 1.0)
        self._s_once_display, self._l_once_display = self._add_slider(
            perf_card, "\u4e00\u6b21\u6027\u663e\u793a\u65f6\u957f (\u79d2)",
            1, 30, 5, "{:.0f}", 1.0)
        column.addWidget(perf_card)
        self._settings_cards.append(perf_card)

        column.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # signal wiring (block signals while loading config later)
        self._s_min_conf.valueChanged.connect(
            lambda v: self._on_f("min_confidence", v, self._l_min_conf,
                                 100.0, "{:.2f}"))
        self._s_min_asp.valueChanged.connect(
            lambda v: self._on_f("min_text_aspect", v, self._l_min_asp,
                                 10.0, "{:.1f}"))
        self._s_max_icon.valueChanged.connect(
            lambda v: self._on_f("max_icon_aspect", v, self._l_max_icon,
                                 10.0, "{:.1f}"))
        self._s_min_area.valueChanged.connect(
            lambda v: self._on_f("min_area_ratio", v, self._l_min_area,
                                 1000.0, "{:.3f}"))
        self._s_fps.valueChanged.connect(self._on_fps_change)
        self._s_once_display.valueChanged.connect(self._on_once_display_change)

        self.mask_check.toggled.connect(self._on_mask_toggle)
        self.boxes_check.toggled.connect(self._on_boxes_toggle)
        self.redbox_check.toggled.connect(self._on_redbox_toggle)
        self.ocr_check.toggled.connect(self._on_ocr_toggle)
        self.trans_check.toggled.connect(self._on_trans_toggle)

        return page

    # -- small builders -----------------------------------------------------

    @staticmethod
    def _make_combo(items, width: int):
        combo = QComboBox()
        combo.addItems(list(items))
        combo.setFixedWidth(width)
        combo.setFixedHeight(28)
        combo.setFont(ui_font(11, QFont.DemiBold))
        combo.setCursor(Qt.PointingHandCursor)
        return combo

    def _add_slider(self, card: Card, title: str, mn: int, mx: int, dv: int,
                    fmt: str, scale: float):
        row = SliderRow(title, mn, mx, dv, fmt=fmt, scale=scale)
        card.add(row)
        return row.slider, row.value_label

    # ==================================================================
    # animations
    # ==================================================================

    def _fade_in(self, widget: QWidget) -> None:
        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        animate(widget, "fade_in", 0.0, 1.0,
                lambda v: effect.setOpacity(float(v)),
                duration=260, easing=QEasingCurve.OutCubic,
                finished=lambda: widget.setGraphicsEffect(None))

    def _stagger_cards(self) -> None:
        for i, card in enumerate(getattr(self, "_settings_cards", [])):
            effect = QGraphicsOpacityEffect(card)
            effect.setOpacity(0.0)
            card.setGraphicsEffect(effect)

            def make(e=effect, c=card):
                def run():
                    animate(c, "stagger", 0.0, 1.0,
                            lambda v: e.setOpacity(float(v)),
                            duration=260, easing=QEasingCurve.OutCubic,
                            finished=lambda: c.setGraphicsEffect(None))
                return run
            QTimer.singleShot(40 * i, make())

    def _animate_height(self, target_h: int, duration: int = Motion.WINDOW) -> None:
        start = self.height()
        animate(self, "height", start, int(target_h),
                lambda v: self.setFixedHeight(int(v)),
                duration=duration, easing=QEasingCurve.OutCubic)

    def _settings_height(self) -> int:
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry().height() if screen else 900
        return max(560, min(880, available - 80)) + SHADOW_PAD * 2

    def _toast(self, text: str, tone: str = "info",
               duration: int = 2400) -> None:
        # float above the footer buttons instead of covering them
        Toast.push(self.shell, text, tone, duration, offset_bottom=58)

    # ==================================================================
    # system tray
    # ==================================================================

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("NexaTrans")
        menu = QMenu()
        self._tray_status = QAction("\u25cf \u5c31\u7eea")
        self._tray_status.setEnabled(False)
        menu.addAction(self._tray_status)
        menu.addSeparator()
        self._tray_show = QAction("\u6253\u5f00\u4e3b\u754c\u9762")
        self._tray_show.triggered.connect(self._show_from_tray)
        menu.addAction(self._tray_show)
        self._tray_toggle = QAction("\u5f00\u59cb\u7ffb\u8bd1")
        self._tray_toggle.triggered.connect(self._on_start)
        menu.addAction(self._tray_toggle)
        self._tray_once = QAction("\u4e00\u6b21\u6027\u7ffb\u8bd1")
        self._tray_once.triggered.connect(self._on_once_translate)
        menu.addAction(self._tray_once)
        menu.addSeparator()
        self._tray_quit = QAction("\u9000\u51fa\u7a0b\u5e8f")
        self._tray_quit.triggered.connect(self._quit_app)
        menu.addAction(self._tray_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda r: self._show_from_tray() if r == QSystemTrayIcon.DoubleClick
            else None)
        self._tray.show()

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self._fade_in(self)

    def _hide_to_tray(self):
        self.hide()
        self._tray.showMessage(
            "NexaTrans",
            "\u7a0b\u5e8f\u5df2\u6700\u5c0f\u5316\u5230\u6258\u76d8\uff0c"
            "\u53cc\u51fb\u6258\u76d8\u56fe\u6807\u53ef\u91cd\u65b0\u6253\u5f00",
            QSystemTrayIcon.Information, 1800)

    def _update_tray_menu(self):
        if self._pipeline and self._pipeline.is_running:
            boxes = (self._pipeline.overlay._boxes
                     if hasattr(self._pipeline.overlay, "_boxes") else [])
            tc = getattr(self._pipeline, "trans_count", 0)
            self._tray_status.setText(
                f"\u25cf \u8fd0\u884c\u4e2d | {self._pipeline.fps:.0f}FPS | "
                f"{len(boxes)}\u6846 | \u7ffb\u8bd1:{tc}\u6b21")
            self._tray_toggle.setText("\u505c\u6b62\u7ffb\u8bd1")
        else:
            self._tray_status.setText("\u25cf \u5c31\u7eea")
            self._tray_toggle.setText("\u5f00\u59cb\u7ffb\u8bd1")

    def _quit_app(self):
        self._quitting = True
        self._unregister_hotkey()
        if self._pipeline:
            try:
                self._pipeline.cleanup()
            except Exception:
                pass
        self._fps_timer.stop()
        self._overlay.close()
        self._tray.setVisible(False)
        self._tray.hide()
        self.hide()
        QApplication.instance().quit()
        sys.exit(0)

    # ==================================================================
    # hotkey
    # ==================================================================

    def _register_hotkey(self):
        try:
            ui = self.config_manager.get_ui_config()
            mod_str = ui.get("once_hotkey_mod", DEFAULT_HOTKEY_MOD)
            key_str = ui.get("once_hotkey_key", DEFAULT_HOTKEY_KEY)
            modifier = MOD_MAP.get(mod_str, MOD_CTRL | MOD_SHIFT) | MOD_NOREPEAT
            vk = self._key_to_vk(key_str)
            if vk == 0:
                logger.warning(f"Invalid hotkey key: {key_str}")
                return
            hwnd = int(self.winId())
            if ctypes.windll.user32.RegisterHotKey(hwnd, self._hotkey_id,
                                                   modifier, vk):
                self._hotkey_registered = True
                logger.info(f"Hotkey registered: {mod_str}+{key_str}")
            else:
                logger.warning(
                    f"Hotkey registration failed (may be in use): "
                    f"{mod_str}+{key_str}")
        except Exception as e:
            logger.error(f"Hotkey register error: {e}")

    def _unregister_hotkey(self):
        if self._hotkey_registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(int(self.winId()),
                                                      self._hotkey_id)
                self._hotkey_registered = False
                logger.info("Hotkey unregistered")
            except Exception as e:
                logger.error(f"Hotkey unregister error: {e}")

    def _reapply_hotkey(self):
        self._unregister_hotkey()
        self._register_hotkey()

    def _on_hotkey_change(self):
        mod_str = self._hotkey_mod_combo.currentText()
        key_str = self._hotkey_key_combo.currentText()
        self._hotkey_label.setText(
            f"\u4e00\u6b21\u6027\u7ffb\u8bd1\u5feb\u6377\u952e  "
            f"{mod_str} + {key_str}")
        ui = self.config_manager.get_ui_config()
        ui["once_hotkey_mod"] = mod_str
        ui["once_hotkey_key"] = key_str
        self.config_manager.save_ui_config(ui)
        self._reapply_hotkey()

    @staticmethod
    def _key_to_vk(key_str: str) -> int:
        if len(key_str) == 1 and key_str.isalpha():
            return ord(key_str.upper())
        elif len(key_str) == 1 and key_str.isdigit():
            return ord(key_str)
        elif key_str.startswith("F") and key_str[1:].isdigit():
            n = int(key_str[1:])
            if 1 <= n <= 24:
                return 0x6F + n
        return 0

    # ==================================================================
    # config
    # ==================================================================

    def _load_config(self):
        tp = self.config_manager.get_text_processing_config()
        ui = self.config_manager.get_ui_config()

        self._settings_visible = False
        self._load_into_controls(tp, ui)

        # hotkey selectors
        mod_str = ui.get("once_hotkey_mod", DEFAULT_HOTKEY_MOD)
        key_str = ui.get("once_hotkey_key", DEFAULT_HOTKEY_KEY)
        self._hotkey_mod_combo.blockSignals(True)
        self._hotkey_key_combo.blockSignals(True)
        idx = self._hotkey_mod_combo.findText(mod_str)
        if idx >= 0:
            self._hotkey_mod_combo.setCurrentIndex(idx)
        idx2 = self._hotkey_key_combo.findText(key_str)
        if idx2 >= 0:
            self._hotkey_key_combo.setCurrentIndex(idx2)
        self._hotkey_mod_combo.blockSignals(False)
        self._hotkey_key_combo.blockSignals(False)
        self._hotkey_label.setText(
            f"\u4e00\u6b21\u6027\u7ffb\u8bd1\u5feb\u6377\u952e  {mod_str} + {key_str}")

        if ui.get("show_redbox", False):
            r = self.config_manager.load_region()
            if r.get("width", 0) > 0:
                self._overlay.update_region(r)
                self._overlay.set_test_visible(True)

    def _load_into_controls(self, tp: dict, ui: dict) -> None:
        """Apply persisted values to the settings widgets."""
        if not self._settings_built:
            return
        widgets = [self._s_min_conf, self._s_min_asp, self._s_max_icon,
                   self._s_min_area, self._s_fps, self._s_once_display,
                   self.mask_check, self.boxes_check, self.redbox_check,
                   self.ocr_check, self.trans_check]
        for w in widgets:
            w.blockSignals(True)
        try:
            self._s_min_conf.setValue(int(tp["min_confidence"] * 100))
            self._s_min_asp.setValue(int(tp["min_text_aspect"] * 10))
            self._s_max_icon.setValue(int(tp["max_icon_aspect"] * 10))
            self._s_min_area.setValue(int(tp["min_area_ratio"] * 1000))
            self._l_min_conf.setText(f"{tp['min_confidence']:.2f}")
            self._l_min_asp.setText(f"{tp['min_text_aspect']:.1f}")
            self._l_max_icon.setText(f"{tp['max_icon_aspect']:.1f}")
            self._l_min_area.setText(f"{tp['min_area_ratio']:.3f}")

            self.mask_check.setChecked(ui.get("show_mask", False))
            self.boxes_check.setChecked(ui.get("show_boxes", True))
            self.redbox_check.setChecked(ui.get("show_redbox", False))
            self.ocr_check.setChecked(ui.get("show_ocr", True))
            self.trans_check.setChecked(ui.get("show_translation", True))

            fps = ui.get("fps_target", 10)
            self._s_fps.setValue(fps)
            self._l_fps.setText(str(fps))
            secs = ui.get("once_display_seconds", 5)
            self._s_once_display.setValue(secs)
            self._l_once_display.setText(str(secs))
        finally:
            for w in widgets:
                w.blockSignals(False)

    def _load_region(self):
        r = self.config_manager.load_region()
        if r.get("width", 0) > 0:
            self.region_info.setText(self._region_text(r))
            self._overlay.update_region(r)

    @staticmethod
    def _region_text(region: dict) -> str:
        return (f"{region['width']} x {region['height']}  "
                f"@ ({region['x']}, {region['y']})")

    def _save_ui(self):
        self.config_manager.save_ui_config({
            "show_mask": self.mask_check.isChecked(),
            "show_boxes": self.boxes_check.isChecked(),
            "show_redbox": self.redbox_check.isChecked(),
            "show_ocr": self.ocr_check.isChecked(),
            "show_translation": self.trans_check.isChecked(),
            "fps_target": self._s_fps.value(),
            "once_display_seconds": self._s_once_display.value(),
            "once_hotkey_mod": self._hotkey_mod_combo.currentText(),
            "once_hotkey_key": self._hotkey_key_combo.currentText(),
        })

    # ==================================================================
    # settings interactions
    # ==================================================================

    def _on_f(self, key, raw, label, div, fmt):
        val = raw / div
        label.setText(fmt.format(val))
        tp = self.config_manager.get_text_processing_config()
        tp[key] = val
        self.config_manager.save_text_processing(tp)

    def _on_fps_change(self, v):
        if not self._settings_built:
            return
        self._l_fps.setText(str(v))
        self._save_ui()
        if self._pipeline:
            self._pipeline.set_fps(v)

    def _on_once_display_change(self, v):
        if not self._settings_built:
            return
        self._l_once_display.setText(str(v))
        self._save_ui()

    def _on_api_key_change(self, text):
        _write_env_key(text.strip())

    def _on_test_connection(self):
        key = self.api_key_input.text().strip()
        if not key:
            self._toast("\u8bf7\u5148\u8f93\u5165 API \u5bc6\u94a5", "warn")
            QMessageBox.warning(self, "\u68c0\u67e5\u8fde\u901a\u6027",
                                "\u8bf7\u5148\u8f93\u5165API\u5bc6\u94a5")
            return

        self.test_btn.set_busy(True)
        self.test_btn.setText("\u68c0\u67e5\u4e2d")
        self.test_btn.setEnabled(False)
        QApplication.instance().processEvents()
        try:
            import importlib
            import translation.deepseek_client as dsc
            importlib.reload(dsc)
            client = dsc.DeepSeekClient(api_key=key)
            result = client.translate("test")
            if result.get("translation") and not result.get("error"):
                self.test_btn.set_variant("success")
                self.test_btn.setText("\u8fde\u63a5\u6210\u529f")
                self._toast("\u2713  DeepSeek API \u8fde\u63a5\u6210\u529f",
                            "success")
            else:
                self.test_btn.set_variant("danger")
                self.test_btn.setText("\u8fde\u63a5\u5931\u8d25")
                self._toast("\u8fde\u63a5\u5931\u8d25\uff1a"
                            f"{result.get('error', 'Unknown')}", "error", 3600)
                QMessageBox.critical(self, "\u8fde\u63a5\u5931\u8d25",
                                     f"API\u9519\u8bef: "
                                     f"{result.get('error', 'Unknown')}")
        except Exception as e:
            self.test_btn.set_variant("danger")
            self.test_btn.setText("\u8fde\u63a5\u5931\u8d25")
            self._toast(f"\u8fde\u63a5\u5f02\u5e38\uff1a{str(e)[:40]}", "error",
                        3600)
            QMessageBox.critical(self, "\u8fde\u63a5\u5931\u8d25", str(e))
        finally:
            self.test_btn.set_busy(False)
            self.test_btn.setEnabled(True)
            QTimer.singleShot(
                2600, lambda: (self.test_btn.set_variant("ghost"),
                               self.test_btn.setText("\u68c0\u67e5\u8fde\u901a\u6027")))

    def _on_toggle_settings(self):
        self._settings_visible = not self._settings_visible

        if self._settings_visible:
            self.stack.setCurrentIndex(1)
            self._animate_height(self._settings_height())
            self._stagger_cards()
            self.settings_btn.setText("\u2039  \u8fd4\u56de")
        else:
            self.stack.setCurrentIndex(0)
            self._animate_height(HOME_H + SHADOW_PAD * 2)
            self.settings_btn.setText("\u2699  \u8bbe\u7f6e")

    # ==================================================================
    # pipeline control
    # ==================================================================

    def _on_start(self):
        if self._pipeline and self._pipeline.is_running:
            self._stop_all()
        else:
            self._start_all()

    def _start_all(self):
        if self._pipeline is None:
            self._init_pipeline()
        if self._pipeline is None:
            return
        if self._pipeline.start():
            self._pipeline.set_fps(self._s_fps.value())
            self._pipeline.show_mask = self.mask_check.isChecked()
            self._pipeline.ocr_enabled = self.ocr_check.isChecked()
            self._pipeline.trans_enabled = self.trans_check.isChecked()
            self._pipeline.overlay.show_boxes = self.boxes_check.isChecked()

            self.start_btn.setText("\u505c\u6b62\u7ffb\u8bd1")
            self.start_btn.set_variant("danger")
            self.hero.set_active(True)
            self.status_pill.set_state("\u8fd0\u884c\u4e2d", "running")
            self._fps_timer.start(500)
            self.region_btn.setEnabled(False)
            self._update_tray_menu()
            self._toast("\u25b6  \u5df2\u5f00\u59cb\u5b9e\u65f6\u7ffb\u8bd1", "success")

    def _stop_all(self):
        if self._pipeline:
            self._pipeline.stop()
        self.start_btn.setText("\u5f00\u59cb\u7ffb\u8bd1")
        self.start_btn.set_variant("primary")
        self.hero.set_active(False)
        self.status_pill.set_state("\u5c31\u7eea", "idle")
        self._fps_timer.stop()
        self.region_btn.setEnabled(True)
        self._update_tray_menu()
        self._chip_fps.set_value(0)
        self._chip_boxes.set_value(0)

    # ---- one-time translation -------------------------------------------

    def _on_once_translate(self):
        if self._once_busy:
            return
        self._once_busy = True
        self.once_btn.setEnabled(False)
        self.once_btn.set_busy(True)
        self.once_btn.setText("\u7ffb\u8bd1\u4e2d")
        self.status_pill.set_state("\u4e00\u6b21\u6027\u7ffb\u8bd1\u4e2d", "busy")

        if self._pipeline is None:
            self._init_pipeline()
        if self._pipeline is None:
            self._set_once_done("\u6a21\u578b\u52a0\u8f7d\u5931\u8d25", "error")
            return

        # stop the continuous loop so it cannot overwrite our results
        self._once_was_running = self._pipeline.is_running
        if self._once_was_running:
            self._pipeline.stop()
            self.start_btn.setText("\u5f00\u59cb\u7ffb\u8bd1")
            self.start_btn.set_variant("primary")
            self.hero.set_active(False)
            self._fps_timer.stop()
            self.region_btn.setEnabled(True)

        self._once_display_timer.stop()

        self._pipeline.show_mask = self.mask_check.isChecked()
        self._pipeline.ocr_enabled = self.ocr_check.isChecked()
        self._pipeline.trans_enabled = self.trans_check.isChecked()
        self._pipeline.overlay.show_boxes = self.boxes_check.isChecked()
        self._pipeline._dpr = self._pipeline._dpr_get()

        region = self.config_manager.load_region()
        self._pipeline._overlay.update_region(region)
        self._pipeline._last_region = dict(region)
        self._pipeline._overlay.show_overlay()

        try:
            result = self._pipeline.capture_once()
            if result is None:
                self._set_once_done("\u6355\u83b7\u5931\u8d25", "error")
                return
            boxes = result.get("boxes", [])
            trans = result.get("trans", [])
            ocr = result.get("ocr", [])
            mask = result.get("mask")
            colors = result.get("colors")

            if boxes:
                if mask is not None:
                    self._pipeline._overlay.set_data(boxes, mask, colors)
                    self._pipeline._sent_has_mask = True
                else:
                    self._pipeline._overlay.set_data(boxes, None, None)
                    self._pipeline._sent_has_mask = False
                self._pipeline._sent_boxes = list(boxes)

            if trans:
                self._pipeline._overlay.set_trans_results(trans)
                self._pipeline._overlay.show_translation = True
                self._pipeline._overlay.show_ocr = False
                self._set_once_done(
                    f"\u7ffb\u8bd1\u5b8c\u6210 \u00b7 {len(trans)} \u6761", "ok")
                self._toast(
                    f"\u2713  \u7ffb\u8bd1\u5b8c\u6210\uff0c{len(trans)} \u6761\u7ed3\u679c",
                    "success")
            elif ocr:
                self._pipeline._overlay.set_ocr_results(ocr)
                self._pipeline._overlay.show_ocr = True
                self._pipeline._overlay.show_translation = False
                self._set_once_done(
                    f"OCR \u5b8c\u6210 \u00b7 {len(ocr)} \u6761", "ok")
                self._toast(f"\u2713  \u8bc6\u522b\u5b8c\u6210\uff0c{len(ocr)} \u6761\u6587\u5b57",
                            "success")
            elif boxes:
                self._pipeline._overlay.show_ocr = False
                self._pipeline._overlay.show_translation = False
                self._set_once_done(
                    f"\u68c0\u6d4b\u5230 {len(boxes)} \u4e2a\u6587\u5b57\u533a\u57df",
                    "ok")
                self._toast(f"\u68c0\u6d4b\u5230 {len(boxes)} \u4e2a\u6587\u5b57\u533a\u57df",
                            "info")
            else:
                self._set_once_done("\u672a\u68c0\u6d4b\u5230\u6587\u5b57", "ready")
                self._toast("\u672a\u68c0\u6d4b\u5230\u6587\u5b57", "warn")

            self._chip_boxes.set_value(len(boxes))
            self._chip_trans.set_value(self._pipeline.trans_count)

            secs = self._s_once_display.value()
            if secs > 0:
                self._once_display_timer.start(secs * 1000)

        except Exception as e:
            logger.error(f"One-time translation failed: {e}", exc_info=True)
            self._set_once_done(f"\u9519\u8bef: {str(e)[:30]}", "error")

    def _clear_once_overlay(self):
        if self._pipeline and not self._pipeline.is_running:
            self._pipeline._overlay.set_data([], None, None)
            self._pipeline._overlay.set_ocr_results([])
            self._pipeline._overlay.set_trans_results([])
            self._pipeline._overlay.hide_overlay()
        self._update_tray_menu()

    def _set_once_done(self, text: str, state: str) -> None:
        self.status_pill.set_state(text, state)
        self.once_btn.setText("\u4e00\u6b21\u6027\u7ffb\u8bd1")
        self.once_btn.set_busy(False)
        self.once_btn.setEnabled(True)
        self._once_busy = False

    # ---- region ----------------------------------------------------------

    def _on_select_region(self):
        if self._overlay.isVisible():
            self._overlay.hide()
        self.hide()
        self._selector = SelectorWindow(self.config_manager.get_overlay_config())
        self._selector.region_selected.connect(self._on_region_done)
        self._selector.cancelled.connect(self._on_region_cancel)

    def _on_region_done(self, region):
        self._selector = None
        self.config_manager.save_region(region)
        self.region_info.setText(self._region_text(region))
        self._overlay.update_region(region)
        if self.redbox_check.isChecked():
            self._overlay.set_test_visible(True)
        self.show()
        self._fade_in(self)
        self._toast(
            f"\u5df2\u8bbe\u7f6e\u7ffb\u8bd1\u533a\u57df  {region['width']} x "
            f"{region['height']}", "info")

    def _on_region_cancel(self):
        self._selector = None
        self.show()
        self._fade_in(self)

    # ---- overlay toggles -------------------------------------------------

    def _on_mask_toggle(self, c):
        self._save_ui()
        if self._pipeline:
            self._pipeline.show_mask = c

    def _on_boxes_toggle(self, c):
        self._save_ui()
        if self._pipeline and self._pipeline.overlay:
            self._pipeline.overlay.show_boxes = c

    def _on_redbox_toggle(self, c):
        self._save_ui()
        if c:
            r = self.config_manager.load_region()
            if r.get("width", 0) > 0:
                self._overlay.update_region(r)
        self._overlay.set_test_visible(c)

    def _on_ocr_toggle(self, c):
        self._save_ui()
        if self._pipeline:
            self._pipeline.ocr_enabled = c

    def _on_trans_toggle(self, c):
        self._save_ui()
        if self._pipeline:
            self._pipeline.trans_enabled = c

    # ---- pipeline init ---------------------------------------------------

    def _init_pipeline(self):
        if self._pipeline_inited:
            return
        self._pipeline_inited = True
        from detection.detection_pipeline import DetectionPipeline

        self.status_pill.set_state("\u52a0\u8f7d\u6a21\u578b", "busy")
        self.start_btn.setEnabled(False)
        self.once_btn.setEnabled(False)
        self.start_btn.set_busy(True)
        self.start_btn.setText("\u52a0\u8f7d\u6a21\u578b")
        QApplication.instance().processEvents()
        try:
            self._pipeline = DetectionPipeline(
                self.config_manager, target_fps=self._s_fps.value())
            if self._pipeline.detector.is_loaded:
                self.status_pill.set_state("\u5c31\u7eea", "idle")
            else:
                self.status_pill.set_state("\u6a21\u578b\u52a0\u8f7d\u5931\u8d25",
                                           "error")
                self._pipeline = None
                self._pipeline_inited = False
        except Exception as e:
            logger.error(f"Pipeline init failed: {e}")
            self.status_pill.set_state("\u9519\u8bef", "error")
            self._pipeline = None
            self._pipeline_inited = False
        finally:
            self.start_btn.set_busy(False)
            self.start_btn.setText("\u5f00\u59cb\u7ffb\u8bd1")
            self.start_btn.setEnabled(True)
            self.once_btn.setEnabled(True)

    def _update_status(self):
        if not self._pipeline or not self._pipeline.is_running:
            return
        boxes = (self._pipeline.overlay._boxes
                 if hasattr(self._pipeline.overlay, "_boxes") else [])
        static = getattr(self._pipeline, "is_static", True)
        trans_count = getattr(self._pipeline, "trans_count", 0)

        self._chip_fps.set_value(self._pipeline.fps)
        self._chip_boxes.set_value(len(boxes))
        self._chip_trans.set_value(trans_count)
        mode = "\u9759\u6001" if static else "\u52a8\u6001"
        self.status_pill.set_state(f"{mode} \u8bc6\u522b\u4e2d", "running")
        self._update_tray_menu()

    # ==================================================================

    def closeEvent(self, event):
        if self._quitting:
            super().closeEvent(event)
        else:
            self.hide()
            self._tray.showMessage(
                "NexaTrans",
                "\u7a0b\u5e8f\u5df2\u6700\u5c0f\u5316\u5230\u6258\u76d8\uff0c"
                "\u53cc\u51fb\u6258\u76d8\u56fe\u6807\u53ef\u91cd\u65b0\u6253\u5f00",
                QSystemTrayIcon.Information, 2000)
            event.ignore()
