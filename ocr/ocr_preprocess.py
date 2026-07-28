"""
NexaTrans - OCR Preprocessing (Stage 5)
Grayscale, CLAHE contrast enhancement, resize with aspect-ratio-preserving padding.
"""

import logging
import numpy as np

logger = logging.getLogger("NexaTrans.OCR.Preprocess")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class OCRPreprocessor:
    """Preprocess text region images for OCR."""

    def __init__(self, target_height: int = 48, clahe_clip: float = 2.0):
        self._target_h = target_height
        self._clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8)) if HAS_CV2 else None

    def process(self, image: np.ndarray) -> np.ndarray:
        """Convert BGR crop to normalized grayscale with CLAHE + padding."""
        if not HAS_CV2:
            return image

        h, w = image.shape[:2]
        if h <= 0 or w <= 0:
            return image

        # Grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # CLAHE contrast enhancement
        if self._clahe is not None:
            gray = self._clahe.apply(gray)

        # Resize preserving aspect ratio
        scale = self._target_h / h
        new_w = max(1, int(w * scale))
        resized = cv2.resize(gray, (new_w, self._target_h), interpolation=cv2.INTER_CUBIC)

        return resized