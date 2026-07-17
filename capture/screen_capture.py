"""
NexaTrans - Screen Capture
屏幕截图模块：使用 PIL.ImageGrab 截取指定区域
自动处理 DPI 缩放（逻辑坐标→物理坐标）
"""

import logging
from PIL import ImageGrab, Image
from PySide6.QtWidgets import QApplication

logger = logging.getLogger("NexaTrans.ScreenCapture")


def get_dpi_scale() -> float:
    """获取逻辑坐标到物理坐标的缩放因子"""
    try:
        # 直接比较逻辑分辨率与物理分辨率
        app = QApplication.instance()
        if not app:
            return 1.0

        screen = app.primaryScreen()
        if not screen:
            return 1.0

        # 物理大小（ImageGrab 使用）
        physical_size = screen.size()  # QSize
        # 逻辑大小（Qt 使用）
        logical_size = screen.availableSize()  # 这个可能不准
        
        # 更可靠的方法：比较实际截图
        geo = screen.geometry()
        log_w = geo.width()
        log_h = geo.height()

        # 截取全屏测试物理尺寸
        full = ImageGrab.grab()
        phy_w, phy_h = full.size

        scale_x = phy_w / log_w if log_w > 0 else 1.0
        scale_y = phy_h / log_h if log_h > 0 else 1.0
        scale = max(scale_x, scale_y)

        if abs(scale - 1.0) > 0.01:
            logger.debug(f"DPI缩放: {scale:.2f}x (逻辑{log_w}x{log_h} → 物理{phy_w}x{phy_h})")
        return scale

    except Exception as e:
        logger.warning(f"获取DPI缩放失败: {e}")
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

        # 获取缩放因子，将逻辑坐标转为物理像素坐标
        scale = get_dpi_scale()
        if abs(scale - 1.0) > 0.01:
            px = int(round(x * scale))
            py = int(round(y * scale))
            pw = int(round(w * scale))
            ph = int(round(h * scale))
            logger.debug(f"坐标缩放: ({x},{y},{w}x{h}) → ({px},{py},{pw}x{ph})")
            x, y, w, h = px, py, pw, ph

        # 截取主屏幕
        full_screen = ImageGrab.grab()
        logger.debug(f"主屏幕截图: {full_screen.size}")

        # 裁剪指定区域
        crop_box = (x, y, x + w, y + h)
        screenshot = full_screen.crop(crop_box)
        logger.info(f"截图成功: ({x},{y},{w}x{h}) → 尺寸 {screenshot.size}")
        return screenshot

    except Exception as e:
        logger.error(f"截图失败: {e}", exc_info=True)
        return None