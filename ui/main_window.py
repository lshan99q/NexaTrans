"""
NexaTrans - Main Window
Stage 3: DBNet++ text detection with start/stop and FPS display.
Stage 4: Mask overlay toggle + filter parameter sliders.
"""

import logging
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QCheckBox, QSlider
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage

from config.config_manager import ConfigManager
from ui.selector_window import SelectorWindow
from ui.region_overlay import RegionOverlay

logger = logging.getLogger("NexaTrans.MainWindow")


class MainWindow(QWidget):
    """Main window with region selection, test overlay, detection, and filter controls."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self._selector = None
        self._overlay = RegionOverlay()
        self._pipeline = None
        self._fps_timer = QTimer()
        self._fps_timer.timeout.connect(self._update_fps_display)
        self._setup_ui()
        self._load_config()
        self._load_region()
        logger.info("Main window initialized (Stage 3 + 4)")

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
        """Load filter params from config."""
        tp = self.config_manager.get_text_processing_config()
        self._slider_min_conf.setValue(int(tp["min_confidence"] * 100))
        self._slider_min_aspect.setValue(int(tp["min_text_aspect"] * 10))
        self._slider_max_icon.setValue(int(tp["max_icon_aspect"] * 10))
        self._slider_min_area.setValue(int(tp["min_area_ratio"] * 1000))

    def _setup_ui(self):
        self.setWindowTitle("NexaTrans v0.4 - 屏幕文本检测")
        self.setFixedSize(420, 860)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Title
        title = QLabel("NexaTrans v0.4")
        title.setAlignment(Qt.AlignCenter)
        f = title.font(); f.setPointSize(16); f.setBold(True); title.setFont(f)
        layout.addWidget(title)

        sub = QLabel("屏幕文本检测系统"); sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #888;"); layout.addWidget(sub)

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
        self.preview_label.setStyleSheet("background:#1a1a1a; border:1px solid #444; border-radius:4px;")
        self.preview_label.setText("(点击「截图预览」查看)")
        pl.addWidget(self.preview_label); pg.setLayout(pl); layout.addWidget(pg)

        # ---- Filter params ----
        fg = QGroupBox("过滤参数 (Stage 4)")
        ffl = QFormLayout()

        self._slider_min_conf = self._make_slider(10, 90, 50)
        self._label_min_conf = QLabel("0.50")
        ffl.addRow("最低置信度:", self._make_slider_row(self._slider_min_conf, self._label_min_conf, "0.10", "0.90"))

        self._slider_min_aspect = self._make_slider(12, 30, 18)
        self._label_min_aspect = QLabel("1.8")
        ffl.addRow("文字长宽比:", self._make_slider_row(self._slider_min_aspect, self._label_min_aspect, "1.2", "3.0"))

        self._slider_max_icon = self._make_slider(11, 20, 14)
        self._label_max_icon = QLabel("1.4")
        ffl.addRow("图标长宽比:", self._make_slider_row(self._slider_max_icon, self._label_max_icon, "1.1", "2.0"))

        self._slider_min_area = self._make_slider(1, 20, 5)
        self._label_min_area = QLabel("0.005")
        ffl.addRow("最小面积比:", self._make_slider_row(self._slider_min_area, self._label_min_area, "0.001", "0.020"))

        fg.setLayout(ffl); layout.addWidget(fg)

        # Connect sliders
        self._slider_min_conf.valueChanged.connect(lambda v: self._on_filter_changed("min_confidence", v / 100.0, self._label_min_conf, 2))
        self._slider_min_aspect.valueChanged.connect(lambda v: self._on_filter_changed("min_text_aspect", v / 10.0, self._label_min_aspect, 1))
        self._slider_max_icon.valueChanged.connect(lambda v: self._on_filter_changed("max_icon_aspect", v / 10.0, self._label_max_icon, 1))
        self._slider_min_area.valueChanged.connect(lambda v: self._on_filter_changed("min_area_ratio", v / 1000.0, self._label_min_area, 3))

        # ---- Detection ----
        dg = QGroupBox("文本检测 (Stage 3 + 4)")
        dl = QVBoxLayout()
        self.model_status_label = QLabel("模型: 未加载"); dl.addWidget(self.model_status_label)
        self.fps_label = QLabel("帧率: --"); dl.addWidget(self.fps_label)
        self.box_count_label = QLabel("检测框: 0"); dl.addWidget(self.box_count_label)
        self.static_label = QLabel("静态: --"); dl.addWidget(self.static_label)
        self.mask_checkbox = QCheckBox("显示 Mask (Stage 4)")
        self.mask_checkbox.setEnabled(False)
        self.mask_checkbox.toggled.connect(self._on_mask_toggle)
        dl.addWidget(self.mask_checkbox)

        dbl = QHBoxLayout(); dbl.addStretch()
        self.detect_btn = QPushButton("开始检测")
        self.detect_btn.setFixedSize(140, 36)
        self.detect_btn.clicked.connect(self._on_toggle_detection)
        dbl.addWidget(self.detect_btn); dbl.addStretch()
        dl.addLayout(dbl); dg.setLayout(dl); layout.addWidget(dg)

        layout.addStretch()
        self.setLayout(layout)

    def _make_slider(self, lo, hi, val):
        s = QSlider(Qt.Horizontal); s.setRange(lo, hi); s.setValue(val); return s

    def _make_slider_row(self, slider, label, lo_text, hi_text):
        row = QHBoxLayout()
        lo = QLabel(lo_text); lo.setStyleSheet("color:#888; font-size:9px;")
        hi = QLabel(hi_text); hi.setStyleSheet("color:#888; font-size:9px;")
        row.addWidget(lo); row.addWidget(slider); row.addWidget(label)
        row.addWidget(hi); label.setFixedWidth(45); label.setAlignment(Qt.AlignCenter)
        return row

    def _on_filter_changed(self, key, value, label, decimals):
        """Slider changed: update label, pipeline, and save config."""
        label.setText(f"{value:.{decimals}f}")
        self._save_filter_config(key, value)

    def _save_filter_config(self, key, value):
        """Persist a single filter param to settings.json."""
        try:
            import json, os
            path = self.config_manager.config_path
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg.setdefault("text_processing", {})[key] = value
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save filter config: {e}")

    def _load_region(self):
        region = self.config_manager.load_region()
        self._update_region_display(region)
        self._overlay.update_region(region)

    def _update_region_display(self, region):
        self.label_x.setText(str(region.get("x", 0)))
        self.label_y.setText(str(region.get("y", 0)))
        self.label_width.setText(str(region.get("width", 0)))
        self.label_height.setText(str(region.get("height", 0)))

    def _on_preview_screenshot(self):
        from screen.screenshot import capture_region
        try:
            region = self.config_manager.load_region()
            if region.get("width", 0) <= 0:
                self.preview_label.setText("(请先框选区域)"); return
            img = capture_region(region)
            if img.size == 0:
                self.preview_label.setText("(截图失败)"); return
            self.preview_label.setPixmap(self._numpy_to_pixmap(img))
        except Exception as e:
            self.preview_label.setText(f"(截图失败: {e})")

    def _update_fps_display(self):
        if self._pipeline and self._pipeline.is_running:
            self.fps_label.setText(f"帧率: {self._pipeline.fps:.1f}")
            boxes = self._pipeline.overlay._boxes if hasattr(self._pipeline.overlay, "_boxes") else []
            self.box_count_label.setText(f"检测框: {len(boxes)}")
            static = self._pipeline.is_static if hasattr(self._pipeline, 'is_static') else True
            self.static_label.setText(f"静态: {'是' if static else '否'}")

    def _on_test_toggle(self, checked):
        if checked:
            self._overlay.update_region(self.config_manager.load_region())
        self._overlay.set_test_visible(checked)

    def _on_mask_toggle(self, checked):
        if self._pipeline:
            self._pipeline.show_mask = checked

    def _on_select_region(self):
        if self._overlay.isVisible(): self._overlay.hide()
        self.hide()
        self._selector = SelectorWindow(self.config_manager.get_overlay_config())
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.cancelled.connect(self._on_selection_cancelled)

    def _on_region_selected(self, region):
        self._selector = None
        self.config_manager.save_region(region)
        self._update_region_display(region)
        self._overlay.update_region(region)
        if self.test_checkbox.isChecked(): self._overlay.set_test_visible(True)
        self.show()

    def _on_selection_cancelled(self):
        self._selector = None
        if self.test_checkbox.isChecked(): self._overlay.set_test_visible(True)
        self.show()

    def _on_toggle_detection(self):
        if self._pipeline is None: self._init_pipeline()
        if self._pipeline is None: return
        if self._pipeline.is_running: self._stop_detection()
        else: self._start_detection()

    def _init_pipeline(self):
        from detection.detection_pipeline import DetectionPipeline
        self.model_status_label.setText("模型: 加载中..."); self.detect_btn.setEnabled(False)
        try:
            self._pipeline = DetectionPipeline(self.config_manager, target_fps=15)
            if self._pipeline.detector.is_loaded:
                self.model_status_label.setText("模型: DBNet++ (ONNX)")
                self.mask_checkbox.setEnabled(True)
            else:
                self.model_status_label.setText("模型: 加载失败"); self._pipeline = None
        except Exception as e:
            logger.error(f"Pipeline init failed: {e}")
            self.model_status_label.setText("模型: 错误"); self._pipeline = None
        self.detect_btn.setEnabled(True)

    def _start_detection(self):
        if self._pipeline is None: return
        if self._pipeline.start():
            self.detect_btn.setText("停止检测"); self._fps_timer.start(500)
        else:
            logger.error("Failed to start detection")

    def _stop_detection(self):
        if self._pipeline: self._pipeline.stop()
        self.detect_btn.setText("开始检测"); self._fps_timer.stop()
        self.fps_label.setText("帧率: --"); self.box_count_label.setText("检测框: 0")
        self.static_label.setText("静态: --")

    def closeEvent(self, event):
        if self._pipeline: self._pipeline.cleanup()
        self._fps_timer.stop(); self._overlay.close()
        super().closeEvent(event)
