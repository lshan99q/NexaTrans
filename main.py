"""
NexaTrans v0.1
入口模块：应用初始化、日志系统、异常保护
"""

import sys
import os
import logging
import logging.handlers
from datetime import datetime

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, qInstallMessageHandler

# ============================================================
# 日志系统初始化（必须在其他导入之前）
# ============================================================

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def setup_logging():
    """配置日志系统：控制台 + 文件轮转"""
    # 确保日志目录存在
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("NexaTrans")
    logger.setLevel(logging.DEBUG)

    # 防止重复添加处理器
    if logger.handlers:
        return logger

    # 格式化器
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "[%(levelname)s] %(message)s"
    )

    # 文件处理器 - 按大小轮转 (1MB, 保留3个备份)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("=" * 50)
    logger.info("NexaTrans v0.1 启动")
    logger.info(f"日志文件: {LOG_FILE}")
    logger.info("=" * 50)

    return logger


# 初始化日志
logger = setup_logging()


# ============================================================
# Qt 消息处理（捕获 Qt 内部的警告/错误）
# ============================================================

def qt_message_handler(mode, context, message):
    """捕获 Qt 内部消息并记录到日志"""
    msg_type = {
        Qt.DebugMsg: "DEBUG",
        Qt.WarningMsg: "WARNING",
        Qt.CriticalMsg: "CRITICAL",
        Qt.FatalMsg: "FATAL",
        Qt.InfoMsg: "INFO",
    }.get(mode, "UNKNOWN")

    # 构建位置信息
    location = ""
    if context.file:
        location = f" ({context.file}:{context.line}, {context.function})"

    logger.debug(f"[Qt {msg_type}]{location} - {message}")

    # 如果是致命错误，记录后终止
    if mode == Qt.FatalMsg:
        logger.critical(f"Qt 致命错误: {message}")
        sys.exit(1)


# 注册 Qt 消息处理器
qInstallMessageHandler(qt_message_handler)


# ============================================================
# 全局异常处理器
# ============================================================

def global_exception_handler(exctype, value, traceback):
    """捕获所有未处理的异常"""
    logger.critical(
        "未捕获的异常",
        exc_info=(exctype, value, traceback)
    )

    # 显示错误对话框
    try:
        app = QApplication.instance()
        if app:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("NexaTrans - 错误")
            msg_box.setText("程序发生未预期的错误")
            msg_box.setInformativeText(str(value))
            msg_box.setDetailedText(
                "请查看日志文件获取详细信息:\n" + LOG_FILE
            )
            msg_box.exec()
    except Exception:
        pass

    # 调用默认异常处理器
    sys.__excepthook__(exctype, value, traceback)


# 注册全局异常处理器
sys.excepthook = global_exception_handler


# ============================================================
# 配置初始化
# ============================================================

def ensure_directories():
    """确保必要的目录存在"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dirs = [
        os.path.join(base_dir, "config"),
        os.path.join(base_dir, "logs"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        logger.debug(f"目录检查/已创建: {d}")


# ============================================================
# 应用入口
# ============================================================

def main():
    """应用程序主入口"""
    try:
        # 确保目录结构
        ensure_directories()

        # 导入项目模块（在日志和异常保护初始化之后）
        from config.config_manager import ConfigManager
        from ui.main_window import MainWindow

        # 创建应用
        app = QApplication(sys.argv)
        app.setApplicationName("NexaTrans")
        app.setApplicationVersion("0.1.0")
        app.setOrganizationName("NexaTrans")

        logger.info("QApplication 初始化完成")

        # 初始化配置管理器
        config_manager = ConfigManager()
        logger.info("配置管理器初始化完成")

        # 创建并显示主窗口
        window = MainWindow(config_manager)
        window.show()
        logger.info("主窗口已显示")

        # 运行应用事件循环
        exit_code = app.exec()
        logger.info(f"应用程序退出，退出码: {exit_code}")
        sys.exit(exit_code)

    except ImportError as e:
        logger.critical(f"模块导入失败: {e}")
        QMessageBox.critical(
            None, "NexaTrans - 错误",
            f"模块导入失败:\n{e}\n\n请确保已安装所有依赖:\npy -m pip install -r requirements.txt"
        )
        sys.exit(1)

    except Exception as e:
        logger.critical(f"应用启动失败: {e}", exc_info=True)
        QMessageBox.critical(
            None, "NexaTrans - 错误",
            f"应用启动失败:\n{e}\n\n请查看日志: {LOG_FILE}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()