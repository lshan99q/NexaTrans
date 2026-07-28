"""
NexaTrans - OCR Worker (Stage 5)
Async worker thread for OCR processing. Uses queue to receive tasks,
processes them off the main thread, and emits results via callback.
"""

import logging
import queue
import threading
import time
import numpy as np

logger = logging.getLogger("NexaTrans.OCR.Worker")


class OCRWorker:
    """Background thread for async OCR processing."""

    def __init__(self, engine, preprocessor, cache, on_result=None):
        self._engine = engine
        self._preprocessor = preprocessor
        self._cache = cache
        self._on_result = on_result  # callable(result_dict)
        self._queue = queue.Queue(maxsize=50)
        self._thread = None
        self._running = False
        self._results = []  # latest results for main thread to read
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def latest_results(self) -> list:
        with self._lock:
            return list(self._results)

    def submit(self, regions: list):
        """Submit text regions for OCR. Each region: {"id": int, "image": ndarray, "box": list, "direction": str}."""
        if not self._running:
            return
        try:
            self._queue.put_nowait(regions)
        except queue.Full:
            logger.debug("OCR queue full, dropping frame")

    def start(self):
        if self._running:
            return
        if not self._engine.is_loaded:
            self._engine.load()
        if not self._engine.is_loaded:
            logger.error("OCR engine not loaded, worker cannot start")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="OCRWorker")
        self._thread.start()
        logger.info("OCR worker started")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("OCR worker stopped")

    def _loop(self):
        while self._running:
            try:
                regions = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            results = []
            for region in regions:
                img = region.get("image")
                if img is None or img.size == 0:
                    continue

                rid = region.get("id", 0)
                direction = region.get("direction", "horizontal")
                box = region.get("box", [])

                # Handle vertical text: rotate 90 degrees
                if direction == "vertical" and img.shape[1] > img.shape[0]:
                    try:
                        import cv2
                        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                    except Exception:
                        pass

                # Preprocess
                processed = self._preprocessor.process(img)

                # Check cache
                cached = self._cache.get(processed) if self._cache else None
                if cached:
                    results.append({
                        "id": rid,
                        "text": cached["text"],
                        "confidence": cached["confidence"],
                        "direction": direction,
                        "box": box,
                        "cached": True,
                    })
                    continue

                # OCR
                t0 = time.time()
                ocr_result = self._engine.recognize(processed)
                elapsed = (time.time() - t0) * 1000

                result = {
                    "id": rid,
                    "text": ocr_result.get("text", ""),
                    "confidence": ocr_result.get("confidence", 0.0),
                    "direction": direction,
                    "box": box,
                    "cached": False,
                    "elapsed_ms": round(elapsed, 1),
                }
                results.append(result)

                # Cache if confidence is reasonable
                if self._cache and result["confidence"] > 0.5:
                    self._cache.put(processed, result)

            # Update latest results
            with self._lock:
                self._results = results

            # Callback
            if self._on_result and results:
                try:
                    self._on_result(results)
                except Exception as e:
                    logger.error(f"OCR callback error: {e}")