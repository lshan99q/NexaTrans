"""
NexaTrans - DBNet++ Detector
Text detection using PaddleOCR's DBNet++ model via ONNX Runtime.
Model is loaded once and reused across frames.
Returns both boxes and confidence scores for filtering.
"""

import logging
import os
import sys
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
        self._model_path = model_path
        self._limit_side_len = limit_side_len
        self._predictor = None
        self._loaded = False
        # Resolve bundled model path
        if getattr(sys, "frozen", False):
            bundled = os.path.join(sys._MEIPASS, "models", "official_models", "PP-OCRv6_medium_det_onnx")
        else:
            bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "official_models", "PP-OCRv6_medium_det_onnx")
        if os.path.isdir(bundled):
            self._bundled_model = bundled
        else:
            self._bundled_model = None
        self._load_model()

    def _load_model(self):
        try:
            from paddlex import create_predictor
        except ImportError:
            import traceback as _tb
            logger.critical("PaddleX import failed. Full traceback:", exc_info=True)
            logger.critical(_tb.format_exc())
            self._loaded = False
            return
        try:
            if self._bundled_model:
                self._predictor = create_predictor("PP-OCRv6_medium_det", model_dir=self._bundled_model, engine="onnxruntime")
            else:
                self._predictor = create_predictor("PP-OCRv6_medium_det", engine="onnxruntime")
            self._loaded = True
            logger.info(f"DBNet++ detector loaded (limit={self._limit_side_len}px)")
        except Exception as e:
            logger.error(f"Failed to load DBNet++ model: {e}", exc_info=True)
            self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def limit_side_len(self) -> int:
        return self._limit_side_len

    @limit_side_len.setter
    def limit_side_len(self, value: int):
        self._limit_side_len = max(240, min(value, 1920))

    def detect(self, image: np.ndarray) -> dict:
        """
        Detect text regions.

        Returns:
            {"boxes": [[x1,y1,...], ...], "scores": [0.95, ...]}
            Empty dict if no text found or error.
        """
        if not self._loaded:
            return {"boxes": [], "scores": []}
        if image is None or image.size == 0:
            return {"boxes": [], "scores": []}

        try:
            h, w = image.shape[:2]
            scale_x, scale_y = 1.0, 1.0
            input_image = image
            longest = max(w, h)
            shortest = min(w, h)

            if HAS_CV2 and longest > self._limit_side_len and shortest >= 32:
                scale = self._limit_side_len / longest
                new_w = max(int(w * scale), 1)
                new_h = max(int(h * scale), 1)
                input_image = cv2.resize(image, (new_w, new_h))
                scale_x = w / new_w
                scale_y = h / new_h

            results = list(self._predictor(input_image))
            if not results:
                return {"boxes": [], "scores": []}

            r = results[0]
            polys = r.get("dt_polys", [])
            scores = r.get("dt_scores", [])

            if polys is None or len(polys) == 0:
                return {"boxes": [], "scores": []}

            boxes = []
            out_scores = []
            for i, poly in enumerate(polys):
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
                    boxes.append(flat)
                    score = float(scores[i]) if i < len(scores) else 0.5
                    out_scores.append(score)

            logger.debug(f"Detected {len(boxes)} regions in {w}x{h} image")
            return {"boxes": boxes, "scores": out_scores}

        except Exception as e:
            logger.error(f"Detection failed: {e}", exc_info=True)
            return {"boxes": [], "scores": []}
