"""
NexaTrans - OCR Worker Thread (Stage 5)
Asynchronous OCR processing to avoid blocking the main UI thread.
Uses QThread + signal/slot for thread-safe result delivery.
"""

import logging
import hashlib
import time
import numpy as np
from collections import OrderedDict
from PySide6.QtCore import QThread, Signal, QMutex, QMutexLocker

logger = logging.getLogger("NexaTrans.OCRWorker")

MAX_CACHE_SIZE = 64


class OCRWorker(QThread):
    """Background worker for OCR recognition."""

    result_ready = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._engine = None
        self._pending = []
        self._mutex = QMutex()
        self._running = False
        self._cache = OrderedDict()
        self._min_conf = 0.7
        self._lang = "ch"

    def set_engine(self, engine):
        self._engine = engine

    @property
    def min_confidence(self) -> float:
        return self._min_conf

    @min_confidence.setter
    def min_confidence(self, v: float):
        self._min_conf = max(0.0, min(v, 1.0))

    @property
    def lang(self) -> str:
        return self._lang

    @lang.setter
    def lang(self, v: str):
        self._lang = v

    def update_regions(self, regions: list):
        """
        Update pending OCR regions. Called from main thread.

        Args:
            regions: List of dicts:
                {"id": int, "image": ndarray, "box": list, "direction": str}
        """
        with QMutexLocker(self._mutex):
            self._pending = regions

    def stop(self):
        self._running = False

    def run(self):
        """Main OCR processing loop."""
        self._running = True
        while self._running:
            regions = None
            with QMutexLocker(self._mutex):
                if self._pending:
                    regions = self._pending
                    self._pending = []

            if regions:
                results = self._process(regions)
                if results:
                    self.result_ready.emit(results)

            self.msleep(20)

        logger.info("OCR worker stopped")

    def _process(self, regions: list) -> list:
        if not self._engine or not self._engine.is_loaded:
            return []

        results = []
        for region in regions:
            try:
                img = region.get("image")
                if img is None or img.size == 0:
                    continue

                img_hash = self._compute_hash(img)
                if img_hash in self._cache:
                    cached = self._cache[img_hash]
                    cached["id"] = region.get("id")
                    cached["box"] = region.get("box")
                    cached["direction"] = region.get("direction", "horizontal")
                    cached["cached"] = True
                    results.append(cached)
                    continue

                t0 = time.time()
                enhanced = self._engine.preprocess(img)
                rec_result = self._engine.recognize(enhanced)

                if rec_result["confidence"] >= self._min_conf:
                    entry = {
                        "id": region.get("id"),
                        "box": region.get("box"),
                        "direction": region.get("direction", "horizontal"),
                        "text": rec_result["text"],
                        "confidence": rec_result["confidence"],
                        "cached": False,
                        "time_ms": (time.time() - t0) * 1000,
                    }
                    results.append(entry)

                    self._cache[img_hash] = dict(entry)
                    if len(self._cache) > MAX_CACHE_SIZE:
                        self._cache.popitem(last=False)

                    logger.debug(
                        f"OCR region {region.get('id')}: "
                        f"'{rec_result['text']}' "
                        f"({rec_result['confidence']:.2f}) "
                        f"in {entry['time_ms']:.1f}ms"
                    )

            except Exception as e:
                logger.error(f"OCR process error: {e}", exc_info=True)

        return results

    @staticmethod
    def _compute_hash(img: np.ndarray) -> str:
        try:
            return hashlib.md5(img.tobytes()).hexdigest()
        except Exception:
            return ""
