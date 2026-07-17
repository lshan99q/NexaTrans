"""
NexaTrans - OCR Engine
OCR 识别引擎：使用 EasyOCR 进行文字识别（已优化速度）
"""

import logging
import numpy as np
from PIL import Image

logger = logging.getLogger("NexaTrans.OCR")


class OCREngine:
    """OCR 识别引擎（懒加载初始化，速度优化版）"""

    # 最大输入尺寸（像素）- 缩小大图可大幅提升 CPU 识别速度
    MAX_IMAGE_SIZE = 1280

    def __init__(self, languages: list = None):
        """
        初始化 OCR 引擎

        参数:
            languages: 识别的语言列表，默认 ['en']（仅英文更快）
                       需要中文时改为 ['ch_sim', 'en']
        """
        # 默认仅英文更快；用户可在后续版本中切换
        self._languages = languages or ['en']
        self._reader = None
        self._initialized = False

    def _lazy_init(self):
        """懒加载：首次使用时初始化 EasyOCR Reader"""
        if not self._initialized:
            logger.info(f"正在初始化 OCR 模型（语言: {self._languages}）...")
            import easyocr
            self._reader = easyocr.Reader(
                self._languages,
                gpu=False,
                verbose=False,
                # 以下参数可加速 CPU 加载
                model_storage_directory=None,
                download_enabled=True
            )
            self._initialized = True
            logger.info("OCR 模型初始化完成")

    def _resize_if_needed(self, image: Image.Image) -> Image.Image:
        """如果图片太大，等比缩小到 MAX_IMAGE_SIZE 以内"""
        w, h = image.size
        max_dim = max(w, h)

        if max_dim > self.MAX_IMAGE_SIZE:
            scale = self.MAX_IMAGE_SIZE / max_dim
            new_w = int(w * scale)
            new_h = int(h * scale)
            # 使用 LANCZOS 高质量缩放
            resized = image.resize((new_w, new_h), Image.LANCZOS)
            logger.debug(f"图像缩放: {w}x{h} → {new_w}x{new_h} (缩放比 {scale:.2f})")
            return resized

        return image

    def recognize(self, image: Image.Image) -> list[dict]:
        """
        识别图片中的文字（速度优化版）

        参数:
            image: PIL.Image 对象

        返回:
            [
                {
                    "text": "识别的文字",
                    "confidence": 0.95,
                    "box": [x1, y1, x2, y2]
                },
                ...
            ]
        """
        try:
            self._lazy_init()

            # 1. 缩小大图提升速度
            image = self._resize_if_needed(image)

            # 2. 转换为 numpy array
            img_array = np.array(image)

            # 3. 执行 OCR（使用速度优化参数）
            results = self._reader.readtext(
                img_array,
                # 速度优化参数
                paragraph=True,          # 段落模式：合并相邻文字，减少结果数
                text_threshold=0.7,      # 提高文字阈值，过滤低置信度结果
                low_text=0.4,            # 降低低文字阈值
                link_threshold=0.4,      # 链接阈值
                canvas_size=1280,        # 限制处理画布大小
                mag_ratio=1.0,           # 放大比例，1.0 为原尺寸
                slope_ths=0.1,           # 倾斜容差
                ycenter_ths=0.5,         # Y 轴中心容差
                width_ths=0.8,           # 宽度容差
                add_margin=0.1,          # 边框余量
                reformat=True            # 优化输出格式
            )

            # 4. 转换结果格式
            ocr_results = []
            for (bbox, text, confidence) in results:
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                box = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]

                ocr_results.append({
                    "text": text.strip(),
                    "confidence": round(confidence, 4),
                    "box": box
                })

            logger.info(f"OCR 识别完成: {len(ocr_results)} 个文字块")
            return ocr_results

        except Exception as e:
            logger.error(f"OCR 识别失败: {e}", exc_info=True)
            return []