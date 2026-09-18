# -*- coding: utf-8 -*-
"""
NexaTrans - Main Window  (Windows 11 Fluent UI)

Frameless Mica-style window with a Win11 caption bar, a WinUI settings-card
layout, a WinUI page transition and an InfoBar notification.

The theme follows the Windows personalisation settings (light / dark) and the
system accent colour; it can be overridden from the Settings page.

Business logic (pipeline control, hotkeys, tray, config persistence) is
unchanged from v1.2 - only the presentation layer was rebuilt.
"""

import ctypes
import logging
import os
import sys
import threading

from PySide6.QtCore import (
    QAbstractNativeEventFilter, QEasingCurve, QPointF, QRectF, Qt, QTimer,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QMessageBox, QScrollArea, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from config.config_manager import ConfigManager
from ui.selector_window import SelectorWindow
from ui.region_overlay import RegionOverlay
from ui.theme import (
    MODE_DARK, MODE_LABELS, MODE_LIGHT, MODE_SYSTEM, Motion, Radius, Space,
    apply_app_theme, qc, rounded_path, set_theme_mode, theme, ui_font,
)
from ui.widgets.anim import animate
from ui.widgets.buttons import FluentButton, IconButton
from ui.widgets.containers import (
    Card, Divider, FluentStack, SettingsRow, TitleBar, paint_logo_mark,
)
from ui.widgets.controls import FluentSlider, ToggleSwitch
from ui.widgets.feedback import (
    InfoBar, MetricTile, ProgressRing, StatusBadge,
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

# ---- geometry ----
# There is deliberately NO transparent padding around the panel: the window
# rect is exactly the visible UI.  A padded translucent window would sit on
# top of the desktop as an invisible band that swallows clicks and travels
# with the app when it is dragged.
WINDOW_W = 452
HOME_H = 448
SHADOW_PAD = 0
APP_VERSION = "v1.3.0"

# ---- optional DWM integration (rounded corners / dark caption) ----
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2


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
    """Multi-resolution tray icon built from the Fluent logo tile."""
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64):
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
        self._loading = False
        self._pending_action = None      # "start" / "once" queued behind loading
        self._load_result = None
        self._load_timer = QTimer(self)
        self._load_timer.timeout.connect(self._poll_model_load)

        app = QApplication.instance()
        if app is not None:
            # honour the persisted theme choice, default = follow Windows
            ui = self.config_manager.get_ui_config()
            apply_app_theme(app, ui.get("theme_mode", MODE_SYSTEM))

        self._setup_ui()
        self._setup_tray()
        self._load_config()
        self._load_region()
        self._hotkey_filter = HotkeyFilter(self._on_once_translate)
        if app:
            app.installNativeEventFilter(self._hotkey_filter)
        QTimer.singleShot(500, self._register_hotkey)
        logger.info("MainWindow v2.0 (Fluent UI) ready")

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
        root.setContentsMargins(SHADOW_PAD, SHADOW_PAD, SHADOW_PAD, SHADOW_PAD)
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
        self.title_bar.close_btn.set_top_right_round(Radius.WINDOW)
        shell_layout.addWidget(self.title_bar)

        self.stack = FluentStack()
        shell_layout.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_home_page())
        self.stack.addWidget(self._build_settings_page())
        self._settings_built = True

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_dwm()

    def _apply_dwm(self) -> None:
        """Ask DWM for rounded corners / dark caption on Windows 11."""
        try:
            hwnd = int(self.winId())
            if not hwnd:
                return
            dwm = ctypes.windll.dwmapi
            pref = ctypes.c_int(DWMWCP_ROUND)
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                                      ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass

    def paintEvent(self, event):
        t = theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        pad = SHADOW_PAD
        panel = QRectF(self.rect()).adjusted(pad, pad, -pad, -pad)
        radius = Radius.WINDOW

        # Mica-like material: base gradient + two very soft tint blobs
        path = rounded_path(panel, radius)
        grad = QLinearGradient(panel.topLeft(), panel.bottomLeft())
        grad.setColorAt(0.0, qc(t.window))
        grad.setColorAt(1.0, qc(t.window_alt))
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawPath(path)

        painter.save()
        painter.setClipPath(path)
        blob = QRadialGradient(panel.left() + panel.width() * 0.15,
                               panel.top() - panel.height() * 0.10,
                               panel.width() * 1.05)
        blob.setColorAt(0.0, qc(t.tint_a))
        blob.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(blob)
        painter.drawPath(path)

        blob2 = QRadialGradient(panel.right() - panel.width() * 0.10,
                                panel.bottom() + panel.height() * 0.05,
                                panel.width() * 0.95)
        blob2.setColorAt(0.0, qc(t.tint_b))
        blob2.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(blob2)
        painter.drawPath(path)
        painter.restore()

        # hairline window border with a brighter top edge (Win11 window stroke)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(qc(t.card_stroke), 1.0))
        painter.drawPath(rounded_path(panel.adjusted(0.5, 0.5, -0.5, -0.5),
                                      radius - 1))
        hl = QLinearGradient(panel.topLeft(), panel.topRight())
        hl.setColorAt(0.0, QColor(255, 255, 255, 0))
        hl.setColorAt(0.5, QColor(255, 255, 255, 40 if t.is_dark else 210))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(hl, 1.0))
        painter.drawLine(QPointF(panel.left() + radius, panel.top() + 0.5),
                         QPointF(panel.right() - radius, panel.top() + 0.5))

    # ==================================================================
    # pages
    # ==================================================================

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Space.LG, Space.SM, Space.LG, Space.MD)
        layout.setSpacing(Space.MD)

        # ---- primary action card --------------------------------------
        hero = Card()
        head = QHBoxLayout()
        head.setSpacing(Space.SM)
        headline = QLabel("\u5b9e\u65f6\u5c4f\u5e55\u7ffb\u8bd1")
        headline.setProperty("role", "subtitle")
        head.addWidget(headline)
        head.addStretch(1)
        self.load_ring = ProgressRing(18)
        self.load_ring.hide()
        head.addWidget(self.load_ring, 0, Qt.AlignVCenter)
        self.status_badge = StatusBadge("\u5c31\u7eea", "idle")
        head.addWidget(self.status_badge, 0, Qt.AlignVCenter)
        hero.add(head)

        self.start_btn = FluentButton("\u5f00\u59cb\u7ffb\u8bd1", "accent",
                                      font_size=15, bold=True)
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setToolTip("\u542f\u52a8\u8fde\u7eed\u5b9e\u65f6\u7ffb\u8bd1")
        self.start_btn.clicked.connect(self._on_start)
        hero.add(self.start_btn)

        action_row = QHBoxLayout()
        action_row.setSpacing(Space.SM)
        self.once_btn = FluentButton("\u7ffb\u8bd1\u4e00\u6b21", "standard",
                                     font_size=14)
        self.once_btn.setMinimumHeight(32)
        self.once_btn.setToolTip(
            "\u622a\u53d6\u5f53\u524d\u753b\u9762\u5e76\u7ffb\u8bd1\u4e00\u6b21")
        self.once_btn.clicked.connect(self._on_once_translate)
        action_row.addWidget(self.once_btn, 3)

        hotkey_caption = QLabel("\u5feb\u6377\u952e")
        hotkey_caption.setProperty("role", "caption")
        action_row.addWidget(hotkey_caption, 0)

        self._hotkey_mod_combo = self._make_combo(list(MOD_MAP.keys()), 86)
        self._hotkey_mod_combo.currentTextChanged.connect(self._on_hotkey_change)
        action_row.addWidget(self._hotkey_mod_combo, 0)

        plus = QLabel("+")
        plus.setProperty("role", "caption")
        action_row.addWidget(plus, 0)

        self._hotkey_key_combo = self._make_combo(HOTKEY_KEYS, 64)
        self._hotkey_key_combo.currentTextChanged.connect(self._on_hotkey_change)
        action_row.addWidget(self._hotkey_key_combo, 0)
        hero.add(action_row)

        layout.addWidget(hero)

        # ---- live metrics ---------------------------------------------
        stats = QHBoxLayout()
        stats.setSpacing(Space.SM)
        self._chip_fps = MetricTile("\u5e27\u7387", "0")
        self._chip_boxes = MetricTile("\u6587\u5b57\u5757", "0")
        self._chip_trans = MetricTile("\u7ffb\u8bd1\u6b21\u6570", "0")
        for chip in (self._chip_fps, self._chip_boxes, self._chip_trans):
            stats.addWidget(chip, 1)
        layout.addLayout(stats)

        # ---- region ----------------------------------------------------
        region_card = Card()
        self.region_btn = FluentButton("\u9009\u62e9\u533a\u57df", "standard",
                                       font_size=14)
        self.region_btn.setFixedWidth(96)
        self.region_btn.setMinimumHeight(32)
        self.region_btn.setToolTip(
            "\u5728\u5c4f\u5e55\u4e0a\u62d6\u51fa\u4e00\u4e2a\u8981\u7ffb\u8bd1\u7684\u533a\u57df")
        self.region_btn.clicked.connect(self._on_select_region)

        region_row = SettingsRow("\u7ffb\u8bd1\u533a\u57df",
                                 "\u5c1a\u672a\u9009\u62e9\u533a\u57df",
                                 self.region_btn)
        self.region_info = region_row.description_label
        region_card.add(region_row)
        layout.addWidget(region_card)

        layout.addStretch(1)

        # ---- footer ----------------------------------------------------
        footer = QHBoxLayout()
        footer.setSpacing(Space.SM)
        self.settings_btn = FluentButton("\u8bbe\u7f6e", "standard",
                                         font_size=14)
        self.settings_btn.setMinimumHeight(32)
        self.settings_btn.clicked.connect(self._on_toggle_settings)
        footer.addWidget(self.settings_btn, 1)

        self.quit_btn = FluentButton("\u9000\u51fa", "subtle", font_size=14)
        self.quit_btn.setMinimumHeight(32)
        self.quit_btn.setToolTip("\u9000\u51fa NexaTrans")
        self.quit_btn.clicked.connect(self._quit_app)
        footer.addWidget(self.quit_btn, 1)
        layout.addLayout(footer)

        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Space.LG, 0, Space.LG, Space.MD)
        layout.setSpacing(Space.SM)

        header = QHBoxLayout()
        header.setSpacing(Space.SM)
        back = IconButton("\u2039", 32)
        back.setToolTip("\u8fd4\u56de")
        back.setFont(ui_font(20))
        back.clicked.connect(self._on_toggle_settings)
        header.addWidget(back)

        title = QLabel("\u8bbe\u7f6e")
        title.setProperty("role", "subtitle")
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
        column.setSpacing(Space.MD)

        # ---- appearance (theme) ---------------------------------------
        appearance = Card("\u5916\u89c2",
                          "\u4e3b\u9898\u9ed8\u8ba4\u8ddf\u968f Windows \u7cfb\u7edf\u8bbe\u7f6e")
        self.theme_combo = QComboBox()
        self.theme_combo.setFixedWidth(120)
        for mode in (MODE_SYSTEM, MODE_LIGHT, MODE_DARK):
            self.theme_combo.addItem(MODE_LABELS[mode], mode)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_change)
        appearance.add(SettingsRow("\u5e94\u7528\u4e3b\u9898",
                                   "\u6d45\u8272 / \u6df1\u8272 / \u8ddf\u968f\u7cfb\u7edf",
                                   self.theme_combo))
        column.addWidget(appearance)

        # ---- API -------------------------------------------------------
        api_card = Card("DeepSeek API", "\u7528\u4e8e AI \u7ffb\u8bd1\u7684\u5bc6\u94a5")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setText(_read_env_key())
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setFont(ui_font(13, mono=True))
        self.api_key_input.textChanged.connect(self._on_api_key_change)
        api_card.add(self.api_key_input)

        api_row = QHBoxLayout()
        api_row.setSpacing(Space.SM)
        self.test_btn = FluentButton("\u68c0\u67e5\u8fde\u901a\u6027", "standard",
                                     font_size=14)
        self.test_btn.setMinimumHeight(32)
        self.test_btn.setFixedWidth(126)
        self.test_btn.clicked.connect(self._on_test_connection)
        api_row.addWidget(self.test_btn, 0)
        self.test_ring = ProgressRing(18)
        self.test_ring.hide()
        api_row.addWidget(self.test_ring, 0, Qt.AlignVCenter)
        api_row.addStretch(1)
        api_card.add(api_row)
        column.addWidget(api_card)

        # ---- overlay toggles ------------------------------------------
        overlay_card = Card("\u8986\u76d6\u5c42",
                            "\u63a7\u5236\u5c4f\u5e55\u4e0a\u7ed8\u5236\u7684\u5185\u5bb9")
        rows = [
            ("mask_check", "\u663e\u793a Mask \u906e\u7f69",
             "\u7528\u80cc\u666f\u8272\u76d6\u4f4f\u539f\u6587\u5b57"),
            ("boxes_check", "\u663e\u793a\u68c0\u6d4b\u6846",
             "\u6807\u51fa\u68c0\u6d4b\u5230\u7684\u6587\u5b57\u4f4d\u7f6e"),
            ("redbox_check", "\u663e\u793a\u533a\u57df\u8fb9\u6846",
             "\u6807\u51fa\u5f53\u524d\u7ffb\u8bd1\u533a\u57df\u7684\u8303\u56f4"),
            ("ocr_check", "\u6587\u5b57\u8bc6\u522b\uff08OCR\uff09",
             "\u4ece\u622a\u56fe\u4e2d\u63d0\u53d6\u6587\u5b57"),
            ("trans_check", "AI \u7ffb\u8bd1",
             "\u8c03\u7528 DeepSeek \u7ffb\u8bd1\u8bc6\u522b\u7ed3\u679c"),
        ]
        for i, (attr, name, hint) in enumerate(rows):
            toggle = ToggleSwitch()
            setattr(self, attr, toggle)
            if i:
                overlay_card.add(Divider())
            overlay_card.add(SettingsRow(name, hint, toggle))
        column.addWidget(overlay_card)

        # ---- filters ---------------------------------------------------
        self.reset_filter_btn = FluentButton("\u6062\u590d\u9ed8\u8ba4",
                                             "standard", font_size=13)
        self.reset_filter_btn.setMinimumHeight(30)
        self.reset_filter_btn.setFixedWidth(84)
        self.reset_filter_btn.setToolTip(
            "\u5c06\u4e0b\u9762\u56db\u9879\u6062\u590d\u4e3a\u9ed8\u8ba4\u503c")
        self.reset_filter_btn.clicked.connect(self._on_reset_filter_defaults)

        filter_card = Card("\u6587\u5b57\u8fc7\u6ee4\u53c2\u6570",
                           "\u8c03\u6574\u68c0\u6d4b\u7ed3\u679c\u7684\u7cbe\u7ec6\u5ea6",
                           action=self.reset_filter_btn)
        self._s_min_conf, self._l_min_conf = self._add_slider(
            filter_card, "\u6700\u4f4e\u7f6e\u4fe1\u5ea6", 10, 90, 50,
            "{:.2f}", 100.0)
        filter_card.add(Divider())
        self._s_min_asp, self._l_min_asp = self._add_slider(
            filter_card, "\u6587\u5b57\u957f\u5bbd\u6bd4", 12, 30, 18,
            "{:.1f}", 10.0)
        filter_card.add(Divider())
        self._s_max_icon, self._l_max_icon = self._add_slider(
            filter_card, "\u56fe\u6807\u5bbd\u9ad8\u6bd4", 10, 18, 14,
            "{:.1f}", 10.0)
        filter_card.add(Divider())
        self._s_min_area, self._l_min_area = self._add_slider(
            filter_card, "\u6700\u5c0f\u9762\u79ef\u6bd4", 1, 20, 5,
            "{:.3f}", 1000.0)
        column.addWidget(filter_card)

        # ---- performance -----------------------------------------------
        perf_card = Card("\u6027\u80fd",
                         "\u5237\u65b0\u7387\u4e0e\u7ed3\u679c\u663e\u793a\u65f6\u957f")
        self._s_fps, self._l_fps = self._add_slider(
            perf_card, "\u5237\u65b0\u9891\u7387", 1, 30, 10,
            "{:.0f}", 1.0)
        perf_card.add(Divider())
        self._s_once_display, self._l_once_display = self._add_slider(
            perf_card, "\u7ed3\u679c\u663e\u793a\u65f6\u957f\uff08\u79d2\uff09",
            1, 30, 5, "{:.0f}", 1.0)
        column.addWidget(perf_card)

        column.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # signal wiring
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
    def _make_combo(items, width: int) -> QComboBox:
        combo = QComboBox()
        combo.addItems(list(items))
        combo.setFixedWidth(width)
        combo.setFixedHeight(32)
        combo.setCursor(Qt.PointingHandCursor)
        return combo

    def _add_slider(self, card: Card, title: str, mn: int, mx: int, dv: int,
                    fmt: str, scale: float):
        """A settings row: title on the left, slider + value chip on the right."""
        slider = FluentSlider(mn, mx, dv)
        slider.setFixedWidth(150)

        value = QLabel(fmt.format(dv / scale))
        value.setProperty("role", "mono")
        value.setAlignment(Qt.AlignCenter)
        value.setFixedSize(56, 26)

        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Space.SM)
        row.addWidget(slider)
        row.addWidget(value)

        card.add(SettingsRow(title, "", holder))
        return slider, value

    # ==================================================================
    # animations / notifications
    # ==================================================================

    def _animate_height(self, target_h: int, duration: int = Motion.WINDOW) -> None:
        start = self.height()
        animate(self, "height", start, int(target_h),
                lambda v: self.setFixedHeight(int(v)),
                duration=duration, easing=QEasingCurve.OutCubic)

    def _settings_height(self) -> int:
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry().height() if screen else 900
        return max(560, min(880, available - 80))

    def _notify(self, text: str, tone: str = "info",
                duration: int = 2600) -> "InfoBar":
        # Anchor just above the footer: at the top the bar hid the headline and
        # the status badge, which is the information the user is looking for.
        # The bar is click-through, so the footer buttons stay usable.
        footer_h = 32 + Space.MD
        y = self.shell.height() - footer_h - InfoBar.HEIGHT - 6
        return InfoBar.push(self.shell, text, tone, duration, top_margin=y)

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
    # theme
    # ==================================================================

    def _on_theme_change(self, _index: int):
        mode = self.theme_combo.currentData() or MODE_SYSTEM
        ui = self.config_manager.get_ui_config()
        ui["theme_mode"] = mode
        self.config_manager.save_ui_config(ui)
        app = QApplication.instance()
        if app is not None:
            set_theme_mode(mode, app)
        self.update()

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
        hint = (f"\u6309\u4e0b {mod_str} + {key_str} "
                f"\u53ef\u968f\u65f6\u7ffb\u8bd1\u4e00\u6b21")
        self._hotkey_mod_combo.setToolTip(hint)
        self._hotkey_key_combo.setToolTip(hint)
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

        self.theme_combo.blockSignals(True)
        index = self.theme_combo.findData(ui.get("theme_mode", MODE_SYSTEM))
        self.theme_combo.setCurrentIndex(max(0, index))
        self.theme_combo.blockSignals(False)

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
        hint = (f"\u6309\u4e0b {mod_str} + {key_str} "
                f"\u53ef\u968f\u65f6\u7ffb\u8bd1\u4e00\u6b21")
        self._hotkey_mod_combo.setToolTip(hint)
        self._hotkey_key_combo.setToolTip(hint)

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
        return (f"{region['width']} \u00d7 {region['height']}"
                f"   \u00b7   ({region['x']}, {region['y']})")

    def _save_ui(self):
        ui = self.config_manager.get_ui_config()
        ui.update({
            "show_mask": self.mask_check.isChecked(),
            "show_boxes": self.boxes_check.isChecked(),
            "show_redbox": self.redbox_check.isChecked(),
            "show_ocr": self.ocr_check.isChecked(),
            "show_translation": self.trans_check.isChecked(),
            "fps_target": self._s_fps.value(),
            "once_display_seconds": self._s_once_display.value(),
            "once_hotkey_mod": self._hotkey_mod_combo.currentText(),
            "once_hotkey_key": self._hotkey_key_combo.currentText(),
            "theme_mode": self.theme_combo.currentData() or MODE_SYSTEM,
        })
        self.config_manager.save_ui_config(ui)

    # ==================================================================
    # settings interactions
    # ==================================================================

    def _on_f(self, key, raw, label, div, fmt):
        val = raw / div
        label.setText(fmt.format(val))
        tp = self.config_manager.get_text_processing_config()
        tp[key] = val
        self.config_manager.save_text_processing(tp)

    #: sliders shown in the "文字过滤参数" card and their config keys
    FILTER_KEYS = ("min_confidence", "min_text_aspect",
                   "max_icon_aspect", "min_area_ratio")

    @staticmethod
    def _filter_defaults() -> dict:
        """Defaults for the filter card, straight from the config module."""
        from config.config_manager import DEFAULT_CONFIG
        tp = DEFAULT_CONFIG["text_processing"]
        return {k: tp[k] for k in MainWindow.FILTER_KEYS}

    def _on_reset_filter_defaults(self):
        """Restore the four filter sliders to their shipped defaults."""
        defaults = self._filter_defaults()

        tp = self.config_manager.get_text_processing_config()
        tp.update(defaults)
        self.config_manager.save_text_processing(tp)

        # setValue also refreshes the value chips and re-saves each key
        self._s_min_conf.setValue(int(round(defaults["min_confidence"] * 100)))
        self._s_min_asp.setValue(int(round(defaults["min_text_aspect"] * 10)))
        self._s_max_icon.setValue(int(round(defaults["max_icon_aspect"] * 10)))
        self._s_min_area.setValue(int(round(defaults["min_area_ratio"] * 1000)))

        logger.info(f"Filter parameters restored to defaults: {defaults}")
        self._notify("\u6587\u5b57\u8fc7\u6ee4\u53c2\u6570\u5df2\u6062\u590d\u9ed8\u8ba4\u503c",
                     "success")

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
            self._notify("\u8bf7\u5148\u8f93\u5165 API \u5bc6\u94a5", "warn")
            QMessageBox.warning(self, "\u68c0\u67e5\u8fde\u901a\u6027",
                                "\u8bf7\u5148\u8f93\u5165API\u5bc6\u94a5")
            return

        self.test_ring.show()
        self.test_btn.setEnabled(False)
        self.test_btn.setText("\u68c0\u67e5\u4e2d")
        QApplication.instance().processEvents()
        try:
            import importlib
            import translation.deepseek_client as dsc
            importlib.reload(dsc)
            client = dsc.DeepSeekClient(api_key=key)
            result = client.translate("test")
            if result.get("translation") and not result.get("error"):
                self.test_btn.setText("\u8fde\u63a5\u6210\u529f")
                # let a freshly verified key take effect without a restart
                if self._pipeline is not None:
                    self._pipeline.refresh_translation()
                self._notify("\u2713  DeepSeek API \u8fde\u63a5\u6210\u529f",
                             "success")
            else:
                self.test_btn.setText("\u8fde\u63a5\u5931\u8d25")
                self._notify("\u8fde\u63a5\u5931\u8d25\uff1a"
                             f"{result.get('error', 'Unknown')}", "error", 3600)
                QMessageBox.critical(self, "\u8fde\u63a5\u5931\u8d25",
                                     f"API\u9519\u8bef: "
                                     f"{result.get('error', 'Unknown')}")
        except Exception as e:
            self.test_btn.setText("\u8fde\u63a5\u5931\u8d25")
            self._notify(f"\u8fde\u63a5\u5f02\u5e38\uff1a{str(e)[:40]}", "error",
                         3600)
            QMessageBox.critical(self, "\u8fde\u63a5\u5931\u8d25", str(e))
        finally:
            self.test_ring.hide()
            self.test_btn.setEnabled(True)
            QTimer.singleShot(
                2600, lambda: self.test_btn.setText("\u68c0\u67e5\u8fde\u901a\u6027"))

    def _on_toggle_settings(self):
        self._settings_visible = not self._settings_visible
        if self._settings_visible:
            self.stack.setCurrentIndex(1)
            self._animate_height(self._settings_height())
            self.settings_btn.setText("\u8fd4\u56de")
        else:
            self.stack.setCurrentIndex(0)
            self._animate_height(HOME_H)
            self.settings_btn.setText("\u8bbe\u7f6e")

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
            # models are still loading (or not loaded yet): queue the start
            self._pending_action = "start"
            self._init_pipeline()
            return
        if self._pipeline.start():
            self._pipeline.set_fps(self._s_fps.value())
            self._pipeline.show_mask = self.mask_check.isChecked()
            self._pipeline.ocr_enabled = self.ocr_check.isChecked()
            self._pipeline.trans_enabled = self.trans_check.isChecked()
            self._pipeline.overlay.show_boxes = self.boxes_check.isChecked()

            self.start_btn.setText("\u505c\u6b62\u7ffb\u8bd1")
            self.start_btn.set_variant("standard")
            self.status_badge.set_state("\u8fd0\u884c\u4e2d", "running")
            self._fps_timer.start(800)
            self.region_btn.setEnabled(False)
            self._update_tray_menu()
            reason = self._translation_block_reason()
            if reason:
                self._notify(
                    f"\u5df2\u5f00\u59cb\u8bc6\u522b\uff0c\u4f46{reason}\uff0c"
                    f"\u4e0d\u4f1a\u7ffb\u8bd1", "warn", 4600)
            else:
                self._notify("\u5df2\u5f00\u59cb\u5b9e\u65f6\u7ffb\u8bd1", "success")

    def _stop_all(self):
        if self._pipeline:
            self._pipeline.stop()
        self.start_btn.setText("\u5f00\u59cb\u7ffb\u8bd1")
        self.start_btn.set_variant("accent")
        self.status_badge.set_state("\u5c31\u7eea", "idle")
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
        self.status_badge.set_state("\u4e00\u6b21\u6027\u7ffb\u8bd1\u4e2d", "busy")

        if self._pipeline is None:
            # models load in the background; _poll_model_load resumes us
            self._pending_action = "once"
            self._init_pipeline()
            return

        self._run_once_translate()

    def _run_once_translate(self):
        """One-shot capture/detect/translate, run once the pipeline is ready."""
        if self._pipeline is None:
            self._set_once_done("\u6a21\u578b\u52a0\u8f7d\u5931\u8d25", "error")
            return

        self._once_was_running = self._pipeline.is_running
        if self._once_was_running:
            self._pipeline.stop()
            self.start_btn.setText("\u5f00\u59cb\u7ffb\u8bd1")
            self.start_btn.set_variant("accent")
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
                self._notify(
                    f"\u7ffb\u8bd1\u5b8c\u6210\uff0c{len(trans)} \u6761\u7ed3\u679c",
                    "success")
            elif ocr:
                self._pipeline._overlay.set_ocr_results(ocr)
                self._pipeline._overlay.show_ocr = True
                self._pipeline._overlay.show_translation = False
                reason = self._translation_block_reason()
                if reason:
                    # OCR worked but nothing could be translated - say why
                    # instead of reporting a plain "OCR 完成"
                    self._set_once_done(
                        f"OCR \u00b7 {len(ocr)} \u6761 \u00b7 {reason}", "busy")
                    self._notify(
                        f"\u5df2\u8bc6\u522b {len(ocr)} \u6761\u6587\u5b57\uff0c"
                        f"\u4f46{reason}\uff0c\u672a\u7ffb\u8bd1", "warn", 4600)
                else:
                    self._set_once_done(
                        f"OCR \u5b8c\u6210 \u00b7 {len(ocr)} \u6761", "ok")
                    self._notify(
                        f"\u8bc6\u522b\u5b8c\u6210\uff0c{len(ocr)} \u6761\u6587\u5b57",
                        "success")
            elif boxes:
                self._pipeline._overlay.show_ocr = False
                self._pipeline._overlay.show_translation = False
                self._set_once_done(
                    f"\u68c0\u6d4b\u5230 {len(boxes)} \u4e2a\u6587\u5b57\u533a\u57df",
                    "ok")
                self._notify(f"\u68c0\u6d4b\u5230 {len(boxes)} \u4e2a\u6587\u5b57\u533a\u57df",
                             "info")
            else:
                self._set_once_done("\u672a\u68c0\u6d4b\u5230\u6587\u5b57", "ready")
                self._notify("\u672a\u68c0\u6d4b\u5230\u6587\u5b57", "warn")

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

    def _translation_block_reason(self) -> str:
        """
        Why OCR results would not be translated (empty string = all good).

        Translation used to be skipped silently - the user only saw
        "OCR 完成" with a translation count of 0 and no clue why.
        """
        if not self.trans_check.isChecked():
            return "\u672a\u542f\u7528 AI \u7ffb\u8bd1"
        if self._pipeline is not None and not self._pipeline.translation_ready:
            return "\u672a\u914d\u7f6e API \u5bc6\u94a5"
        return ""

    def _set_once_done(self, text: str, state: str) -> None:
        self.status_badge.set_state(text, state)
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
        self._notify(
            f"\u5df2\u8bbe\u7f6e\u7ffb\u8bd1\u533a\u57df  {region['width']} \u00d7 "
            f"{region['height']}", "info")

    def _on_region_cancel(self):
        self._selector = None
        self.show()

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
        """
        Kick off model loading **without blocking the GUI thread**.

        ``DBNetDetector`` and ``PaddleOCREngine`` take seconds to build their
        ONNX/PaddleX predictors and used to be constructed right here, which
        froze the window (and its spinner) until they finished.  Neither has a
        Qt dependency, so they are built on a worker thread; the pipeline
        object itself owns an overlay widget and is therefore still created on
        the GUI thread, once the models are ready.
        """
        if self._pipeline_inited:
            return
        self._pipeline_inited = True

        want_ocr = self.ocr_check.isChecked()
        result = {"done": False, "detector": None, "ocr": None, "error": None}
        self._load_result = result
        self._set_loading(True)

        def work():
            try:
                from detection.dbnet_detector import DBNetDetector
                result["detector"] = DBNetDetector(limit_side_len=960)
            except Exception as exc:                       # noqa: BLE001
                logger.error(f"Detector load failed: {exc}", exc_info=True)
                result["error"] = exc
                result["done"] = True
                return
            if want_ocr:
                try:
                    from ocr.paddleocr_engine import PaddleOCREngine
                    result["ocr"] = PaddleOCREngine(lang="ch")
                except Exception as exc:                   # noqa: BLE001
                    # OCR is optional - the pipeline runs without it
                    logger.error(f"OCR load failed: {exc}", exc_info=True)
            result["done"] = True

        threading.Thread(target=work, daemon=True,
                         name="NexaTrans-model-loader").start()
        self._load_timer.start(80)

    def _set_loading(self, loading: bool) -> None:
        self._loading = loading
        self.load_ring.setVisible(loading)
        self.start_btn.set_busy(loading)
        self.start_btn.setEnabled(not loading)
        self.once_btn.setEnabled(not loading)
        if loading:
            self.start_btn.setText("\u52a0\u8f7d\u6a21\u578b")
            self.status_badge.set_state("\u52a0\u8f7d\u6a21\u578b", "busy")
        else:
            self.start_btn.setText("\u5f00\u59cb\u7ffb\u8bd1")

    def _poll_model_load(self):
        """GUI-thread poll for the worker started by :meth:`_init_pipeline`."""
        result = self._load_result
        if not result or not result.get("done"):
            return
        self._load_timer.stop()
        self._load_result = None

        detector = result["detector"]
        failed = (result["error"] is not None or detector is None
                  or not getattr(detector, "is_loaded", False))
        if failed:
            logger.error("Model load finished without a usable detector")
            self._pipeline = None
            self._pipeline_inited = False
            self._set_loading(False)
            self.status_badge.set_state("\u6a21\u578b\u52a0\u8f7d\u5931\u8d25",
                                        "error")
            pending, self._pending_action = self._pending_action, None
            if pending == "once":
                self._set_once_done("\u6a21\u578b\u52a0\u8f7d\u5931\u8d25", "error")
            return

        try:
            from detection.detection_pipeline import DetectionPipeline
            self._pipeline = DetectionPipeline(
                self.config_manager, target_fps=self._s_fps.value(),
                detector=detector, ocr_engine=result["ocr"])
        except Exception as exc:                           # noqa: BLE001
            logger.error(f"Pipeline init failed: {exc}", exc_info=True)
            self._pipeline = None
            self._pipeline_inited = False
            self._set_loading(False)
            self.status_badge.set_state("\u9519\u8bef", "error")
            pending, self._pending_action = self._pending_action, None
            if pending == "once":
                self._set_once_done("\u6a21\u578b\u52a0\u8f7d\u5931\u8d25", "error")
            return

        self._set_loading(False)
        self.status_badge.set_state("\u5c31\u7eea", "idle")
        logger.info("Pipeline ready")

        pending, self._pending_action = self._pending_action, None
        if pending == "start":
            self._start_all()
        elif pending == "once":
            self._run_once_translate()

    def _update_status(self):
        if not self._pipeline or not self._pipeline.is_running:
            return
        boxes = (self._pipeline.overlay._boxes
                 if hasattr(self._pipeline.overlay, "_boxes") else [])
        trans_count = getattr(self._pipeline, "trans_count", 0)

        self._chip_fps.set_value(self._pipeline.fps, animate_change=False)
        self._chip_boxes.set_value(len(boxes), animate_change=False)
        self._chip_trans.set_value(trans_count, animate_change=False)
        self.status_badge.set_state("\u8fd0\u884c\u4e2d", "running")
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
