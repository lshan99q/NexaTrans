"""
NexaTrans - Main Window
Main interface module: displays translation region info, provides selection entry and test box control.
Stage 3: Integrated DBNet++ text detection with start/stop and FPS display.
"""

import logging
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QImage

from config.config_manager import ConfigManager
from ui.selector_window import SelectorWindow
from ui.region_overlay import RegionOverlay

logger = logging.getLogger("NexaTrans.MainWindow")


class MainWindow(QWidget):
    """Main window with region selection, test overlay, and text detection."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self._selector = None
        self._overlay = RegionOverlay()
        self._pipeline = None
        self._fps_timer = QTimer()
        self._fps_timer.timeout.connect(self._update_fps_display)
        self._setup_ui()
        self._load_region()
        logger.info("Main window initialized (Stage 3)")

    def _numpy_to_pixmap(self, img: np.ndarray, max_w: int = 340) -> QPixmap:
        """Convert BGR numpy array to QPixmap, scaled to fit max_w."""
        import cv2
        h, w = img.shape[:2]
        if w > max_w:
            scale = max_w / w
            img = cv2.resize(img, (max_w, int(h * scale)))
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        qimg = QImage(rgb.data, w, h, w * c, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def _setup_ui(self):
        """Set up the UI (Chinese)."""
        self.setWindowTitle("NexaTrans v0.3 - 屏幕文本检测")
        self.setFixedSize(400, 720)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Title
        title_label = QLabel("NexaTrans v0.3")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = title_label.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        subtitle = QLabel("屏幕文本检测系统")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #888;")
        layout.addWidget(subtitle)

        # ---- Region info group ----
        group_box = QGroupBox("翻译区域")
        form_layout = QFormLayout()

        self.label_x = QLabel("0")
        self.label_y = QLabel("0")
        self.label_width = QLabel("0")
        self.label_height = QLabel("0")

        form_layout.addRow("X:", self.label_x)
        form_layout.addRow("Y:", self.label_y)
        form_layout.addRow("宽:", self.label_width)
        form_layout.addRow("高:", self.label_height)

        group_box.setLayout(form_layout)
        layout.addWidget(group_box)

        # ---- Region controls ----
        region_ctrl = QHBoxLayout()

        self.test_checkbox = QCheckBox("显示红框")
        self.test_checkbox.toggled.connect(self._on_test_toggle)
        region_ctrl.addWidget(self.test_checkbox)

        self.select_btn = QPushButton("框选区域")
        self.select_btn.setFixedSize(100, 32)
        self.select_btn.clicked.connect(self._on_select_region)
        region_ctrl.addWidget(self.select_btn)

        self.preview_btn = QPushButton("截图预览")
        self.preview_btn.setFixedSize(100, 32)
        self.preview_btn.clicked.connect(self._on_preview_screenshot)
        region_ctrl.addWidget(self.preview_btn)

        layout.addLayout(region_ctrl)

        # ---- Screenshot preview ----
        preview_group = QGroupBox("截图预览")
        preview_layout = QVBoxLayout()
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(120)
        self.preview_label.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #444; border-radius: 4px;"
        )
        self.preview_label.setText("(点击「截图预览」查看)")
        preview_layout.addWidget(self.preview_label)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # ---- Stage 3: Detection group ----
        detection_group = QGroupBox("文本检测 (Stage 3)")
        det_layout = QVBoxLayout()

        self.model_status_label = QLabel("模型: 未加载")
        det_layout.addWidget(self.model_status_label)

        self.fps_label = QLabel("帧率: --")
        det_layout.addWidget(self.fps_label)

        self.box_count_label = QLabel("检测框: 0")
        det_layout.addWidget(self.box_count_label)

        det_btn_layout = QHBoxLayout()
        det_btn_layout.addStretch()

        self.detect_btn = QPushButton("开始检测")
        self.detect_btn.setFixedSize(140, 36)
        self.detect_btn.clicked.connect(self._on_toggle_detection)
        det_btn_layout.addWidget(self.detect_btn)

        det_btn_layout.addStretch()
        det_layout.addLayout(det_btn_layout)
        detection_group.setLayout(det_layout)
        layout.addWidget(detection_group)

        layout.addStretch()
        self.setLayout(layout)

    def _load_region(self):
        """Load and display saved region info."""
        region = self.config_manager.load_region()
        self._update_region_display(region)
        self._overlay.update_region(region)

    def _update_region_display(self, region: dict):
        """Update region info labels."""
        self.label_x.setText(str(region.get("x", 0)))
        self.label_y.setText(str(region.get("y", 0)))
        self.label_width.setText(str(region.get("width", 0)))
        self.label_height.setText(str(region.get("height", 0)))

    def _on_preview_screenshot(self):
        """Capture and display the region screenshot in the preview panel."""
        from screen.screenshot import capture_region
        logger.info("User clicked screenshot preview")
        try:
            region = self.config_manager.load_region()
            w = region.get("width", 0)
            h = region.get("height", 0)
            if w <= 0 or h <= 0:
                self.preview_label.setText("(请先框选区域)")
                return

            img = capture_region(region)
            if img.size == 0:
                self.preview_label.setText("(截图失败)")
                return

            pixmap = self._numpy_to_pixmap(img)
            self.preview_label.setPixmap(pixmap)
            logger.info(f"Screenshot preview: {img.shape[1]}x{img.shape[0]}")
        except Exception as e:
            logger.error(f"Screenshot preview failed: {e}")
            self.preview_label.setText(f"(截图失败: {e})")

    def _update_fps_display(self):
        """Periodic FPS and box count update."""
        if self._pipeline and self._pipeline.is_running:
            fps = self._pipeline.fps
            self.fps_label.setText(f"帧率: {fps:.1f}")
            boxes = self._pipeline.overlay._boxes if hasattr(self._pipeline.overlay, "_boxes") else []
            self.box_count_label.setText(f"检测框: {len(boxes)}")

    def _on_test_toggle(self, checked: bool):
        """Toggle region test overlay."""
        if checked:
            region = self.config_manager.load_region()
            self._overlay.update_region(region)
        self._overlay.set_test_visible(checked)

    def _on_select_region(self):
        """Handle region selection button."""
        logger.info("User clicked region selection")
        if self._overlay.isVisible():
            self._overlay.hide()
        self.hide()

        overlay_config = self.config_manager.get_overlay_config()
        self._selector = SelectorWindow(overlay_config)
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.cancelled.connect(self._on_selection_cancelled)

    def _on_region_selected(self, region: dict):
        """Region selection completed."""
        logger.info(f"Region selected: {region}")
        self._selector = None
        self.config_manager.save_region(region)
        self._update_region_display(region)
        self._overlay.update_region(region)
        if self.test_checkbox.isChecked():
            self._overlay.set_test_visible(True)
        self.show()

    def _on_selection_cancelled(self):
        """Region selection cancelled."""
        logger.info("Region selection cancelled")
        self._selector = None
        if self.test_checkbox.isChecked():
            self._overlay.set_test_visible(True)
        self.show()

    def _on_toggle_detection(self):
        """Start or stop the DBNet++ detection pipeline."""
        if self._pipeline is None:
            self._init_pipeline()

        if self._pipeline is None:
            return

        if self._pipeline.is_running:
            self._stop_detection()
        else:
            self._start_detection()

    def _init_pipeline(self):
        """Lazy-initialize the detection pipeline."""
        from detection.detection_pipeline import DetectionPipeline

        self.model_status_label.setText("模型: 加载中...")
        self.detect_btn.setEnabled(False)

        try:
            self._pipeline = DetectionPipeline(self.config_manager, target_fps=15)
            if self._pipeline.detector.is_loaded:
                self.model_status_label.setText("模型: DBNet++ (ONNX)")
            else:
                self.model_status_label.setText("模型: 加载失败")
                self._pipeline = None
        except Exception as e:
            logger.error(f"Pipeline init failed: {e}")
            self.model_status_label.setText("模型: 错误 - 查看日志")
            self._pipeline = None

        self.detect_btn.setEnabled(True)

    def _start_detection(self):
        """Start detection."""
        if self._pipeline is None:
            return

        success = self._pipeline.start()
        if success:
            self.detect_btn.setText("停止检测")
            self._fps_timer.start(500)
            logger.info("Detection started")
        else:
            logger.error("Failed to start detection")

    def _stop_detection(self):
        """Stop detection."""
        if self._pipeline:
            self._pipeline.stop()
        self.detect_btn.setText("开始检测")
        self._fps_timer.stop()
        self.fps_label.setText("帧率: --")
        self.box_count_label.setText("检测框: 0")
        logger.info("Detection stopped")

    def closeEvent(self, event):
        """Clean up on close."""
        if self._pipeline:
            self._pipeline.cleanup()
        self._fps_timer.stop()
        self._overlay.close()
        super().closeEvent(event)
