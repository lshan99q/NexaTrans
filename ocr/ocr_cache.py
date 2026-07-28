"""
NexaTrans - OCR Cache (Stage 5)
MD5-based caching to avoid redundant OCR on identical text regions.
"""

import hashlib
import logging
import time
import numpy as np

logger = logging.getLogger("NexaTrans.OCR.Cache")


class OCRCache:
    """MD5 hash-based cache for OCR results."""

    def __init__(self, max_size: int = 500):
        self._cache = {}  # hash -> {"text", "confidence", "timestamp"}
        self._max = max_size

    def _hash(self, image: np.ndarray) -> str:
        """Compute MD5 hash of image data."""
        data = image.tobytes()
        return hashlib.md5(data).hexdigest()

    def get(self, image: np.ndarray) -> dict | None:
        """Return cached result or None."""
        key = self._hash(image)
        if key in self._cache:
            logger.debug(f"Cache hit: {key[:8]}...")
            return dict(self._cache[key])
        return None

    def put(self, image: np.ndarray, result: dict):
        """Store result in cache."""
        key = self._hash(image)
        result["timestamp"] = time.time()
        self._cache[key] = dict(result)
        logger.debug(f"Cache stored: {key[:8]}...")

        # Evict oldest if over max
        if len(self._cache) > self._max:
            oldest = min(self._cache, key=lambda k: self._cache[k].get("timestamp", 0))
            del self._cache[oldest]

    def clear(self):
        self._cache.clear()
        logger.info("OCR cache cleared")

    def __len__(self):
        return len(self._cache)