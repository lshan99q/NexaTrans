"""
NexaTrans - Screen Capture
屏幕截图模块：使用 PIL.ImageGrab 截取指定区域
只截取主屏幕区域（解决多显示器虚拟桌面坐标偏差）
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

        # 只截取主屏幕（不含 all_screens=True，避免虚拟桌面坐标偏差）
        full_screen = ImageGrab.grab()
        logger.debug(f"主屏幕截图尺寸: {full_screen.size}")

        # 裁剪指定区域
        crop_box = (x, y, x + w, y + h)
        screenshot = full_screen.crop(crop_box)
        logger.info(f"截图成功: 区域 ({x},{y},{w}x{h}) → 尺寸 {screenshot.size}")
        return screenshot

    except Exception as e:
        logger.error(f"截图失败: {e}", exc_info=True)
        return None