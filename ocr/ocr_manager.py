"""
NexaTrans - OCR Manager (Stage 5)
Top-level OCR coordinator: engine, preprocessor, cache, worker.
Integrates with text_processing crops and detection pipeline.
"""

import logging
import numpy as np
from ocr.ocr_engine import PaddleOCREngine
from ocr.ocr_preprocess import OCRPreprocessor
from ocr.ocr_cache import OCRCache
from ocr.ocr_worker import OCRWorker

logger = logging.getLogger("NexaTrans.OCR.Manager")


class OCRManager:
    """Manages OCR engine lifecycle, preprocessing, caching, and async worker."""

    def __init__(self, config: dict = None, on_result=None):
        cfg = config or {}
        self._engine = PaddleOCREngine()
        self._preprocessor = OCRPreprocessor(
            target_height=cfg.get("target_height", 48),
            clahe_clip=cfg.get("clahe_clip", 2.0),
        )
        self._cache = OCRCache(max_size=cfg.get("cache_size", 500))
        self._worker = OCRWorker(
            engine=self._engine,
            preprocessor=self._preprocessor,
            cache=self._cache,
            on_result=on_result,
        )
        self._enabled = cfg.get("enabled", True)
        self._confidence_threshold = cfg.get("confidence_threshold", 0.5)
        self._crop_processor = None
        self._layout_analyzer = None

    @property
    def is_running(self) -> bool:
        return self._worker.is_running

    @property
    def latest_results(self) -> list:
        return self._worker.latest_results

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @is_enabled.setter
    def is_enabled(self, v: bool):
        self._enabled = v
        if not v:
            self._cache.clear()

    def start(self):
        if not self._enabled:
            return False
        self._init_processors()
        self._worker.start()
        return True

    def stop(self):
        self._worker.stop()

    def _init_processors(self):
        if self._crop_processor is None:
            from text_processing.crop_processor import CropProcessor
            self._crop_processor = CropProcessor()
        if self._layout_analyzer is None:
            from text_processing.layout_analyzer import LayoutAnalyzer
            self._layout_analyzer = LayoutAnalyzer()

    def submit(self, image: np.ndarray, boxes: list, mask=None):
        """Submit full image + boxes for OCR. Crops, analyzes direction, sends to worker."""
        if not self._enabled or not self._worker.is_running:
            return
        if image is None or image.size == 0 or not boxes:
            return

        self._init_processors()

        # Crop regions
        crops = self._crop_processor.crop(image, boxes, mask)
        if not crops:
            return

        # Analyze direction
        layouts = self._layout_analyzer.analyze(boxes)
        dir_map = {l["id"]: l["direction"] for l in layouts}

        # Build regions for worker
        regions = []
        for crop in crops:
            rid = crop["id"]
            regions.append({
                "id": rid,
                "image": crop["image"],
                "box": crop["box"],
                "direction": dir_map.get(rid, "horizontal"),
            })

        self._worker.submit(regions)

    def get_filtered_results(self) -> list:
        """Return results above confidence threshold."""
        raw = self._worker.latest_results
        return [r for r in raw if r.get("confidence", 0) >= self._confidence_threshold]

    def clear_cache(self):
        self._cache.clear()