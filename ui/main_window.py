# -*- coding: utf-8 -*-
"""
NexaTrans - Main Window (Stage 5)
Stage 3: DBNet++ text detection with start/stop and FPS display.
Stage 4: Mask overlay toggle + filter parameter sliders.
Stage 5: OCR recognition with PP-OCRv5, results display.
"""

import logging
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QCheckBox, QSlider,
    QTextEdit, QScrollArea,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage, QFont

from config.config_manager import ConfigManager
from ui.selector_window import SelectorWindow
from ui.region_overlay import RegionOverlay

logger = logging.getLogger("NexaTrans.MainWindow")


class MainWindow(QWidget):
    """Main window with region selection, detection, mask, OCR, and filter controls."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self._selector = None
        self._overlay = RegionOverlay()
        self._pipeline = None
        self._fps_timer = QTimer()
        self._fps_timer.timeout.connect(self._update_fps_display)
        self._ocr_update_timer = QTimer()
        self._ocr_update_timer.timeout.connect(self._update_ocr_display)
        self._setup_ui()
        self._load_config()
        self._load_region()
        logger.info("Main window initialized (Stage 5)")

    def _numpy_to_pixmap(self, img: np.ndarray, max_w: int = 320) -> QPixmap:
        import cv2
        h, w = img.shape[:2]
        if w > max_w:
            scale = max_w / w
            img = cv2.resize(img, (max_w, int(h * scale)))
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        return QPixmap.fromImage(QImage(rgb.data, w, h, w * c, QImage.Format_RGB888))

    def _load_config(self):
        tp = self.config_manager.get_text_processing_config()
        self._slider_min_conf.setValue(int(tp["min_confidence"] * 100))
        self._slider_min_aspect.setValue(int(tp["min_text_aspect"] * 10))
        self._slider_max_icon.setValue(int(tp["max_icon_aspect"] * 10))
        self._slider_min_area.setValue(int(tp["min_area_ratio"] * 1000))

    def _setup_ui(self):
        self.setWindowTitle("NexaTrans v0.5 - Stage 5 OCR")
        self.setFixedSize(420, 900)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(5)

        # Title
        title = QLabel("NexaTrans v0.5")
        title.setAlignment(Qt.AlignCenter)
        f = title.font(); f.setPointSize(16); f.setBold(True); title.setFont(f)
        layout.addWidget(title)

        sub = QLabel("屏幕文本检测 + OCR识别")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #888;")
        layout.addWidget(sub)

        # ---- Region info ----
        gb = QGroupBox("翻译区域")
        fl = QFormLayout()
        self.label_x = QLabel("0"); self.label_y = QLabel("0")
        self.label_width = QLabel("0"); self.label_height = QLabel("0")
        fl.addRow("X:", self.label_x); fl.addRow("Y:", self.label_y)
        fl.addRow("宽:", self.label_width); fl.addRow("高:", self.label_height)
        gb.setLayout(fl); layout.addWidget(gb)

        # ---- Region controls ----
        rc = QHBoxLayout()
        self.test_checkbox = QCheckBox("显示红框")
        self.test_checkbox.toggled.connect(self._on_test_toggle)
        rc.addWidget(self.test_checkbox)
        self.select_btn = QPushButton("框选区域")
        self.select_btn.setFixedSize(90, 30)
        self.select_btn.clicked.connect(self._on_select_region)
        rc.addWidget(self.select_btn)
        self.preview_btn = QPushButton("截图预览")
        self.preview_btn.setFixedSize(90, 30)
        self.preview_btn.clicked.connect(self._on_preview_screenshot)
        rc.addWidget(self.preview_btn)
        layout.addLayout(rc)

        # ---- Preview ----
        pg = QGroupBox("截图预览")
        pl = QVBoxLayout()
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(100)
        self.preview_label.setStyleSheet(
            "background:#1a1a1a; border:1px solid #444; border-radius:4px;"
        )
        self.preview_label.setText("(点击「截图预览」查看)")
        pl.addWidget(self.preview_label); pg.setLayout(pl); layout.addWidget(pg)

        # ---- Detection Controls ----
        dg = QGroupBox("检测控制")
        dl = QVBoxLayout()

        dc1 = QHBoxLayout()
        self.detect_btn = QPushButton("开始检测")
        self.detect_btn.setFixedSize(90, 30)
        self.detect_btn.clicked.connect(self._on_toggle_detection)
        dc1.addWidget(self.detect_btn)
        self.model_status_label = QLabel("模型: 未加载")
        dc1.addWidget(self.model_status_label)
        dc1.addStretch()
        dl.addLayout(dc1)

        dc2 = QHBoxLayout()
        self.mask_checkbox = QCheckBox("显示Mask")
        self.mask_checkbox.setEnabled(False)
        self.mask_checkbox.toggled.connect(self._on_mask_toggle)
        dc2.addWidget(self.mask_checkbox)
        self.boxes_checkbox = QCheckBox("显示绿框")
        self.boxes_checkbox.setChecked(True)
        self.boxes_checkbox.toggled.connect(self._on_boxes_toggle)
        dc2.addWidget(self.boxes_checkbox)
        dl.addLayout(dc2)

        dc3 = QHBoxLayout()
        self.ocr_checkbox = QCheckBox("启用OCR (Stage 5)")
        self.ocr_checkbox.setEnabled(False)
        self.ocr_checkbox.toggled.connect(self._on_ocr_toggle)
        dc3.addWidget(self.ocr_checkbox)
        self.ocr_status_label = QLabel("OCR: 未启动")
        dc3.addWidget(self.ocr_status_label)
        dc3.addStretch()
        dl.addLayout(dc3)

        dg.setLayout(dl); layout.addWidget(dg)

        # ---- Stats ----
        sg = QGroupBox("运行状态")
        sfl = QFormLayout()
        self.fps_label = QLabel("帧率: --")
        self.box_count_label = QLabel("检测框: 0")
        self.static_label = QLabel("静态: --")
        sfl.addRow(self.fps_label, self.box_count_label)
        sfl.addRow(self.static_label)
        sg.setLayout(sfl); layout.addWidget(sg)

        # ---- OCR Results ----
        og = QGroupBox("OCR识别结果 (Stage 5)")
        ol = QVBoxLayout()
        self.ocr_text = QTextEdit()
        self.ocr_text.setReadOnly(True)
        self.ocr_text.setMinimumHeight(80)
        self.ocr_text.setMaximumHeight(120)
        self.ocr_text.setStyleSheet(
            "background:#1a1a1a; color:#0f0; border:1px solid #444; border-radius:4px;"
        )
        mono = QFont("Consolas", 10)
        self.ocr_text.setFont(mono)
        self.ocr_text.setPlaceholderText("(等待OCR结果...)")
        ol.addWidget(self.ocr_text)
        og.setLayout(ol); layout.addWidget(og)

        # ---- Filter params ----
        fg = QGroupBox("过滤参数 (Stage 4)")
        ffl = QFormLayout()

        self._slider_min_conf = self._make_slider(10, 90, 50)
        self._label_min_conf = QLabel("0.50")
        ffl.addRow(
            "最低置信度:",
            self._make_slider_row(self._slider_min_conf, self._label_min_conf, "0.10", "0.90"),
        )

        self._slider_min_aspect = self._make_slider(12, 30, 18)
        self._label_min_aspect = QLabel("1.8")
        ffl.addRow(
            "文字长宽比:",
            self._make_slider_row(self._slider_min_aspect, self._label_min_aspect, "1.2", "3.0"),
        )

        self._slider_max_icon = self._make_slider(10, 18, 14)
        self._label_max_icon = QLabel("1.4")
        ffl.addRow(
            "图标宽高比:",
            self._make_slider_row(self._slider_max_icon, self._label_max_icon, "1.0", "1.8"),
        )

        self._slider_min_area = self._make_slider(1, 20, 5)
        self._label_min_area = QLabel("0.005")
        ffl.addRow(
            "最小面积比:",
            self._make_slider_row(self._slider_min_area, self._label_min_area, "0.001", "0.020"),
        )

        fg.setLayout(ffl); layout.addWidget(fg)

        # ---- Slider helpers ----
        self._slider_min_conf.valueChanged.connect(
            lambda v: self._on_filter_change("min_confidence", v, self._label_min_conf, 100.0, "{:.2f}")
        )
        self._slider_min_aspect.valueChanged.connect(
            lambda v: self._on_filter_change("min_text_aspect", v, self._label_min_aspect, 10.0, "{:.1f}")
        )
        self._slider_max_icon.valueChanged.connect(
            lambda v: self._on_filter_change("max_icon_aspect", v, self._label_max_icon, 10.0, "{:.1f}")
        )
        self._slider_min_area.valueChanged.connect(
            lambda v: self._on_filter_change("min_area_ratio", v, self._label_min_area, 1000.0, "{:.3f}")
        )

        self.setLayout(layout)

    def _make_slider(self, min_val, max_val, default):
        s = QSlider(Qt.Horizontal)
        s.setRange(min_val, max_val)
        s.setValue(default)
        return s

    def _make_slider_row(self, slider, label, left_text, right_text):
        row = QHBoxLayout()
        row.addWidget(QLabel(left_text))
        row.addWidget(slider)
        row.addWidget(QLabel(right_text))
        row.addWidget(label)
        return row

    def _on_filter_change(self, key, raw_value, label, divisor, fmt):
        val = raw_value / divisor
        label.setText(fmt.format(val))
        tp = self.config_manager.get_text_processing_config()
        tp[key] = val
        self.config_manager.save_text_processing(tp)

    def _load_region(self):
        region = self.config_manager.load_region()
        self._update_region_display(region)

    def _update_region_display(self, region):
        self.label_x.setText(str(region.get("x", 0)))
        self.label_y.setText(str(region.get("y", 0)))
        self.label_width.setText(str(region.get("width", 0)))
        self.label_height.setText(str(region.get("height", 0)))

    def _on_preview_screenshot(self):
        from screen.screenshot import capture_region
        import ctypes
        try:
            region = self.config_manager.load_region()
            if region.get("width", 0) <= 0:
                self.preview_label.setText("(未选择区域)")
                return
            u32 = ctypes.windll.user32
            if hasattr(self, "_overlay") and self._overlay:
                u32.ShowWindow(int(self._overlay.winId()), 0)
            if self._pipeline and self._pipeline.overlay:
                u32.ShowWindow(int(self._pipeline.overlay.winId()), 0)
            try:
                img = capture_region(region)
            finally:
                if hasattr(self, "_overlay") and self._overlay:
                    u32.ShowWindow(int(self._overlay.winId()), 4)
                if self._pipeline and self._pipeline.overlay:
                    u32.ShowWindow(int(self._pipeline.overlay.winId()), 4)
            if img.size == 0:
                self.preview_label.setText("(截图失败)")
                return
            self.preview_label.setPixmap(self._numpy_to_pixmap(img))
        except Exception as e:
            self.preview_label.setText(f"(错误: {e})")

    def _update_fps_display(self):
        if self._pipeline and self._pipeline.is_running:
            self.fps_label.setText(f"帧率: {self._pipeline.fps:.1f}")
            boxes = (
                self._pipeline.overlay._boxes
                if hasattr(self._pipeline.overlay, "_boxes")
                else []
            )
            self.box_count_label.setText(f"检测框: {len(boxes)}")
            static = self._pipeline.is_static if hasattr(self._pipeline, "is_static") else True
            self.static_label.setText(f"静态: {'是' if static else '否'}")

    def _update_ocr_display(self):
        if not self._pipeline or not self._pipeline.ocr_enabled:
            return
        results = self._pipeline.ocr_results
        if not results:
            return
        lines = []
        for r in results:
            text = r.get("text", "")
            conf = r.get("confidence", 0)
            cached = "C" if r.get("cached") else " "
            lines.append(f"[{cached}] [{conf:.2f}] {text}")
        if lines:
            self.ocr_text.setPlainText("\n".join(lines))
            self.ocr_status_label.setText(f"OCR: {len(results)} 条结果")

    def _on_test_toggle(self, checked):
        if checked:
            self._overlay.update_region(self.config_manager.load_region())
        self._overlay.set_test_visible(checked)

    def _on_mask_toggle(self, checked):
        if self._pipeline:
            self._pipeline.show_mask = checked

    def _on_boxes_toggle(self, checked):
        if self._pipeline and self._pipeline.overlay:
            self._pipeline.overlay.show_boxes = checked

    def _on_ocr_toggle(self, checked):
        if self._pipeline:
            self._pipeline.ocr_enabled = checked
            if checked:
                self._ocr_update_timer.start(500)
                self.ocr_status_label.setText("OCR: 运行中...")
            else:
                self._ocr_update_timer.stop()
                self.ocr_text.clear()
                self.ocr_text.setPlaceholderText("(等待OCR结果...)")
                self.ocr_status_label.setText("OCR: 已关闭")

    def _on_select_region(self):
        if self._overlay.isVisible():
            self._overlay.hide()
        self.hide()
        self._selector = SelectorWindow(self.config_manager.get_overlay_config())
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.cancelled.connect(self._on_selection_cancelled)

    def _on_region_selected(self, region):
        self._selector = None
        self.config_manager.save_region(region)
        self._update_region_display(region)
        self._overlay.update_region(region)
        if self.test_checkbox.isChecked():
            self._overlay.set_test_visible(True)
        self.show()

    def _on_selection_cancelled(self):
        self._selector = None
        if self.test_checkbox.isChecked():
            self._overlay.set_test_visible(True)
        self.show()

    def _on_toggle_detection(self):
        if self._pipeline is None:
            self._init_pipeline()
        if self._pipeline is None:
            return
        if self._pipeline.is_running:
            self._stop_detection()
        else:
            self._start_detection()

    def _init_pipeline(self):
        from detection.detection_pipeline import DetectionPipeline
        self.model_status_label.setText("模型: 加载中...")
        self.detect_btn.setEnabled(False)
        try:
            self._pipeline = DetectionPipeline(self.config_manager, target_fps=15)
            if self._pipeline.detector.is_loaded:
                self.model_status_label.setText("模型: DBNet++ (ONNX)")
                self.mask_checkbox.setEnabled(True)
                self.ocr_checkbox.setEnabled(True)
            else:
                self.model_status_label.setText("模型: 加载失败")
                self._pipeline = None
        except Exception as e:
            logger.error(f"Pipeline init failed: {e}")
            self.model_status_label.setText("模型: 错误")
            self._pipeline = None
        self.detect_btn.setEnabled(True)

    def _start_detection(self):
        if self._pipeline is None:
            return
        if self._pipeline.start():
            self.detect_btn.setText("停止检测")
            self._fps_timer.start(500)
        else:
            logger.error("Failed to start detection")

    def _stop_detection(self):
        if self._pipeline:
            self._pipeline.stop()
        self.detect_btn.setText("开始检测")
        self._fps_timer.stop()
        self._ocr_update_timer.stop()
        self.fps_label.setText("帧率: --")
        self.box_count_label.setText("检测框: 0")
        self.static_label.setText("静态: --")
        self.ocr_status_label.setText("OCR: 未启动")

    def closeEvent(self, event):
        if self._pipeline:
            self._pipeline.cleanup()
        self._fps_timer.stop()
        self._ocr_update_timer.stop()
        self._overlay.close()
        super().closeEvent(event)

