"""
NexaTrans - OCR Engine (Stage 5)
Abstract base class + PaddleOCR recognition implementation.
"""

import logging
import time
import numpy as np

logger = logging.getLogger("NexaTrans.OCR.Engine")


class OCREngine:
    """Abstract OCR engine interface."""

    @property
    def is_loaded(self) -> bool:
        raise NotImplementedError

    def recognize(self, image: np.ndarray) -> dict:
        """Return {"text": str, "confidence": float}."""
        raise NotImplementedError


class PaddleOCREngine(OCREngine):
    """PaddleOCR PP-OCRv4 recognition engine."""

    def __init__(self):
        self._ocr = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self):
        """Lazy-load PaddleOCR recognition model."""
        if self._loaded:
            return True
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                lang="ch",
                use_angle_cls=True,
                show_log=False,
            )
            self._loaded = True
            logger.info("PaddleOCR recognition engine loaded")
            return True
        except Exception as e:
            logger.error(f"PaddleOCR recognition load failed: {e}")
            return False

    def recognize(self, image: np.ndarray) -> dict:
        """Recognize text from preprocessed image."""
        if not self._loaded:
            return {"text": "", "confidence": 0.0}

        try:
            t0 = time.time()
            result = self._ocr.ocr(image, cls=True)
            elapsed_ms = (time.time() - t0) * 1000

            if not result or not result[0]:
                return {"text": "", "confidence": 0.0, "elapsed_ms": elapsed_ms}

            # PaddleOCR returns: [[[box], (text, confidence)], ...]
            texts = []
            confs = []
            for line in result[0]:
                if len(line) >= 2:
                    rec = line[1]
                    texts.append(str(rec[0]) if rec[0] else "")
                    confs.append(float(rec[1]) if len(rec) > 1 else 0.0)

            text = "".join(texts)
            conf = float(np.mean(confs)) if confs else 0.0

            return {
                "text": text,
                "confidence": round(conf, 4),
                "elapsed_ms": round(elapsed_ms, 1),
            }
        except Exception as e:
            logger.error(f"OCR recognition failed: {e}")
            return {"text": "", "confidence": 0.0}