"""
NexaTrans - Main Window
主界面模块：显示翻译区域信息，提供框选入口和 OCR 测试功能
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QCheckBox,
    QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal

from config.config_manager import ConfigManager
from ui.selector_window import SelectorWindow
from ui.region_overlay import RegionOverlay
from capture.screen_capture import capture_region
from ocr.ocr_engine import OCREngine

logger = logging.getLogger("NexaTrans.MainWindow")


class OCRWorker(QThread):
    """OCR 工作线程：在后台执行截图和识别，避免卡死 UI"""

    finished = Signal(list)   # 识别完成
    error = Signal(str)       # 出错
    progress = Signal(str)    # 进度提示

    def __init__(self, region: dict, engine: OCREngine):
        super().__init__()
        self._region = region
        self._engine = engine  # 共享引擎，避免重复加载模型

    def run(self):
        try:
            # 1. 截图
            self.progress.emit("正在截图...")
            image = capture_region(self._region)
            if image is None:
                self.error.emit("截图失败，请检查区域设置")
                return

            # 2. 识别
            self.progress.emit("正在识别文字...")
            results = self._engine.recognize(image)
            self.finished.emit(results)

        except Exception as e:
            logger.error(f"OCR 工作线程异常: {e}", exc_info=True)
            self.error.emit(f"OCR 识别出错: {str(e)}")


class MainWindow(QWidget):
    """主窗口"""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self._selector = None
        self._overlay = RegionOverlay()
        self._ocr_engine = OCREngine()  # 共享 OCR 引擎（懒加载）
        self._ocr_worker = None
        self._setup_ui()
        self._load_region()
        logger.info("主窗口初始化完成")

    def _setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("NexaTrans")
        self.setFixedSize(420, 520)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        # === 标题 ===
        title_label = QLabel("NexaTrans")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = title_label.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # === 区域信息 ===
        group_region = QGroupBox("当前翻译区域")
        form_layout = QFormLayout()

        self.label_x = QLabel("0")
        self.label_y = QLabel("0")
        self.label_w = QLabel("0")
        self.label_h = QLabel("0")

        form_layout.addRow("X:", self.label_x)
        form_layout.addRow("Y:", self.label_y)
        form_layout.addRow("Width:", self.label_w)
        form_layout.addRow("Height:", self.label_h)

        group_region.setLayout(form_layout)
        layout.addWidget(group_region)

        # === 测试框开关 ===
        self.test_checkbox = QCheckBox("显示测试框（屏幕上显示所选区域红色边框）")
        self.test_checkbox.toggled.connect(self._on_test_toggle)
        layout.addWidget(self.test_checkbox)

        # === OCR 结果 ===
        group_ocr = QGroupBox("OCR 结果")
        ocr_layout = QVBoxLayout()

        self.ocr_text = QTextEdit()
        self.ocr_text.setReadOnly(True)
        self.ocr_text.setPlaceholderText("点击「测试OCR」查看识别结果...")
        self.ocr_text.setMaximumHeight(120)
        self.ocr_text.setMinimumHeight(80)
        ocr_layout.addWidget(self.ocr_text)

        group_ocr.setLayout(ocr_layout)
        layout.addWidget(group_ocr)

        # === 按钮行 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.test_ocr_btn = QPushButton("测试OCR")
        self.test_ocr_btn.setFixedSize(120, 36)
        self.test_ocr_btn.clicked.connect(self._on_test_ocr)
        btn_layout.addWidget(self.test_ocr_btn)

        self.select_btn = QPushButton("框选区域")
        self.select_btn.setFixedSize(120, 36)
        self.select_btn.clicked.connect(self._on_select_region)
        btn_layout.addWidget(self.select_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        self.setLayout(layout)

    def _load_region(self):
        """加载并显示已保存的区域信息"""
        region = self.config_manager.load_region()
        self._update_region_display(region)
        self._overlay.update_region(region)

    def _update_region_display(self, region: dict):
        """更新界面上的区域信息显示"""
        self.label_x.setText(str(region.get("x", 0)))
        self.label_y.setText(str(region.get("y", 0)))
        self.label_w.setText(str(region.get("width", 0)))
        self.label_h.setText(str(region.get("height", 0)))

    def _on_test_toggle(self, checked: bool):
        """测试框开关切换"""
        if checked:
            region = self.config_manager.load_region()
            self._overlay.update_region(region)
        self._overlay.set_test_visible(checked)

    def _on_test_ocr(self):
        """测试OCR按钮：启动后台线程执行截图和识别"""
        logger.info("用户点击「测试OCR」按钮")

        # 检查区域
        region = self.config_manager.load_region()
        if region.get("width", 0) <= 0 or region.get("height", 0) <= 0:
            self.ocr_text.setText("请先选择翻译区域")
            return

        # 防止重复点击
        if self._ocr_worker and self._ocr_worker.isRunning():
            return

        # 禁用按钮
        self.test_ocr_btn.setEnabled(False)
        self.test_ocr_btn.setText("处理中...")
        self.ocr_text.setText("准备中...")

        # 启动后台线程（传入共享 engine，首次会加载模型但不会阻塞 UI）
        self._ocr_worker = OCRWorker(region, self._ocr_engine)
        self._ocr_worker.progress.connect(self._on_ocr_progress)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_worker.start()
        logger.info("OCR 工作线程已启动")

    def _on_ocr_progress(self, message: str):
        """OCR 进度更新"""
        self.ocr_text.setText(message)

    def _on_ocr_finished(self, results: list):
        """OCR 识别完成"""
        if not results:
            self.ocr_text.setText("未检测到文字")
        else:
            sorted_results = sorted(results, key=lambda r: r["confidence"], reverse=True)
            text_lines = [r["text"] for r in sorted_results]
            display_text = "\n".join(text_lines)
            self.ocr_text.setText(display_text)
            logger.info(f"OCR 完成: {len(text_lines)} 行文字")

        self.test_ocr_btn.setEnabled(True)
        self.test_ocr_btn.setText("测试OCR")
        self._ocr_worker = None

    def _on_ocr_error(self, message: str):
        """OCR 出错"""
        self.ocr_text.setText(message)
        self.test_ocr_btn.setEnabled(True)
        self.test_ocr_btn.setText("测试OCR")
        self._ocr_worker = None

    def _on_select_region(self):
        """点击「框选区域」按钮后的处理"""
        logger.info("用户点击「框选区域」按钮")
        if self._overlay.isVisible():
            self._overlay.hide()
        self.hide()

        overlay_config = self.config_manager.get_overlay_config()
        self._selector = SelectorWindow(overlay_config)
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.cancelled.connect(self._on_selection_cancelled)

    def _on_region_selected(self, region: dict):
        """区域选择完成后的回调"""
        logger.info(f"区域选择完成: {region}")
        self._selector = None
        self.config_manager.save_region(region)
        self._update_region_display(region)
        self._overlay.update_region(region)

        if self.test_checkbox.isChecked():
            self._overlay.set_test_visible(True)

        self.show()

    def _on_selection_cancelled(self):
        """区域选择取消后的回调"""
        logger.info("区域选择已取消")
        self._selector = None

        if self.test_checkbox.isChecked():
            self._overlay.set_test_visible(True)

        self.show()

    def closeEvent(self, event):
        """窗口关闭时清理"""
        if self._ocr_worker and self._ocr_worker.isRunning():
            self._ocr_worker.quit()
            self._ocr_worker.wait(3000)
        self._overlay.close()
        super().closeEvent(event)