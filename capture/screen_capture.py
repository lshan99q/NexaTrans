"""
NexaTrans - Screen Capture
屏幕截图模块：使用 PIL.ImageGrab 截取指定区域
支持 DPI 缩放转换（解决高分屏坐标偏差）
"""

import logging
from PIL import ImageGrab, Image
from PySide6.QtWidgets import QApplication

logger = logging.getLogger("NexaTrans.ScreenCapture")


def _get_dpi_scale() -> float:
    """获取当前屏幕的 DPI 缩放比例"""
    try:
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                # 逻辑分辨率 vs 物理分辨率
                log_dpi = screen.logicalDotsPerInch()
                phy_dpi = screen.physicalDotsPerInch()
                # Windows 默认 DPI 是 96
                scale = log_dpi / 96.0
                logger.debug(f"DPI 缩放比例: {scale:.2f} (logical={log_dpi:.0f}, physical={phy_dpi:.0f})")
                return scale
        return 1.0
    except Exception as e:
        logger.warning(f"获取 DPI 缩放失败: {e}，使用默认 1.0")
        return 1.0


def capture_region(region: dict) -> Image.Image | None:
    """
    截取指定区域的屏幕画面（自动处理 DPI 缩放）

    参数:
        region: {
            "x": int,       # 左上角 X 坐标（逻辑坐标）
            "y": int,       # 左上角 Y 坐标（逻辑坐标）
            "width": int,   # 区域宽度（逻辑坐标）
            "height": int   # 区域高度（逻辑坐标）
        }

    返回:
        PIL.Image 对象，失败时返回 None
    """
    try:
        x = region.get("x", 0)
        y = region.get("y", 0)
        w = region.get("width", 0)
        h = region.get("height", 0)

        if w <= 0 or h <= 0:
            logger.warning(f"无效的区域尺寸: {w}x{h}")
            return None

        # 获取 DPI 缩放因子，将逻辑坐标转换为物理坐标
        scale = _get_dpi_scale()
        if scale != 1.0:
            px = int(round(x * scale))
            py = int(round(y * scale))
            pw = int(round(w * scale))
            ph = int(round(h * scale))
            logger.debug(f"DPI转换: ({x},{y},{w}x{h}) → ({px},{py},{pw}x{ph})")
        else:
            px, py, pw, ph = x, y, w, h

        # 构建 bbox: (left, top, right, bottom)
        bbox = (px, py, px + pw, py + ph)
        logger.debug(f"截图区域: {bbox}")

        # 截取屏幕
        screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)
        logger.info(f"截图成功: 尺寸 {screenshot.size}")
        return screenshot

    except Exception as e:
        logger.error(f"截图失败: {e}", exc_info=True)
        return None