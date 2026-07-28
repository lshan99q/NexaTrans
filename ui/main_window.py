# -*- coding: utf-8 -*-
"""
NexaTrans - Main Window v1.0.2
Clean UI: Start/Stop, Select Region, Settings (expandable).
One-click translation. API key config in settings.
"""

import os
import logging
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QCheckBox, QSlider,
    QLineEdit, QFrame,
)
from PySide6.QtCore import Qt, QTimer

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
        self._setup_ui()
        self._load_config()
        self._load_region()
        logger.info("MainWindow v1.0.2 ready")

    def _setup_ui(self):
        self.setWindowTitle("NexaTrans v1.0")
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
            QPushButton#startBtn.running { background: #c22; border-color: #e44; }
            QPushButton#startBtn.running:hover { background: #e44; }
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

        # Title
        title = QLabel("NexaTrans")
        title.setAlignment(Qt.AlignCenter)
        f = title.font(); f.setPointSize(22); f.setBold(True); title.setFont(f)
        title.setStyleSheet("color: #0af; background: transparent;")
        layout.addWidget(title)

        ver = QLabel("v1.0 · Screen AI Translation")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color: #666; font-size: 11px; background: transparent;")
        layout.addWidget(ver)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #333; background: transparent;")
        layout.addWidget(sep)

        # Start button
        self.start_btn = QPushButton("Start Translate")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start)
        layout.addWidget(self.start_btn)

        # Region + Settings row
        btn_row = QHBoxLayout()
        self.region_btn = QPushButton("Select Region")
        self.region_btn.setCursor(Qt.PointingHandCursor)
        self.region_btn.clicked.connect(self._on_select_region)
        btn_row.addWidget(self.region_btn)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(self._on_toggle_settings)
        btn_row.addWidget(self.settings_btn)
        layout.addLayout(btn_row)

        # Region info
        self.region_info = QLabel("Region: none")
        self.region_info.setAlignment(Qt.AlignCenter)
        self.region_info.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        layout.addWidget(self.region_info)

        # Status
        self.status_label = QLabel("- Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        layout.addWidget(self.status_label)

        # ═══════════════ Settings ═══════════════
        self._settings_area = QWidget()
        self._settings_area.setVisible(False)
        sl = QVBoxLayout()
        sl.setContentsMargins(0, 4, 0, 0)
        sl.setSpacing(6)

        # API Key
        ag = QGroupBox("DeepSeek API")
        al = QVBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxx")
        self.api_key_input.setText(_read_env_key())
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.textChanged.connect(self._on_api_key_change)
        al.addWidget(QLabel("API Key:"))
        al.addWidget(self.api_key_input)
        ag.setLayout(al)
        sl.addWidget(ag)

        # Toggles
        tg = QGroupBox("Overlay")
        tfl = QVBoxLayout()
        self.mask_check = QCheckBox("Show Mask")
        self.mask_check.toggled.connect(self._on_mask_toggle)
        tfl.addWidget(self.mask_check)
        self.boxes_check = QCheckBox("Show Green Boxes")
        self.boxes_check.setChecked(True)
        self.boxes_check.toggled.connect(self._on_boxes_toggle)
        tfl.addWidget(self.boxes_check)
        self.ocr_check = QCheckBox("Enable OCR")
        self.ocr_check.setChecked(True)
        self.ocr_check.toggled.connect(self._on_ocr_toggle)
        tfl.addWidget(self.ocr_check)
        self.trans_check = QCheckBox("Enable Translation")
        self.trans_check.setChecked(True)
        self.trans_check.toggled.connect(self._on_trans_toggle)
        tfl.addWidget(self.trans_check)
        tg.setLayout(tfl)
        sl.addWidget(tg)

        # Filters
        fg = QGroupBox("Filters")
        ffl = QFormLayout()

        self._s_min_conf = self._make_s(10, 90, 50)
        self._l_min_conf = QLabel("0.50")
        ffl.addRow("Min Confidence:", self._make_sr(self._s_min_conf, self._l_min_conf))

        self._s_min_asp = self._make_s(12, 30, 18)
        self._l_min_asp = QLabel("1.8")
        ffl.addRow("Min Text Aspect:", self._make_sr(self._s_min_asp, self._l_min_asp))

        self._s_max_icon = self._make_s(10, 18, 14)
        self._l_max_icon = QLabel("1.4")
        ffl.addRow("Max Icon Aspect:", self._make_sr(self._s_max_icon, self._l_max_icon))

        self._s_min_area = self._make_s(1, 20, 5)
        self._l_min_area = QLabel("0.005")
        ffl.addRow("Min Area Ratio:", self._make_sr(self._s_min_area, self._l_min_area))

        fg.setLayout(ffl)
        sl.addWidget(fg)

        self._settings_area.setLayout(sl)
        layout.addWidget(self._settings_area)

        # Slider signals
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
        r.addWidget(QLabel("Low")); r.addWidget(s); r.addWidget(QLabel("High")); r.addWidget(l)
        w.setLayout(r); return w

    def _load_config(self):
        tp = self.config_manager.get_text_processing_config()
        self._s_min_conf.setValue(int(tp["min_confidence"] * 100))
        self._s_min_asp.setValue(int(tp["min_text_aspect"] * 10))
        self._s_max_icon.setValue(int(tp["max_icon_aspect"] * 10))
        self._s_min_area.setValue(int(tp["min_area_ratio"] * 1000))

    def _load_region(self):
        r = self.config_manager.load_region()
        if r.get("width", 0) > 0:
            self.region_info.setText(f"Region: ({r['x']},{r['y']}) {r['width']}x{r['height']}")

    def _on_f(self, key, raw, label, div, fmt):
        val = raw / div; label.setText(fmt.format(val))
        tp = self.config_manager.get_text_processing_config()
        tp[key] = val
        self.config_manager.save_text_processing(tp)

    def _on_api_key_change(self, text):
        _write_env_key(text.strip())

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

            self.start_btn.setText("Stop Translate")
            self.start_btn.setStyleSheet("""
                QPushButton#startBtn {
                    background: #c22; color: #fff; border-color: #e44;
                    font-size: 16px; padding: 14px 0; border-radius: 6px;
                }
                QPushButton#startBtn:hover { background: #e44; }
            """)
            self.status_label.setText("- Running")
            self.status_label.setStyleSheet("color: #0c8; font-size: 12px; background: transparent;")
            self._fps_timer.start(500)
            self.region_btn.setEnabled(False)
        else:
            self.status_label.setText("- Start Failed")
            self.status_label.setStyleSheet("color: #e44; font-size: 12px; background: transparent;")

    def _stop_all(self):
        if self._pipeline:
            self._pipeline.stop()
        self.start_btn.setText("Start Translate")
        self.start_btn.setStyleSheet("""
            QPushButton#startBtn {
                background: #0a6; color: #fff; border-color: #0c8;
                font-size: 16px; padding: 14px 0; border-radius: 6px;
            }
            QPushButton#startBtn:hover { background: #0c8; }
        """)
        self.status_label.setText("- Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
        self._fps_timer.stop()
        self.region_btn.setEnabled(True)

    def _on_select_region(self):
        if self._overlay.isVisible(): self._overlay.hide()
        self.hide()
        self._selector = SelectorWindow(self.config_manager.get_overlay_config())
        self._selector.region_selected.connect(self._on_region_done)
        self._selector.cancelled.connect(self._on_region_cancel)

    def _on_region_done(self, region):
        self._selector = None
        self.config_manager.save_region(region)
        self.region_info.setText(f"Region: ({region['x']},{region['y']}) {region['width']}x{region['height']}")
        self._overlay.update_region(region)
        self.show()

    def _on_region_cancel(self):
        self._selector = None
        self.show()

    def _on_toggle_settings(self):
        self._settings_visible = not self._settings_visible
        self._settings_area.setVisible(self._settings_visible)
        if self._settings_visible:
            self.settings_btn.setText("Hide Settings")
            self.setFixedSize(380, 580)
        else:
            self.settings_btn.setText("Settings")
            self.setFixedSize(380, 260)

    def _on_mask_toggle(self, checked):
        if self._pipeline:
            self._pipeline.show_mask = checked

    def _on_boxes_toggle(self, checked):
        if self._pipeline and self._pipeline.overlay:
            self._pipeline.overlay.show_boxes = checked

    def _on_ocr_toggle(self, checked):
        if self._pipeline:
            self._pipeline.ocr_enabled = checked

    def _on_trans_toggle(self, checked):
        if self._pipeline:
            self._pipeline.trans_enabled = checked

    def _init_pipeline(self):
        from detection.detection_pipeline import DetectionPipeline
        self.status_label.setText("- Loading model...")
        self.status_label.setStyleSheet("color: #fa0; font-size: 12px; background: transparent;")
        self.start_btn.setEnabled(False)
        try:
            self._pipeline = DetectionPipeline(self.config_manager, target_fps=15)
            if self._pipeline.detector.is_loaded:
                self.status_label.setText("- Ready")
                self.status_label.setStyleSheet("color: #888; font-size: 12px; background: transparent;")
            else:
                self.status_label.setText("- Model load failed")
                self._pipeline = None
        except Exception as e:
            logger.error(f"Pipeline init failed: {e}")
            self.status_label.setText("- Error")
            self._pipeline = None
        self.start_btn.setEnabled(True)

    def _update_status(self):
        if not self._pipeline or not self._pipeline.is_running:
            return
        boxes = self._pipeline.overlay._boxes if hasattr(self._pipeline.overlay, "_boxes") else []
        static = self._pipeline.is_static if hasattr(self._pipeline, "is_static") else True
        self.status_label.setText(
            f"- Running | {self._pipeline.fps:.0f} FPS | "
            f"{len(boxes)} boxes | {'Static' if static else 'Dynamic'}")

    def closeEvent(self, event):
        if self._pipeline:
            self._pipeline.cleanup()
        self._fps_timer.stop()
        self._overlay.close()
        super().closeEvent(event)
