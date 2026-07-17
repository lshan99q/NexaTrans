"""
NexaTrans - OCR Engine
OCR 识别引擎：使用 EasyOCR 进行文字识别
"""

import logging
import numpy as np
from PIL import Image

logger = logging.getLogger("NexaTrans.OCR")


class OCREngine:
    """OCR 识别引擎（懒加载初始化）"""

    def __init__(self, languages: list = None):
        """
        初始化 OCR 引擎

        参数:
            languages: 识别的语言列表，默认 ['ch_sim', 'en']（中文+英文）
        """
        self._languages = languages or ['ch_sim', 'en']
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
                verbose=False
            )
            self._initialized = True
            logger.info("OCR 模型初始化完成")

    def recognize(self, image: Image.Image) -> list[dict]:
        """
        识别图片中的文字

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

            img_array = np.array(image)
            results = self._reader.readtext(img_array)

            # 转换结果格式
            ocr_results = []
            for (bbox, text, confidence) in results:
                x_coords = [p[0] for p in bbox]
                y_coords = [p[1] for p in bbox]
                box = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]

                ocr_results.append({
                    "text": text,
                    "confidence": round(confidence, 4),
                    "box": box
                })

            logger.info(f"OCR 识别完成: {len(ocr_results)} 个文字块")
            return ocr_results

        except Exception as e:
            logger.error(f"OCR 识别失败: {e}", exc_info=True)
            return []