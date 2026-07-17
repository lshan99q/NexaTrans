"""
NexaTrans - Main Window
主界面模块：显示翻译区域信息，提供框选入口
"""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal

from config.config_manager import ConfigManager
from ui.selector_window import SelectorWindow

logger = logging.getLogger("NexaTrans.MainWindow")


class MainWindow(QWidget):
    """主窗口"""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self._setup_ui()
        self._load_region()
        logger.info("主窗口初始化完成")

    def _setup_ui(self):
        """设置UI界面"""
        self.setWindowTitle("NexaTrans")
        self.setFixedSize(360, 300)

        # 主布局
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 标题
        title_label = QLabel("NexaTrans")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = title_label.font()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # 区域信息分组
        group_box = QGroupBox("当前翻译区域")
        form_layout = QFormLayout()

        self.label_x = QLabel("0")
        self.label_y = QLabel("0")
        self.label_width = QLabel("0")
        self.label_height = QLabel("0")

        form_layout.addRow("X:", self.label_x)
        form_layout.addRow("Y:", self.label_y)
        form_layout.addRow("Width:", self.label_width)
        form_layout.addRow("Height:", self.label_height)

        group_box.setLayout(form_layout)
        layout.addWidget(group_box)

        # 框选按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.select_btn = QPushButton("框选区域")
        self.select_btn.setFixedSize(120, 40)
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

    def _update_region_display(self, region: dict):
        """更新界面上的区域信息显示"""
        self.label_x.setText(str(region.get("x", 0)))
        self.label_y.setText(str(region.get("y", 0)))
        self.label_width.setText(str(region.get("width", 0)))
        self.label_height.setText(str(region.get("height", 0)))

    def _on_select_region(self):
        """点击「框选区域」按钮后的处理"""
        logger.info("用户点击「框选区域」按钮")
        self.hide()  # 隐藏主窗口

        # 获取覆盖层配置
        overlay_config = self.config_manager.get_overlay_config()

        # 打开选择窗口
        selector = SelectorWindow(overlay_config)
        selector.region_selected.connect(self._on_region_selected)
        selector.cancelled.connect(self._on_selection_cancelled)
        selector.show()

    def _on_region_selected(self, region: dict):
        """区域选择完成后的回调"""
        logger.info(f"区域选择完成: {region}")
        # 保存区域配置
        self.config_manager.save_region(region)
        # 更新显示
        self._update_region_display(region)
        # 显示主窗口
        self.show()

    def _on_selection_cancelled(self):
        """区域选择取消后的回调"""
        logger.info("区域选择已取消")
        # 显示主窗口
        self.show()