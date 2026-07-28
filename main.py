# -*- coding: utf-8 -*-
"""
NexaTrans v1.0
Application entry: logging, exceptions, initialization.
"""

import sys
import os
import logging
import logging.handlers

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, qInstallMessageHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Detect if running without console (e.g. .pyw or pythonw.exe)
HAS_CONSOLE = sys.stdout is not None and hasattr(sys.stdout, "fileno") and sys.stdout.fileno() >= 0


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("NexaTrans")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger

    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Only add console handler if running with console visible
    if HAS_CONSOLE:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(console_handler)

    logger.info("=" * 50)
    logger.info("NexaTrans v1.0 Startup")
    logger.info(f"Log: {LOG_FILE}")
    logger.info("=" * 50)
    return logger


logger = setup_logging()


def qt_message_handler(mode, context, message):
    msg_type = {
        Qt.DebugMsg: "DEBUG",
        Qt.WarningMsg: "WARNING",
        Qt.CriticalMsg: "CRITICAL",
        Qt.FatalMsg: "FATAL",
        Qt.InfoMsg: "INFO",
    }.get(mode, "UNKNOWN")
    location = ""
    if context.file:
        location = f" ({context.file}:{context.line}, {context.function})"
    logger.debug(f"[Qt {msg_type}]{location} - {message}")
    if mode == Qt.FatalMsg:
        logger.critical(f"Qt Fatal: {message}")
        sys.exit(1)


qInstallMessageHandler(qt_message_handler)


def global_exception_handler(exctype, value, traceback):
    logger.critical("Uncaught exception", exc_info=(exctype, value, traceback))
    try:
        app = QApplication.instance()
        if app:
            QMessageBox.critical(
                None, "NexaTrans - Error",
                f"Unexpected error:\n{value}\n\nSee {LOG_FILE}"
            )
    except Exception:
        pass
    sys.__excepthook__(exctype, value, traceback)


sys.excepthook = global_exception_handler


def ensure_directories():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for d in ["config", "logs"]:
        os.makedirs(os.path.join(base_dir, d), exist_ok=True)


def main():
    try:
        ensure_directories()
        from config.config_manager import ConfigManager
        from ui.main_window import MainWindow

        app = QApplication(sys.argv)
        app.setApplicationName("NexaTrans")
        app.setApplicationVersion("1.1.0")
        app.setOrganizationName("NexaTrans")

        config_manager = ConfigManager()
        window = MainWindow(config_manager)
        window.show()

        exit_code = app.exec()
        logger.info(f"Exit code: {exit_code}")
        sys.exit(exit_code)

    except ImportError as e:
        logger.critical(f"Import failed: {e}")
        QMessageBox.critical(
            None, "NexaTrans - Error",
            f"Module import failed:\n{e}\n\nInstall dependencies:\npy -m pip install -r requirements.txt"
        )
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Startup failed: {e}", exc_info=True)
        QMessageBox.critical(
            None, "NexaTrans - Error",
            f"Startup failed:\n{e}\n\nSee {LOG_FILE}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
