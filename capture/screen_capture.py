"""
NexaTrans - Screen Capture
屏幕截图模块：使用 PIL.ImageGrab 截取指定区域
"""

import logging
from PIL import ImageGrab, Image

logger = logging.getLogger("NexaTrans.ScreenCapture")


def capture_region(region: dict) -> Image.Image | None:
    """
    截取指定区域的屏幕画面

    参数:
        region: {
            "x": int,       # 左上角 X 坐标
            "y": int,       # 左上角 Y 坐标
            "width": int,   # 区域宽度
            "height": int   # 区域高度
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

        # 构建 bbox: (left, top, right, bottom)
        bbox = (x, y, x + w, y + h)
        logger.debug(f"截图区域: {bbox}")

        # 截取屏幕
        screenshot = ImageGrab.grab(bbox=bbox, all_screens=True)
        logger.info(f"截图成功: 尺寸 {screenshot.size}")
        return screenshot

    except Exception as e:
        logger.error(f"截图失败: {e}", exc_info=True)
        return None