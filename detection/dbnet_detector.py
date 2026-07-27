"""
NexaTrans - DBNet++ Detector
Text detection using PaddleOCR's DBNet++ model via ONNX Runtime.
Model is loaded once and reused across frames.
Supports automatic image resizing for speed/accuracy tradeoff.
"""

import logging
import numpy as np

logger = logging.getLogger("NexaTrans.DBNetDetector")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


class DBNetDetector:
    """DBNet++ text detector using PaddleX create_predictor (detection only)."""

    def __init__(self, model_path: str = None, limit_side_len: int = 960):
        """
        Initialize the DBNet++ detector.

        Args:
            model_path: Optional path to custom model directory.
            limit_side_len: Max side length for detection input.
                            Lower = faster but may miss small text.
                            Recommended: 640 (balanced), 960 (accurate).
        """
        self._model_path = model_path
        self._limit_side_len = limit_side_len
        self._predictor = None
        self._loaded = False
        self._load_model()

    def _load_model(self):
        """Load the detection model once using PaddleX create_predictor."""
        try:
            from paddlex import create_predictor
        except ImportError:
            logger.critical("PaddleX not installed. Run: pip install paddleocr")
            self._loaded = False
            return

        try:
            model_name = "PP-OCRv6_medium_det"
            self._predictor = create_predictor(model_name, engine="onnxruntime")
            self._loaded = True
            logger.info(
                f"DBNet++ detector loaded "
                f"({model_name}, ONNX Runtime, limit={self._limit_side_len}px)"
            )
        except Exception as e:
            logger.error(f"Failed to load DBNet++ model: {e}", exc_info=True)
            self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """Check if the model is loaded and ready."""
        return self._loaded

    @property
    def limit_side_len(self) -> int:
        return self._limit_side_len

    @limit_side_len.setter
    def limit_side_len(self, value: int):
        self._limit_side_len = max(240, min(value, 1920))

    def detect(self, image: np.ndarray) -> list:
        """
        Detect text regions in an image.

        Args:
            image: numpy array (H, W, 3) in BGR format.

        Returns:
            List of polygons, each as [x1,y1, x2,y2, x3,y3, x4,y4]
            in the original image coordinate space.
        """
        if not self._loaded:
            logger.warning("DBNet++ model not loaded, skipping detection")
            return []

        if image is None or image.size == 0:
            logger.warning("Empty image passed to detector")
            return []

        try:
            h, w = image.shape[:2]
            scale_x, scale_y = 1.0, 1.0
            input_image = image

            # Resize only if the image is larger than limit_side_len
            # and the short side is at least 32px (avoid collapsing small images)
            longest = max(w, h)
            shortest = min(w, h)
            min_short_side = 32

            if HAS_CV2 and longest > self._limit_side_len and shortest >= min_short_side:
                scale = self._limit_side_len / longest
                new_w = max(int(w * scale), 1)
                new_h = max(int(h * scale), 1)
                input_image = cv2.resize(image, (new_w, new_h))
                scale_x = w / new_w
                scale_y = h / new_h
                logger.debug(
                    f"Resized detection input: {w}x{h} -> {new_w}x{new_h} "
                    f"(scale={scale:.3f})"
                )

            results = list(self._predictor(input_image))

            if not results:
                return []

            r = results[0]
            polys = r.get("dt_polys", [])

            if polys is None or len(polys) == 0:
                return []

            polygons = []
            for poly in polys:
                if poly is None or len(poly) < 4:
                    continue

                flat = []
                for pt in poly:
                    if hasattr(pt, "__iter__") and len(pt) >= 2:
                        flat.extend([
                            int(round(pt[0] * scale_x)),
                            int(round(pt[1] * scale_y)),
                        ])

                if len(flat) >= 8:
                    polygons.append(flat)

            logger.debug(f"Detected {len(polygons)} text region(s) in {w}x{h} image")
            return polygons

        except Exception as e:
            logger.error(f"Detection failed: {e}", exc_info=True)
            return []
