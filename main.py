"""
NexaTrans v1.0
鍏ュ彛妯″潡锛氬簲鐢ㄥ垵濮嬪寲銆佹棩蹇楃郴缁熴€佸紓甯镐繚鎶?
"""

import sys
import os
import logging
import logging.handlers
from datetime import datetime

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, qInstallMessageHandler

# ============================================================
# 鏃ュ織绯荤粺鍒濆鍖栵紙蹇呴』鍦ㄥ叾浠栧鍏ヤ箣鍓嶏級
# ============================================================

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def setup_logging():
    """閰嶇疆鏃ュ織绯荤粺锛氭帶鍒跺彴 + 鏂囦欢杞浆"""
    # 纭繚鏃ュ織鐩綍瀛樺湪
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("NexaTrans")
    logger.setLevel(logging.DEBUG)

    # 闃叉閲嶅娣诲姞澶勭悊鍣?
    if logger.handlers:
        return logger

    # 鏍煎紡鍖栧櫒
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "[%(levelname)s] %(message)s"
    )

    # 鏂囦欢澶勭悊鍣?- 鎸夊ぇ灏忚疆杞?(1MB, 淇濈暀3涓浠?
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # 鎺у埗鍙板鐞嗗櫒
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("=" * 50)
    logger.info("NexaTrans v1.0 鍚姩")
    logger.info(f"鏃ュ織鏂囦欢: {LOG_FILE}")
    logger.info("=" * 50)

    return logger


# 鍒濆鍖栨棩蹇?
logger = setup_logging()


# ============================================================
# Qt 娑堟伅澶勭悊锛堟崟鑾?Qt 鍐呴儴鐨勮鍛?閿欒锛?
# ============================================================

def qt_message_handler(mode, context, message):
    """鎹曡幏 Qt 鍐呴儴娑堟伅骞惰褰曞埌鏃ュ織"""
    msg_type = {
        Qt.DebugMsg: "DEBUG",
        Qt.WarningMsg: "WARNING",
        Qt.CriticalMsg: "CRITICAL",
        Qt.FatalMsg: "FATAL",
        Qt.InfoMsg: "INFO",
    }.get(mode, "UNKNOWN")

    # 鏋勫缓浣嶇疆淇℃伅
    location = ""
    if context.file:
        location = f" ({context.file}:{context.line}, {context.function})"

    logger.debug(f"[Qt {msg_type}]{location} - {message}")

    # 濡傛灉鏄嚧鍛介敊璇紝璁板綍鍚庣粓姝?
    if mode == Qt.FatalMsg:
        logger.critical(f"Qt 鑷村懡閿欒: {message}")
        sys.exit(1)


# 娉ㄥ唽 Qt 娑堟伅澶勭悊鍣?
qInstallMessageHandler(qt_message_handler)


# ============================================================
# 鍏ㄥ眬寮傚父澶勭悊鍣?
# ============================================================

def global_exception_handler(exctype, value, traceback):
    """鎹曡幏鎵€鏈夋湭澶勭悊鐨勫紓甯?""
    logger.critical(
        "鏈崟鑾风殑寮傚父",
        exc_info=(exctype, value, traceback)
    )

    # 鏄剧ず閿欒瀵硅瘽妗?
    try:
        app = QApplication.instance()
        if app:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("NexaTrans - 閿欒")
            msg_box.setText("绋嬪簭鍙戠敓鏈鏈熺殑閿欒")
            msg_box.setInformativeText(str(value))
            msg_box.setDetailedText(
                "璇锋煡鐪嬫棩蹇楁枃浠惰幏鍙栬缁嗕俊鎭?\n" + LOG_FILE
            )
            msg_box.exec()
    except Exception:
        pass

    # 璋冪敤榛樿寮傚父澶勭悊鍣?
    sys.__excepthook__(exctype, value, traceback)


# 娉ㄥ唽鍏ㄥ眬寮傚父澶勭悊鍣?
sys.excepthook = global_exception_handler


# ============================================================
# 閰嶇疆鍒濆鍖?
# ============================================================

def ensure_directories():
    """纭繚蹇呰鐨勭洰褰曞瓨鍦?""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dirs = [
        os.path.join(base_dir, "config"),
        os.path.join(base_dir, "logs"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        logger.debug(f"鐩綍妫€鏌?宸插垱寤? {d}")


# ============================================================
# 搴旂敤鍏ュ彛
# ============================================================

def main():
    """搴旂敤绋嬪簭涓诲叆鍙?""
    try:
        # 纭繚鐩綍缁撴瀯
        ensure_directories()

        # 瀵煎叆椤圭洰妯″潡锛堝湪鏃ュ織鍜屽紓甯镐繚鎶ゅ垵濮嬪寲涔嬪悗锛?
        from config.config_manager import ConfigManager
        from ui.main_window import MainWindow

        # 鍒涘缓搴旂敤
        app = QApplication(sys.argv)
        app.setApplicationName("NexaTrans")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("NexaTrans")

        logger.info("QApplication 鍒濆鍖栧畬鎴?)

        # 鍒濆鍖栭厤缃鐞嗗櫒
        config_manager = ConfigManager()
        logger.info("閰嶇疆绠＄悊鍣ㄥ垵濮嬪寲瀹屾垚")

        # 鍒涘缓骞舵樉绀轰富绐楀彛
        window = MainWindow(config_manager)
        window.show()
        logger.info("涓荤獥鍙ｅ凡鏄剧ず")

        # 杩愯搴旂敤浜嬩欢寰幆
        exit_code = app.exec()
        logger.info(f"搴旂敤绋嬪簭閫€鍑猴紝閫€鍑虹爜: {exit_code}")
        sys.exit(exit_code)

    except ImportError as e:
        logger.critical(f"妯″潡瀵煎叆澶辫触: {e}")
        QMessageBox.critical(
            None, "NexaTrans - 閿欒",
            f"妯″潡瀵煎叆澶辫触:\n{e}\n\n璇风‘淇濆凡瀹夎鎵€鏈変緷璧?\npy -m pip install -r requirements.txt"
        )
        sys.exit(1)

    except Exception as e:
        logger.critical(f"搴旂敤鍚姩澶辫触: {e}", exc_info=True)
        QMessageBox.critical(
            None, "NexaTrans - 閿欒",
            f"搴旂敤鍚姩澶辫触:\n{e}\n\n璇锋煡鐪嬫棩蹇? {LOG_FILE}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()