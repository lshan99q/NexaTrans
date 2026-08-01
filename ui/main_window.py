# -*- coding: utf-8 -*-
"""
NexaTrans - Main Window v1.1
System tray, settings persistence, FPS slider, translation stats.
"""

import os, sys, logging, ctypes
from ctypes import wintypes
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QCheckBox, QSlider,
    QLineEdit, QFrame, QMessageBox, QApplication, QSystemTrayIcon, QMenu,
    QComboBox,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction, QKeySequence

from config.config_manager import ConfigManager
from ui.selector_window import SelectorWindow
from ui.region_overlay import RegionOverlay

logger = logging.getLogger("NexaTrans.MainWindow")
_FROZEN = getattr(sys, "frozen", False)
ENV_PATH = os.path.join(
    os.path.dirname(sys.executable) if _FROZEN else os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
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
              ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"]


def _read_env_key():
    try:
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        return line.strip().split("=", 1)[1].strip().strip("\"'")
    except: pass
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
                found = True; break
        if not found:
            lines.append(f"DEEPSEEK_API_KEY={key}\n")
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except: pass


def _make_tray_icon():
    pix = QPixmap(32, 32); pix.fill(Qt.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(0, 170, 255)); p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 28, 28, 8, 8)
    p.setPen(QColor(255, 255, 255))
    f = p.font(); f.setPixelSize(18); f.setBold(True); p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignCenter, "N"); p.end()
    return QIcon(pix)


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
        self._setup_ui()
        self._setup_tray()
        self._load_config()
        self._load_region()
        QTimer.singleShot(500, self._register_hotkey)
        logger.info("MainWindow v1.2 ready")

    # ---- native event for global hotkey ----
    def nativeEvent(self, eventType, message):
        if eventType == "windows_generic_MSG":
            try:
                ptr = ctypes.c_void_p(int(message))
                msg = ctypes.cast(ptr, ctypes.POINTER(_WinMSG)).contents
                if msg.message == WM_HOTKEY:
                    if msg.wParam == self._hotkey_id:
                        logger.info("Global hotkey triggered")
                        self._on_once_translate()
                        return True, 0
            except Exception as e:
                logger.debug(f"nativeEvent error (non-critical): {e}")
        return super().nativeEvent(eventType, message)

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("NexaTrans")
        menu = QMenu()
        self._tray_status = QAction("\u25cf \u5c31\u7eea"); self._tray_status.setEnabled(False)
        menu.addAction(self._tray_status); menu.addSeparator()
        self._tray_show = QAction("\u6253\u5f00\u4e3b\u754c\u9762"); self._tray_show.triggered.connect(self._show_from_tray); menu.addAction(self._tray_show)
        self._tray_toggle = QAction("\u5f00\u59cb\u7ffb\u8bd1"); self._tray_toggle.triggered.connect(self._on_start); menu.addAction(self._tray_toggle)
        self._tray_once = QAction("\u4e00\u6b21\u6027\u7ffb\u8bd1"); self._tray_once.triggered.connect(self._on_once_translate); menu.addAction(self._tray_once)
        menu.addSeparator()
        self._tray_quit = QAction("\u9000\u51fa\u7a0b\u5e8f"); self._tray_quit.triggered.connect(self._quit_app); menu.addAction(self._tray_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(lambda r: self._show_from_tray() if r == QSystemTrayIcon.DoubleClick else None)
        self._tray.show()

    def _show_from_tray(self): self.show(); self.raise_(); self.activateWindow()

    def _update_tray_menu(self):
        if self._pipeline and self._pipeline.is_running:
            boxes = self._pipeline.overlay._boxes if hasattr(self._pipeline.overlay, "_boxes") else []
            s = self._pipeline.is_static if hasattr(self._pipeline, "is_static") else True
            tc = self._pipeline.trans_count if hasattr(self._pipeline, "trans_count") else 0
            self._tray_status.setText(f"\u25cf \u8fd0\u884c\u4e2d | {self._pipeline.fps:.0f}FPS | {len(boxes)}\u6846 | \u7ffb\u8bd1:{tc}\u6b21")
            self._tray_toggle.setText("\u505c\u6b62\u7ffb\u8bd1")
        else:
            self._tray_status.setText("\u25cf \u5c31\u7eea")
            self._tray_toggle.setText("\u5f00\u59cb\u7ffb\u8bd1")

    def _quit_app(self):
        self._quitting = True
        self._unregister_hotkey()
        if self._pipeline:
            try: self._pipeline.cleanup()
            except: pass
        self._fps_timer.stop()
        self._overlay.close()
        self._tray.setVisible(False)
        self._tray.hide()
        self.hide()
        QApplication.instance().quit()
        import sys; sys.exit(0)

    # ---- hotkey ----
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
            result = ctypes.windll.user32.RegisterHotKey(hwnd, self._hotkey_id, modifier, vk)
            if result:
                self._hotkey_registered = True
                logger.info(f"Hotkey registered: {mod_str}+{key_str}")
            else:
                logger.warning(f"Hotkey registration failed (may be in use): {mod_str}+{key_str}")
        except Exception as e:
            logger.error(f"Hotkey register error: {e}")

    def _unregister_hotkey(self):
        if self._hotkey_registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(int(self.winId()), self._hotkey_id)
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
        self._hotkey_label.setText(f"\u5feb\u6377\u952e: {mod_str}+{key_str}")
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

    def _setup_ui(self):
        self.setWindowTitle("NexaTrans v1.2"); self.setFixedSize(420, 310)
        self.setStyleSheet("""
            QWidget { background: #1a1a2e; color: #eee; font-size: 13px; }
            QPushButton { background: #16213e; color: #0af; border: 1px solid #0af; border-radius: 6px; padding: 10px 20px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background: #1a3a5e; }
            QPushButton#startBtn { background: #0a6; color: #fff; border-color: #0c8; font-size: 16px; padding: 14px 0; }
            QPushButton#startBtn:hover { background: #0c8; }
            QPushButton#onceBtn { background: #1a5a8e; color: #fff; border-color: #2a7abe; font-size: 14px; padding: 10px 0; }
            QPushButton#onceBtn:hover { background: #2a6a9e; }
            QPushButton#onceBtn:disabled { background: #333; color: #666; border-color: #444; }
            QPushButton#testBtn { background: #333; color: #fa0; border-color: #fa0; padding: 6px 12px; font-size: 12px; }
            QGroupBox { border: 1px solid #333; border-radius: 6px; margin-top: 8px; padding-top: 14px; color: #aaa; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #0af; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QCheckBox { spacing: 8px; } QCheckBox::indicator { width: 16px; height: 16px; }
            QLineEdit { background: #0d1117; color: #58a6ff; border: 1px solid #333; border-radius: 4px; padding: 6px 8px; }
            QComboBox { background: #0d1117; color: #58a6ff; border: 1px solid #333; border-radius: 4px; padding: 4px 8px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #1a1a2e; color: #eee; selection-background-color: #16213e; }
        """)

        layout = QVBoxLayout(); layout.setContentsMargins(16, 14, 16, 14); layout.setSpacing(8)

        t = QLabel("NexaTrans"); t.setAlignment(Qt.AlignCenter)
        f = t.font(); f.setPointSize(22); f.setBold(True); t.setFont(f)
        t.setStyleSheet("color: #0af; background: transparent;"); layout.addWidget(t)

        v = QLabel("v1.2 - \u5c4f\u5e55AI\u7ffb\u8bd1 (\u8fde\u7eed+\u4e00\u6b21\u6027)"); v.setAlignment(Qt.AlignCenter)
        v.setStyleSheet("color: #666; font-size: 11px; background: transparent;"); layout.addWidget(v)

        s = QFrame(); s.setFrameShape(QFrame.HLine); s.setStyleSheet("color: #333; background: transparent;"); layout.addWidget(s)

        self.start_btn = QPushButton("\u5f00\u59cb\u7ffb\u8bd1"); self.start_btn.setObjectName("startBtn")
        self.start_btn.setCursor(Qt.PointingHandCursor); self.start_btn.clicked.connect(self._on_start); layout.addWidget(self.start_btn)

        # ---- One-time translation row ----
        once_row = QHBoxLayout()
        self.once_btn = QPushButton("\u4e00\u6b21\u6027\u7ffb\u8bd1"); self.once_btn.setObjectName("onceBtn")
        self.once_btn.setCursor(Qt.PointingHandCursor); self.once_btn.clicked.connect(self._on_once_translate)
        once_row.addWidget(self.once_btn, 3)

        hk_w = QWidget(); hk_w.setStyleSheet("background: transparent;")
        hk_layout = QHBoxLayout(); hk_layout.setContentsMargins(0, 0, 0, 0); hk_layout.setSpacing(4)
        hk_label = QLabel("\u5feb\u6377\u952e:")
        hk_label.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        hk_layout.addWidget(hk_label)

        self._hotkey_mod_combo = QComboBox(); self._hotkey_mod_combo.addItems(list(MOD_MAP.keys()))
        self._hotkey_mod_combo.setFixedWidth(85); self._hotkey_mod_combo.setFixedHeight(24)
        self._hotkey_mod_combo.setStyleSheet("font-size: 10px; padding: 2px 4px;")
        self._hotkey_mod_combo.currentTextChanged.connect(self._on_hotkey_change)
        hk_layout.addWidget(self._hotkey_mod_combo)

        hk_plus = QLabel("+"); hk_plus.setStyleSheet("color: #888; font-size: 10px; background: transparent;")
        hk_layout.addWidget(hk_plus)

        self._hotkey_key_combo = QComboBox(); self._hotkey_key_combo.addItems(HOTKEY_KEYS)
        self._hotkey_key_combo.setFixedWidth(50); self._hotkey_key_combo.setFixedHeight(24)
        self._hotkey_key_combo.setStyleSheet("font-size: 10px; padding: 2px 4px;")
        self._hotkey_key_combo.currentTextChanged.connect(self._on_hotkey_change)
        hk_layout.addWidget(self._hotkey_key_combo)

        hk_w.setLayout(hk_layout); once_row.addWidget(hk_w, 2)
        layout.addLayout(once_row)

        self._hotkey_label = QLabel("")
        self._hotkey_label.setAlignment(Qt.AlignCenter)
        self._hotkey_label.setStyleSheet("color: #666; font-size: 10px; background: transparent;")
        layout.addWidget(self._hotkey_label)

        br = QHBoxLayout()
        self.region_btn = QPushButton("\u6846\u9009\u533a\u57df"); self.region_btn.setCursor(Qt.PointingHandCursor)
        self.region_btn.clicked.connect(self._on_select_region); br.addWidget(self.region_btn)
        self.settings_btn = QPushButton("\u8bbe  \u7f6e"); self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self._on_toggle_settings); br.addWidget(self.settings_btn)
        layout.addLayout(br)

        self.region_info = QLabel("\u533a\u57df: \u672a\u9009\u62e9"); self.region_info.setAlignment(Qt.AlignCenter)
        self.region_info.setStyleSheet("color: #888; font-size: 11px; background: transparent;"); layout.addWidget(self.region_info)

        self.status_label = QLabel("\u25cf \u5c31\u7eea"); self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;"); layout.addWidget(self.status_label)

        self._trans_label = QLabel("\u7ffb\u8bd1\u6b21\u6570: 0"); self._trans_label.setAlignment(Qt.AlignCenter)
        self._trans_label.setStyleSheet("color: #666; font-size: 11px; background: transparent;"); layout.addWidget(self._trans_label)

        # Settings
        self._settings_area = QWidget(); self._settings_area.setVisible(False)
        sl = QVBoxLayout(); sl.setContentsMargins(0, 4, 0, 0); sl.setSpacing(6)

        ag = QGroupBox("DeepSeek API"); al = QVBoxLayout()
        self.api_key_input = QLineEdit(); self.api_key_input.setPlaceholderText("sk-...")
        self.api_key_input.setText(_read_env_key()); self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.textChanged.connect(self._on_api_key_change)
        al.addWidget(QLabel("API\u5bc6\u94a5:")); al.addWidget(self.api_key_input)
        self.test_btn = QPushButton("\u68c0\u67e5\u8fde\u901a\u6027"); self.test_btn.setObjectName("testBtn")
        self.test_btn.setCursor(Qt.PointingHandCursor); self.test_btn.clicked.connect(self._on_test_connection)
        al.addWidget(self.test_btn); ag.setLayout(al); sl.addWidget(ag)

        tg = QGroupBox("\u8986\u76d6\u5c42"); tfl = QVBoxLayout()
        self.mask_check = QCheckBox("\u663e\u793aMask\u906e\u7f69"); self.mask_check.toggled.connect(self._on_mask_toggle); tfl.addWidget(self.mask_check)
        self.boxes_check = QCheckBox("\u663e\u793a\u7eff\u6846"); self.boxes_check.toggled.connect(self._on_boxes_toggle); tfl.addWidget(self.boxes_check)
        self.redbox_check = QCheckBox("\u663e\u793a\u7ea2\u6846(\u7ffb\u8bd1\u533a\u57df)"); self.redbox_check.toggled.connect(self._on_redbox_toggle); tfl.addWidget(self.redbox_check)
        self.ocr_check = QCheckBox("\u542f\u7528OCR\u8bc6\u522b"); self.ocr_check.toggled.connect(self._on_ocr_toggle); tfl.addWidget(self.ocr_check)
        self.trans_check = QCheckBox("\u542f\u7528AI\u7ffb\u8bd1"); self.trans_check.toggled.connect(self._on_trans_toggle); tfl.addWidget(self.trans_check)
        tg.setLayout(tfl); sl.addWidget(tg)

        fg = QGroupBox("\u8fc7\u6ee4\u53c2\u6570"); ffl = QFormLayout()
        self._s_min_conf = self._make_s(10, 90, 50); self._l_min_conf = QLabel("0.50")
        ffl.addRow("\u6700\u4f4e\u7f6e\u4fe1\u5ea6:", self._make_sr(self._s_min_conf, self._l_min_conf))
        self._s_min_asp = self._make_s(12, 30, 18); self._l_min_asp = QLabel("1.8")
        ffl.addRow("\u6587\u5b57\u957f\u5bbd\u6bd4:", self._make_sr(self._s_min_asp, self._l_min_asp))
        self._s_max_icon = self._make_s(10, 18, 14); self._l_max_icon = QLabel("1.4")
        ffl.addRow("\u56fe\u6807\u5bbd\u9ad8\u6bd4:", self._make_sr(self._s_max_icon, self._l_max_icon))
        self._s_min_area = self._make_s(1, 20, 5); self._l_min_area = QLabel("0.005")
        ffl.addRow("\u6700\u5c0f\u9762\u79ef\u6bd4:", self._make_sr(self._s_min_area, self._l_min_area))
        fg.setLayout(ffl); sl.addWidget(fg)

        pf = QGroupBox("\u6027\u80fd"); pfl = QFormLayout()
        self._s_fps = self._make_s(1, 30, 10); self._l_fps = QLabel("10")
        pfl.addRow("\u5237\u65b0\u9891\u7387(FPS):", self._make_sr(self._s_fps, self._l_fps))
        self._s_once_display = self._make_s(1, 30, 5); self._l_once_display = QLabel("5")
        pfl.addRow("\u4e00\u6b21\u6027\u663e\u793a\u65f6\u957f(\u79d2):", self._make_sr(self._s_once_display, self._l_once_display))
        pf.setLayout(pfl); sl.addWidget(pf)

        self._settings_area.setLayout(sl); layout.addWidget(self._settings_area)

        self._s_min_conf.valueChanged.connect(lambda v: self._on_f("min_confidence", v, self._l_min_conf, 100.0, "{:.2f}"))
        self._s_min_asp.valueChanged.connect(lambda v: self._on_f("min_text_aspect", v, self._l_min_asp, 10.0, "{:.1f}"))
        self._s_max_icon.valueChanged.connect(lambda v: self._on_f("max_icon_aspect", v, self._l_max_icon, 10.0, "{:.1f}"))
        self._s_min_area.valueChanged.connect(lambda v: self._on_f("min_area_ratio", v, self._l_min_area, 1000.0, "{:.3f}"))
        self._s_fps.valueChanged.connect(self._on_fps_change)
        self._s_once_display.valueChanged.connect(self._on_once_display_change)

        layout.addStretch(); self.setLayout(layout)

    def _make_s(self, mn, mx, dv):
        s = QSlider(Qt.Horizontal); s.setRange(mn, mx); s.setValue(dv); return s

    def _make_sr(self, s, l):
        w = QWidget(); w.setStyleSheet("background: transparent;"); r = QHBoxLayout(); r.setContentsMargins(0, 0, 0, 0)
        r.addWidget(QLabel("\u4f4e")); r.addWidget(s); r.addWidget(QLabel("\u9ad8")); r.addWidget(l); w.setLayout(r); return w

    def _load_config(self):
        tp = self.config_manager.get_text_processing_config()
        self._s_min_conf.setValue(int(tp["min_confidence"] * 100))
        self._s_min_asp.setValue(int(tp["min_text_aspect"] * 10))
        self._s_max_icon.setValue(int(tp["max_icon_aspect"] * 10))
        self._s_min_area.setValue(int(tp["min_area_ratio"] * 1000))
        ui = self.config_manager.get_ui_config()
        self.mask_check.setChecked(ui.get("show_mask", False))
        self.boxes_check.setChecked(ui.get("show_boxes", True))
        self.redbox_check.setChecked(ui.get("show_redbox", False))
        self.ocr_check.setChecked(ui.get("show_ocr", True))
        self.trans_check.setChecked(ui.get("show_translation", True))
        fps = ui.get("fps_target", 10)
        self._s_fps.setValue(fps); self._l_fps.setText(str(fps))
        once_secs = ui.get("once_display_seconds", 5)
        self._s_once_display.setValue(once_secs); self._l_once_display.setText(str(once_secs))
        if ui.get("show_redbox", False):
            r = self.config_manager.load_region()
            if r.get("width", 0) > 0:
                self._overlay.update_region(r); self._overlay.set_test_visible(True)
        # Hotkey (block signals to avoid premature registration)
        mod_str = ui.get("once_hotkey_mod", DEFAULT_HOTKEY_MOD)
        key_str = ui.get("once_hotkey_key", DEFAULT_HOTKEY_KEY)
        self._hotkey_mod_combo.blockSignals(True)
        self._hotkey_key_combo.blockSignals(True)
        idx = self._hotkey_mod_combo.findText(mod_str)
        if idx >= 0: self._hotkey_mod_combo.setCurrentIndex(idx)
        idx2 = self._hotkey_key_combo.findText(key_str)
        if idx2 >= 0: self._hotkey_key_combo.setCurrentIndex(idx2)
        self._hotkey_mod_combo.blockSignals(False)
        self._hotkey_key_combo.blockSignals(False)
        self._hotkey_label.setText(f"\u5feb\u6377\u952e: {mod_str}+{key_str}")

    def _load_region(self):
        r = self.config_manager.load_region()
        if r.get("width", 0) > 0:
            self.region_info.setText(f"\u533a\u57df: ({r['x']},{r['y']}) {r['width']}x{r['height']}")
            self._overlay.update_region(r)

    def _save_ui(self):
        self.config_manager.save_ui_config({
            "show_mask": self.mask_check.isChecked(), "show_boxes": self.boxes_check.isChecked(),
            "show_redbox": self.redbox_check.isChecked(), "show_ocr": self.ocr_check.isChecked(),
            "show_translation": self.trans_check.isChecked(), "fps_target": self._s_fps.value(),
            "once_hotkey_mod": self._hotkey_mod_combo.currentText(),
            "once_hotkey_key": self._hotkey_key_combo.currentText(),
        })

    def _on_f(self, key, raw, label, div, fmt):
        val = raw / div; label.setText(fmt.format(val))
        tp = self.config_manager.get_text_processing_config(); tp[key] = val
        self.config_manager.save_text_processing(tp)

    def _on_fps_change(self, v):
        self._l_fps.setText(str(v)); self._save_ui()
        if self._pipeline: self._pipeline.set_fps(v)

    def _on_once_display_change(self, v):
        self._l_once_display.setText(str(v)); self._save_ui()

    def _on_api_key_change(self, text): _write_env_key(text.strip())

    def _on_test_connection(self):
        key = self.api_key_input.text().strip()
        if not key: QMessageBox.warning(self, "\u68c0\u67e5\u8fde\u901a\u6027", "\u8bf7\u5148\u8f93\u5165API\u5bc6\u94a5"); return
        self.test_btn.setText("\u68c0\u67e5\u4e2d..."); self.test_btn.setEnabled(False); QApplication.instance().processEvents()
        try:
            from translation.deepseek_client import DeepSeekClient; import importlib, translation.deepseek_client as dsc
            importlib.reload(dsc); client = dsc.DeepSeekClient(api_key=key); result = client.translate("test")
            if result.get("translation") and not result.get("error"):
                self.test_btn.setText("\u8fde\u63a5\u6210\u529f")
                self.test_btn.setStyleSheet("QPushButton#testBtn { background: #333; color: #0c8; border-color: #0c8; padding: 6px 12px; font-size: 12px; }")
            else:
                self.test_btn.setText("\u8fde\u63a5\u5931\u8d25")
                self.test_btn.setStyleSheet("QPushButton#testBtn { background: #333; color: #e44; border-color: #e44; padding: 6px 12px; font-size: 12px; }")
                QMessageBox.critical(self, "\u8fde\u63a5\u5931\u8d25", f"API\u9519\u8bef: {result.get('error', 'Unknown')}")
        except Exception as e:
            self.test_btn.setText("\u8fde\u63a5\u5931\u8d25")
            self.test_btn.setStyleSheet("QPushButton#testBtn { background: #333; color: #e44; border-color: #e44; padding: 6px 12px; font-size: 12px; }")
            QMessageBox.critical(self, "\u8fde\u63a5\u5931\u8d25", str(e))
        finally: self.test_btn.setEnabled(True)

    def _on_start(self):
        if self._pipeline and self._pipeline.is_running: self._stop_all()
        else: self._start_all()

    def _start_all(self):
        if self._pipeline is None: self._init_pipeline()
        if self._pipeline is None: return
        if self._pipeline.start():
            self._pipeline.set_fps(self._s_fps.value())
            self._pipeline.show_mask = self.mask_check.isChecked()
            self._pipeline.ocr_enabled = self.ocr_check.isChecked()
            self._pipeline.trans_enabled = self.trans_check.isChecked()
            self._pipeline.overlay.show_boxes = self.boxes_check.isChecked()
            self.start_btn.setText("\u505c\u6b62\u7ffb\u8bd1")
            self.start_btn.setStyleSheet("QPushButton#startBtn { background: #c22; color: #fff; border-color: #e44; font-size: 16px; padding: 14px 0; border-radius: 6px; } QPushButton#startBtn:hover { background: #e44; }")
            self.status_label.setText("\u25cf \u8fd0\u884c\u4e2d"); self.status_label.setStyleSheet("color: #0c8; font-size: 12px; background: transparent;")
            self._fps_timer.start(500); self.region_btn.setEnabled(False); self._update_tray_menu()

    def _stop_all(self):
        if self._pipeline: self._pipeline.stop()
        self.start_btn.setText("\u5f00\u59cb\u7ffb\u8bd1")
        self.start_btn.setStyleSheet("QPushButton#startBtn { background: #0a6; color: #fff; border-color: #0c8; font-size: 16px; padding: 14px 0; border-radius: 6px; } QPushButton#startBtn:hover { background: #0c8; }")
        self.status_label.setText("\u25cf \u5c31\u7eea"); self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        self._fps_timer.stop(); self.region_btn.setEnabled(True); self._update_tray_menu()

    # ---- one-time translation ----
    def _on_once_translate(self):
        if self._once_busy: return
        self._once_busy = True
        self.once_btn.setEnabled(False)
        self.once_btn.setText("\u7ffb\u8bd1\u4e2d...")
        self.once_btn.setStyleSheet("QPushButton#onceBtn { background: #555; color: #fa0; border-color: #fa0; font-size: 14px; padding: 10px 0; }")
        self.status_label.setText("\u25cf \u4e00\u6b21\u6027\u7ffb\u8bd1\u4e2d...")
        self.status_label.setStyleSheet("color: #fa0; font-size: 12px; background: transparent;")

        if self._pipeline is None:
            self._init_pipeline()
        if self._pipeline is None:
            self._set_once_done("\u2717 \u6a21\u578b\u52a0\u8f7d\u5931\u8d25", "#e44")
            return

        # Stop continuous pipeline if running to avoid overwriting results
        self._once_was_running = self._pipeline.is_running
        if self._once_was_running:
            self._pipeline.stop()
            self.start_btn.setText("\u5f00\u59cb\u7ffb\u8bd1")
            self.start_btn.setStyleSheet("QPushButton#startBtn { background: #0a6; color: #fff; border-color: #0c8; font-size: 16px; padding: 14px 0; border-radius: 6px; } QPushButton#startBtn:hover { background: #0c8; }")
            self._fps_timer.stop()
            self.region_btn.setEnabled(True)

        # Cancel any pending display timer
        self._once_display_timer.stop()

        # Sync pipeline settings from UI (critical for first use: initializes OCR/trans/mask)
        self._pipeline.show_mask = self.mask_check.isChecked()
        self._pipeline.ocr_enabled = self.ocr_check.isChecked()
        self._pipeline.trans_enabled = self.trans_check.isChecked()
        self._pipeline.overlay.show_boxes = self.boxes_check.isChecked()
        # Set correct DPR for coordinate calculation
        self._pipeline._dpr = self._pipeline._dpr_get()

        # Update overlay region
        region = self.config_manager.load_region()
        self._pipeline._overlay.update_region(region)
        self._pipeline._last_region = dict(region)
        self._pipeline._overlay.show_overlay()

        try:
            result = self._pipeline.capture_once()
            if result is None:
                self._set_once_done("\u2717 \u6355\u83b7\u5931\u8d25", "#e44")
                return
            boxes = result.get("boxes", [])
            trans = result.get("trans", [])
            ocr = result.get("ocr", [])
            mask = result.get("mask")
            colors = result.get("colors")

            # Update overlay and lock sent state
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
                self._set_once_done(f"\u2713 \u7ffb\u8bd1\u5b8c\u6210 ({len(boxes)}\u6846/{len(trans)}\u6761)", "#0c8")
            elif ocr:
                self._pipeline._overlay.set_ocr_results(ocr)
                self._pipeline._overlay.show_ocr = True
                self._pipeline._overlay.show_translation = False
                self._set_once_done(f"\u2713 OCR\u5b8c\u6210 ({len(boxes)}\u6846/{len(ocr)}\u6761)", "#0c8")
            elif boxes:
                self._pipeline._overlay.show_ocr = False
                self._pipeline._overlay.show_translation = False
                self._set_once_done(f"\u2713 \u68c0\u6d4b\u5230 {len(boxes)} \u4e2a\u6587\u5b57\u533a\u57df", "#0c8")
            else:
                self._set_once_done(f"\u25cb \u672a\u68c0\u6d4b\u5230\u6587\u5b57", "#888")

            self._trans_label.setText(f"\u7ffb\u8bd1\u6b21\u6570: {self._pipeline.trans_count}")

            # Start auto-dismiss timer
            secs = self._s_once_display.value()
            if secs > 0:
                self._once_display_timer.start(secs * 1000)

        except Exception as e:
            logger.error(f"One-time translation failed: {e}", exc_info=True)
            self._set_once_done(f"\u2717 \u9519\u8bef: {str(e)[:30]}", "#e44")

    def _clear_once_overlay(self):
        if self._pipeline and not self._pipeline.is_running:
            self._pipeline._overlay.set_data([], None, None)
            self._pipeline._overlay.set_ocr_results([])
            self._pipeline._overlay.set_trans_results([])
            self._pipeline._overlay.hide_overlay()
        self._update_tray_menu()

    def _set_once_done(self, text, color):
        self.status_label.setText(f"\u25cf {text}")
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
        self.once_btn.setText("\u4e00\u6b21\u6027\u7ffb\u8bd1")
        self.once_btn.setEnabled(True)
        self.once_btn.setStyleSheet("QPushButton#onceBtn { background: #1a5a8e; color: #fff; border-color: #2a7abe; font-size: 14px; padding: 10px 0; } QPushButton#onceBtn:hover { background: #2a6a9e; }")
        self._once_busy = False

    def _on_select_region(self):
        if self._overlay.isVisible(): self._overlay.hide()
        self.hide()
        self._selector = SelectorWindow(self.config_manager.get_overlay_config())
        self._selector.region_selected.connect(self._on_region_done)
        self._selector.cancelled.connect(self._on_region_cancel)

    def _on_region_done(self, region):
        self._selector = None
        self.config_manager.save_region(region)
        self.region_info.setText(f"\u533a\u57df: ({region['x']},{region['y']}) {region['width']}x{region['height']}")
        self._overlay.update_region(region)
        if self.redbox_check.isChecked(): self._overlay.set_test_visible(True)
        self.show()

    def _on_region_cancel(self): self._selector = None; self.show()

    def _on_toggle_settings(self):
        self._settings_visible = not self._settings_visible; self._settings_area.setVisible(self._settings_visible)
        self.settings_btn.setText("\u9690\u85cf\u8bbe\u7f6e" if self._settings_visible else "\u8bbe  \u7f6e")
        self.setFixedSize(420, 800 if self._settings_visible else 310)

    def _on_mask_toggle(self, c): self._save_ui(); (lambda: setattr(self._pipeline, "show_mask", c))() if self._pipeline else None
    def _on_boxes_toggle(self, c): self._save_ui(); (lambda: setattr(self._pipeline.overlay, "show_boxes", c))() if self._pipeline and self._pipeline.overlay else None
    def _on_redbox_toggle(self, c):
        self._save_ui()
        if c:
            r = self.config_manager.load_region()
            if r.get("width", 0) > 0: self._overlay.update_region(r)
        self._overlay.set_test_visible(c)
    def _on_ocr_toggle(self, c): self._save_ui(); (lambda: setattr(self._pipeline, "ocr_enabled", c))() if self._pipeline else None
    def _on_trans_toggle(self, c): self._save_ui(); (lambda: setattr(self._pipeline, "trans_enabled", c))() if self._pipeline else None

    def _init_pipeline(self):
        from detection.detection_pipeline import DetectionPipeline
        self.status_label.setText("\u25cf \u52a0\u8f7d\u6a21\u578b..."); self.status_label.setStyleSheet("color: #fa0; font-size: 12px; background: transparent;")
        self.start_btn.setEnabled(False); self.once_btn.setEnabled(False)
        try:
            self._pipeline = DetectionPipeline(self.config_manager, target_fps=self._s_fps.value())
            if self._pipeline.detector.is_loaded:
                self.status_label.setText("\u25cf \u5c31\u7eea"); self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
            else: self.status_label.setText("\u25cf \u6a21\u578b\u52a0\u8f7d\u5931\u8d25"); self._pipeline = None
        except Exception as e:
            logger.error(f"Pipeline init failed: {e}"); self.status_label.setText("\u25cf \u9519\u8bef"); self._pipeline = None
        self.start_btn.setEnabled(True); self.once_btn.setEnabled(True)

    def _update_status(self):
        if not self._pipeline or not self._pipeline.is_running: return
        boxes = self._pipeline.overlay._boxes if hasattr(self._pipeline.overlay, "_boxes") else []
        s = self._pipeline.is_static if hasattr(self._pipeline, "is_static") else True
        tc = self._pipeline.trans_count if hasattr(self._pipeline, "trans_count") else 0
        self.status_label.setText(f"\u25cf \u8fd0\u884c\u4e2d | {self._pipeline.fps:.0f}FPS | {len(boxes)}\u6846 | { '\u9759\u6001' if s else '\u52a8\u6001' }")
        self._trans_label.setText(f"\u7ffb\u8bd1\u6b21\u6570: {tc}")
        self._update_tray_menu()

    def closeEvent(self, event):
        if self._quitting: super().closeEvent(event)
        else:
            self.hide()
            self._tray.showMessage("NexaTrans", "\u7a0b\u5e8f\u5df2\u6700\u5c0f\u5316\u5230\u6258\u76d8\uff0c\u53cc\u51fb\u6258\u76d8\u56fe\u6807\u53ef\u91cd\u65b0\u6253\u5f00", QSystemTrayIcon.Information, 2000)
            event.ignore()