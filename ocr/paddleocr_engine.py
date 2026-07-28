"""
NexaTrans - PaddleOCR Engine (Stage 5)
PP-OCRv5 Recognition wrapper using PaddleX ONNX Runtime.
Recognition only (no detection) - DBNet++ handles detection.
"""

import logging
import numpy as np

logger = logging.getLogger("NexaTrans.OCREngine")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class PaddleOCREngine:
    """PP-OCRv5 Recognition engine via PaddleX ONNX."""

    def __init__(self, lang: str = "ch"):
        self._lang = lang
        self._predictor = None
        self._loaded = False
        self._load_model()

    def _load_model(self):
        try:
            from paddlex import create_predictor
            self._predictor = create_predictor(
                "PP-OCRv5_mobile_rec", engine="onnxruntime"
            )
            self._loaded = True
            logger.info("PP-OCRv5_mobile_rec loaded via PaddleX ONNX")
        except ImportError:
            logger.critical("PaddleX not installed. Run: pip install paddleocr")
            self._loaded = False
        except Exception as e:
            logger.error(f"Failed to load OCR model: {e}", exc_info=True)
            self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def recognize(self, image: np.ndarray) -> dict:
        """
        Recognize text from a cropped image.

        Args:
            image: Cropped text image (H, W, 3) in BGR format.

        Returns:
            {"text": str, "confidence": float}
            On failure: {"text": "", "confidence": 0.0}
        """
        if not self._loaded:
            return {"text": "", "confidence": 0.0}
        if image is None or image.size == 0:
            return {"text": "", "confidence": 0.0}

        try:
            h, w = image.shape[:2]
            if h < 8 or w < 8:
                return {"text": "", "confidence": 0.0}

            results = list(self._predictor(image))
            if not results:
                return {"text": "", "confidence": 0.0}

            r = results[0]
            text = str(r.get("rec_text", "") or "")
            score = float(r.get("rec_score", 0.0) or 0.0)

            logger.debug(f"OCR: '{text}' (conf={score:.3f})")
            return {"text": text, "confidence": score}

        except Exception as e:
            logger.error(f"OCR recognition failed: {e}", exc_info=True)
            return {"text": "", "confidence": 0.0}

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR: CLAHE contrast enhancement.

        Args:
            image: Input BGR image.

        Returns:
            Enhanced BGR image.
        """
        if not HAS_CV2:
            return image
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
        except Exception:
            return image
