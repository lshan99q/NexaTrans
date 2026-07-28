# -*- coding: utf-8 -*-
"""
NexaTrans - Main Window v1.1
System tray: minimize to tray, background translation, tray controls.
"""

import os
import logging
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
    """Generate a simple N icon for tray."""
    pix = QPixmap(32, 32)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(0, 170, 255))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(2, 2, 28, 28, 8, 8)
    p.setPen(QColor(255, 255, 255))
    f = p.font(); f.setPixelSize(18); f.setBold(True); p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignCenter, "N")
    p.end()
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

    # ═══════════════ System Tray ═══════════════

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon())
        self._tray.setToolTip("NexaTrans")

        menu = QMenu()

        self._tray_status = QAction("● 就绪")
        self._tray_status.setEnabled(False)
        menu.addAction(self._tray_status)
        menu.addSeparator()

        show_action = QAction("打开主界面")
        show_action.triggered.connect(self._show_from_tray)
        menu.addAction(show_action)

        self._tray_toggle = QAction("开始翻译")
        self._tray_toggle.triggered.connect(self._on_start)
        menu.addAction(self._tray_toggle)
        menu.addSeparator()

        quit_action = QAction("退出程序")
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _update_tray_menu(self):
        if self._pipeline and self._pipeline.is_running:
            boxes = self._pipeline.overlay._boxes if hasattr(self._pipeline.overlay, "_boxes") else []
            static = self._pipeline.is_static if hasattr(self._pipeline, "is_static") else True
            self._tray_status.setText(
                f"● 运行中 | {self._pipeline.fps:.0f}FPS | {len(boxes)}框 | {'静态' if static else '动态'}")
            self._tray_toggle.setText("停止翻译")
        else:
            self._tray_status.setText("● 就绪")
            self._tray_toggle.setText("开始翻译")

    def _quit_app(self):
        self._quitting = True
        if self._pipeline:
            self._pipeline.cleanup()
        self._fps_timer.stop()
        self._overlay.close()
        self._tray.hide()
        QApplication.instance().quit()

    # ═══════════════ UI Setup ═══════════════

    def _setup_ui(self):
        self.setWindowTitle("NexaTrans v1.1")
        self.setFixedSize(380, 260)

        css = """
            QWidget { background: #1a1a2e; color: #eee; font-size: 13px; }
            QPushButton {
                background: #16213e; color: #0af; border: 1px solid #0af;
                border-radius: 6px; padding: 10px 20px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: #1a3a5e; }
            QPushButton:pressed { background: #0d1b36; }
            QPushButton#startBtn {
                background: #0a6; color: #fff; border-color: #0c8; font-size: 16px;
                padding: 14px 0;
            }
            QPushButton#startBtn:hover { background: #0c8; }
            QPushButton#testBtn {
                background: #333; color: #fa0; border-color: #fa0;
                padding: 6px 12px; font-size: 12px;
            }
            QPushButton#testBtn:hover { background: #554400; }
            QGroupBox {
                border: 1px solid #333; border-radius: 6px; margin-top: 8px;
                padding-top: 14px; color: #aaa; font-weight: bold;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
            QSlider::groove:horizontal {
                background: #333; height: 4px; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #0af; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QLineEdit {
                background: #0d1117; color: #58a6ff; border: 1px solid #333;
                border-radius: 4px; padding: 6px 8px; font-family: Consolas;
            }
        """
        self.setStyleSheet(css)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel("NexaTrans")
        title.setAlignment(Qt.AlignCenter)
        f = title.font(); f.setPointSize(22); f.setBold(True); title.setFont(f)
        title.setStyleSheet("color: #0af; background: transparent;")
        layout.addWidget(title)

        ver = QLabel("v1.1 - 屏幕实时AI翻译")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color: #666; font-size: 11px; background: transparent;")
        layout.addWidget(ver)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #333; background: transparent;")
        layout.addWidget(sep)

        self.start_btn = QPushButton("开始翻译")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start)
        layout.addWidget(self.start_btn)

        btn_row = QHBoxLayout()
        self.region_btn = QPushButton("框选区域")
        self.region_btn.setCursor(Qt.PointingHandCursor)
        self.region_btn.clicked.connect(self._on_select_region)
        btn_row.addWidget(self.region_btn)

        self.settings_btn = QPushButton("设  置")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self._on_toggle_settings)
        btn_row.addWidget(self.settings_btn)
        layout.addLayout(btn_row)

        self.region_info = QLabel("区域: 未选择")
        self.region_info.setAlignment(Qt.AlignCenter)
        self.region_info.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        layout.addWidget(self.region_info)

        self.status_label = QLabel("● 就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        layout.addWidget(self.status_label)

        # ═══════════════ Settings ═══════════════
        self._settings_area = QWidget()
        self._settings_area.setVisible(False)
        sl = QVBoxLayout()
        sl.setContentsMargins(0, 4, 0, 0)
        sl.setSpacing(6)

        ag = QGroupBox("DeepSeek API")
        al = QVBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxx")
        self.api_key_input.setText(_read_env_key())
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.textChanged.connect(self._on_api_key_change)
        al.addWidget(QLabel("API密钥:"))
        al.addWidget(self.api_key_input)

        self.test_btn = QPushButton("检查连通性")
        self.test_btn.setObjectName("testBtn")
        self.test_btn.setCursor(Qt.PointingHandCursor)
        self.test_btn.clicked.connect(self._on_test_connection)
        al.addWidget(self.test_btn)
        ag.setLayout(al)
        sl.addWidget(ag)

        tg = QGroupBox("覆盖层")
        tfl = QVBoxLayout()
        self.mask_check = QCheckBox("显示Mask遮罩")
        self.mask_check.toggled.connect(self._on_mask_toggle)
        tfl.addWidget(self.mask_check)
        self.boxes_check = QCheckBox("显示绿框")
        self.boxes_check.toggled.connect(self._on_boxes_toggle)
        tfl.addWidget(self.boxes_check)
        self.redbox_check = QCheckBox("显示红框(翻译区域)")
        self.redbox_check.toggled.connect(self._on_redbox_toggle)
        tfl.addWidget(self.redbox_check)
        self.ocr_check = QCheckBox("启用OCR识别")
        self.ocr_check.toggled.connect(self._on_ocr_toggle)
        tfl.addWidget(self.ocr_check)
        self.trans_check = QCheckBox("启用AI翻译")
        self.trans_check.toggled.connect(self._on_trans_toggle)
        tfl.addWidget(self.trans_check)
        tg.setLayout(tfl)
        sl.addWidget(tg)

        fg = QGroupBox("过滤参数")
        ffl = QFormLayout()
        self._s_min_conf = self._make_s(10, 90, 50)
        self._l_min_conf = QLabel("0.50")
        ffl.addRow("最低置信度:", self._make_sr(self._s_min_conf, self._l_min_conf))
        self._s_min_asp = self._make_s(12, 30, 18)
        self._l_min_asp = QLabel("1.8")
        ffl.addRow("文字长宽比:", self._make_sr(self._s_min_asp, self._l_min_asp))
        self._s_max_icon = self._make_s(10, 18, 14)
        self._l_max_icon = QLabel("1.4")
        ffl.addRow("图标宽高比:", self._make_sr(self._s_max_icon, self._l_max_icon))
        self._s_min_area = self._make_s(1, 20, 5)
        self._l_min_area = QLabel("0.005")
        ffl.addRow("最小面积比:", self._make_sr(self._s_min_area, self._l_min_area))
        fg.setLayout(ffl)
        sl.addWidget(fg)

        self._settings_area.setLayout(sl)
        layout.addWidget(self._settings_area)

        self._s_min_conf.valueChanged.connect(
            lambda v: self._on_f("min_confidence", v, self._l_min_conf, 100.0, "{:.2f}"))
        self._s_min_asp.valueChanged.connect(
            lambda v: self._on_f("min_text_aspect", v, self._l_min_asp, 10.0, "{:.1f}"))
        self._s_max_icon.valueChanged.connect(
            lambda v: self._on_f("max_icon_aspect", v, self._l_max_icon, 10.0, "{:.1f}"))
        self._s_min_area.valueChanged.connect(
            lambda v: self._on_f("min_area_ratio", v, self._l_min_area, 1000.0, "{:.3f}"))

        layout.addStretch()
        self.setLayout(layout)

    def _make_s(self, mn, mx, dv):
        s = QSlider(Qt.Horizontal); s.setRange(mn, mx); s.setValue(dv); return s

    def _make_sr(self, s, l):
        w = QWidget(); w.setStyleSheet("background: transparent;")
        r = QHBoxLayout(); r.setContentsMargins(0, 0, 0, 0)
        r.addWidget(QLabel("低")); r.addWidget(s); r.addWidget(QLabel("高")); r.addWidget(l)
        w.setLayout(r); return w

    # ═══════════════ Config ═══════════════

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
        if ui.get("show_redbox", False):
            r = self.config_manager.load_region()
            if r.get("width", 0) > 0:
                self._overlay.update_region(r)
                self._overlay.set_test_visible(True)

    def _load_region(self):
        r = self.config_manager.load_region()
        if r.get("width", 0) > 0:
            self.region_info.setText(f"区域: ({r['x']},{r['y']}) {r['width']}x{r['height']}")
            self._overlay.update_region(r)

    def _save_ui(self):
        self.config_manager.save_ui_config({
            "show_mask": self.mask_check.isChecked(),
            "show_boxes": self.boxes_check.isChecked(),
            "show_redbox": self.redbox_check.isChecked(),
            "show_ocr": self.ocr_check.isChecked(),
            "show_translation": self.trans_check.isChecked(),
        })

    def _on_f(self, key, raw, label, div, fmt):
        val = raw / div; label.setText(fmt.format(val))
        tp = self.config_manager.get_text_processing_config()
        tp[key] = val
        self.config_manager.save_text_processing(tp)

    # ═══════════════ API ═══════════════

    def _on_api_key_change(self, text):
        _write_env_key(text.strip())

    def _on_test_connection(self):
        key = self.api_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "检查连通性", "请先输入API密钥")
            return
        self.test_btn.setText("检查中...")
        self.test_btn.setEnabled(False)
        QApplication.instance().processEvents()
        try:
            from translation.deepseek_client import DeepSeekClient
            import importlib, translation.deepseek_client as dsc
            importlib.reload(dsc)
            client = dsc.DeepSeekClient(api_key=key)
            result = client.translate("test")
            if result.get("translation") and not result.get("error"):
                self.test_btn.setText("连接成功")
                self.test_btn.setStyleSheet(
                    "QPushButton#testBtn { background: #333; color: #0c8; "
                    "border-color: #0c8; padding: 6px 12px; font-size: 12px; }")
            else:
                self.test_btn.setText("连接失败")
                self.test_btn.setStyleSheet(
                    "QPushButton#testBtn { background: #333; color: #e44; "
                    "border-color: #e44; padding: 6px 12px; font-size: 12px; }")
                QMessageBox.critical(self, "连接失败",
                    f"API错误: {result.get('error', 'Unknown')}")
        except Exception as e:
            self.test_btn.setText("连接失败")
            self.test_btn.setStyleSheet(
                "QPushButton#testBtn { background: #333; color: #e44; "
                "border-color: #e44; padding: 6px 12px; font-size: 12px; }")
            QMessageBox.critical(self, "连接失败", str(e))
        finally:
            self.test_btn.setEnabled(True)

    # ═══════════════ Start / Stop ═══════════════

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
            self._pipeline.show_mask = self.mask_check.isChecked()
            self._pipeline.ocr_enabled = self.ocr_check.isChecked()
            self._pipeline.trans_enabled = self.trans_check.isChecked()
            self._pipeline.overlay.show_boxes = self.boxes_check.isChecked()

            self.start_btn.setText("停止翻译")
            self.start_btn.setStyleSheet("""
                QPushButton#startBtn {
                    background: #c22; color: #fff; border-color: #e44;
                    font-size: 16px; padding: 14px 0; border-radius: 6px;
                }
                QPushButton#startBtn:hover { background: #e44; }
            """)
            self.status_label.setText("● 运行中")
            self.status_label.setStyleSheet("color: #0c8; font-size: 12px; background: transparent;")
            self._fps_timer.start(500)
            self.region_btn.setEnabled(False)
            self._update_tray_menu()
        else:
            self.status_label.setText("● 启动失败")
            self.status_label.setStyleSheet("color: #e44; font-size: 12px; background: transparent;")

    def _stop_all(self):
        if self._pipeline:
            self._pipeline.stop()
        self.start_btn.setText("开始翻译")
        self.start_btn.setStyleSheet("""
            QPushButton#startBtn {
                background: #0a6; color: #fff; border-color: #0c8;
                font-size: 16px; padding: 14px 0; border-radius: 6px;
            }
            QPushButton#startBtn:hover { background: #0c8; }
        """)
        self.status_label.setText("● 就绪")
        self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        self._fps_timer.stop()
        self.region_btn.setEnabled(True)
        self._update_tray_menu()

    # ═══════════════ Region ═══════════════

    def _on_select_region(self):
        if self._overlay.isVisible(): self._overlay.hide()
        self.hide()
        self._selector = SelectorWindow(self.config_manager.get_overlay_config())
        self._selector.region_selected.connect(self._on_region_done)
        self._selector.cancelled.connect(self._on_region_cancel)

    def _on_region_done(self, region):
        self._selector = None
        self.config_manager.save_region(region)
        self.region_info.setText(f"区域: ({region['x']},{region['y']}) {region['width']}x{region['height']}")
        self._overlay.update_region(region)
        if self.redbox_check.isChecked():
            self._overlay.set_test_visible(True)
        self.show()

    def _on_region_cancel(self):
        self._selector = None
        self.show()

    def _on_toggle_settings(self):
        self._settings_visible = not self._settings_visible
        self._settings_area.setVisible(self._settings_visible)
        if self._settings_visible:
            self.settings_btn.setText("隐藏设置")
            self.setFixedSize(380, 640)
        else:
            self.settings_btn.setText("设  置")
            self.setFixedSize(380, 260)

    # ═══════════════ Toggles ═══════════════

    def _on_mask_toggle(self, checked):
        self._save_ui()
        if self._pipeline:
            self._pipeline.show_mask = checked

    def _on_boxes_toggle(self, checked):
        self._save_ui()
        if self._pipeline and self._pipeline.overlay:
            self._pipeline.overlay.show_boxes = checked

    def _on_redbox_toggle(self, checked):
        self._save_ui()
        if checked:
            r = self.config_manager.load_region()
            if r.get("width", 0) > 0:
                self._overlay.update_region(r)
        self._overlay.set_test_visible(checked)

    def _on_ocr_toggle(self, checked):
        self._save_ui()
        if self._pipeline:
            self._pipeline.ocr_enabled = checked

    def _on_trans_toggle(self, checked):
        self._save_ui()
        if self._pipeline:
            self._pipeline.trans_enabled = checked

    # ═══════════════ Pipeline ═══════════════

    def _init_pipeline(self):
        from detection.detection_pipeline import DetectionPipeline
        self.status_label.setText("● 加载模型...")
        self.status_label.setStyleSheet("color: #fa0; font-size: 12px; background: transparent;")
        self.start_btn.setEnabled(False)
        try:
            self._pipeline = DetectionPipeline(self.config_manager, target_fps=15)
            if self._pipeline.detector.is_loaded:
                self.status_label.setText("● 就绪")
                self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
            else:
                self.status_label.setText("● 模型加载失败")
                self._pipeline = None
        except Exception as e:
            logger.error(f"Pipeline init failed: {e}")
            self.status_label.setText("● 错误")
            self._pipeline = None
        self.start_btn.setEnabled(True)

    def _update_status(self):
        if not self._pipeline or not self._pipeline.is_running:
            return
        boxes = self._pipeline.overlay._boxes if hasattr(self._pipeline.overlay, "_boxes") else []
        static = self._pipeline.is_static if hasattr(self._pipeline, "is_static") else True
        self.status_label.setText(
            f"● 运行中 | {self._pipeline.fps:.0f} FPS | "
            f"{len(boxes)} 框 | {'静态' if static else '动态'}")
        self._update_tray_menu()

    # ═══════════════ Close → Tray ═══════════════

    def closeEvent(self, event):
        if self._quitting:
            super().closeEvent(event)
        else:
            self.hide()
            self._tray.showMessage("NexaTrans", "程序已最小化到托盘，双击托盘图标可重新打开", QSystemTrayIcon.Information, 2000)
            event.ignore()
