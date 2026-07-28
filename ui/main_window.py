# -*- coding: utf-8 -*-
"""
NexaTrans - Main Window v1.1
System tray, settings persistence, FPS slider, translation stats.
"""

import os, logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QCheckBox, QSlider,
    QLineEdit, QFrame, QMessageBox, QApplication, QSystemTrayIcon, QMenu,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction

from config.config_manager import ConfigManager
from ui.selector_window import SelectorWindow
from ui.region_overlay import RegionOverlay

logger = logging.getLogger("NexaTrans.MainWindow")
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


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
        self._setup_ui()
        self._setup_tray()
        self._load_config()
        self._load_region()
        logger.info("MainWindow v1.1 ready")

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("NexaTrans")
        menu = QMenu()
        self._tray_status = QAction("\u25cf \u5c31\u7eea"); self._tray_status.setEnabled(False)
        menu.addAction(self._tray_status); menu.addSeparator()
        a = QAction("\u6253\u5f00\u4e3b\u754c\u9762"); a.triggered.connect(self._show_from_tray); menu.addAction(a)
        self._tray_toggle = QAction("\u5f00\u59cb\u7ffb\u8bd1"); self._tray_toggle.triggered.connect(self._on_start); menu.addAction(self._tray_toggle)
        menu.addSeparator()
        a = QAction("\u9000\u51fa\u7a0b\u5e8f"); a.triggered.connect(self._quit_app); menu.addAction(a)
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
        if self._pipeline: self._pipeline.cleanup()
        self._fps_timer.stop(); self._overlay.close(); self._tray.hide()
        QApplication.instance().quit()

    def _setup_ui(self):
        self.setWindowTitle("NexaTrans v1.1"); self.setFixedSize(380, 260)
        self.setStyleSheet("""
            QWidget { background: #1a1a2e; color: #eee; font-size: 13px; }
            QPushButton { background: #16213e; color: #0af; border: 1px solid #0af; border-radius: 6px; padding: 10px 20px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background: #1a3a5e; }
            QPushButton#startBtn { background: #0a6; color: #fff; border-color: #0c8; font-size: 16px; padding: 14px 0; }
            QPushButton#startBtn:hover { background: #0c8; }
            QPushButton#testBtn { background: #333; color: #fa0; border-color: #fa0; padding: 6px 12px; font-size: 12px; }
            QGroupBox { border: 1px solid #333; border-radius: 6px; margin-top: 8px; padding-top: 14px; color: #aaa; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QSlider::groove:horizontal { background: #333; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #0af; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            QCheckBox { spacing: 8px; } QCheckBox::indicator { width: 16px; height: 16px; }
            QLineEdit { background: #0d1117; color: #58a6ff; border: 1px solid #333; border-radius: 4px; padding: 6px 8px; }
        """)

        layout = QVBoxLayout(); layout.setContentsMargins(16, 14, 16, 14); layout.setSpacing(8)

        t = QLabel("NexaTrans"); t.setAlignment(Qt.AlignCenter)
        f = t.font(); f.setPointSize(22); f.setBold(True); t.setFont(f)
        t.setStyleSheet("color: #0af; background: transparent;"); layout.addWidget(t)

        v = QLabel("v1.1 - \u5c4f\u5e55\u5b9e\u65f6AI\u7ffb\u8bd1"); v.setAlignment(Qt.AlignCenter)
        v.setStyleSheet("color: #666; font-size: 11px; background: transparent;"); layout.addWidget(v)

        s = QFrame(); s.setFrameShape(QFrame.HLine); s.setStyleSheet("color: #333; background: transparent;"); layout.addWidget(s)

        self.start_btn = QPushButton("\u5f00\u59cb\u7ffb\u8bd1"); self.start_btn.setObjectName("startBtn")
        self.start_btn.setCursor(Qt.PointingHandCursor); self.start_btn.clicked.connect(self._on_start); layout.addWidget(self.start_btn)

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
        pf.setLayout(pfl); sl.addWidget(pf)

        self._settings_area.setLayout(sl); layout.addWidget(self._settings_area)

        self._s_min_conf.valueChanged.connect(lambda v: self._on_f("min_confidence", v, self._l_min_conf, 100.0, "{:.2f}"))
        self._s_min_asp.valueChanged.connect(lambda v: self._on_f("min_text_aspect", v, self._l_min_asp, 10.0, "{:.1f}"))
        self._s_max_icon.valueChanged.connect(lambda v: self._on_f("max_icon_aspect", v, self._l_max_icon, 10.0, "{:.1f}"))
        self._s_min_area.valueChanged.connect(lambda v: self._on_f("min_area_ratio", v, self._l_min_area, 1000.0, "{:.3f}"))
        self._s_fps.valueChanged.connect(self._on_fps_change)

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
        if ui.get("show_redbox", False):
            r = self.config_manager.load_region()
            if r.get("width", 0) > 0:
                self._overlay.update_region(r); self._overlay.set_test_visible(True)

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
        })

    def _on_f(self, key, raw, label, div, fmt):
        val = raw / div; label.setText(fmt.format(val))
        tp = self.config_manager.get_text_processing_config(); tp[key] = val
        self.config_manager.save_text_processing(tp)

    def _on_fps_change(self, v):
        self._l_fps.setText(str(v)); self._save_ui()
        if self._pipeline: self._pipeline.set_fps(v)

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
        self.setFixedSize(380, 700 if self._settings_visible else 260)

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
        self.start_btn.setEnabled(False)
        try:
            self._pipeline = DetectionPipeline(self.config_manager, target_fps=self._s_fps.value())
            if self._pipeline.detector.is_loaded:
                self.status_label.setText("\u25cf \u5c31\u7eea"); self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
            else: self.status_label.setText("\u25cf \u6a21\u578b\u52a0\u8f7d\u5931\u8d25"); self._pipeline = None
        except Exception as e:
            logger.error(f"Pipeline init failed: {e}"); self.status_label.setText("\u25cf \u9519\u8bef"); self._pipeline = None
        self.start_btn.setEnabled(True)

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
