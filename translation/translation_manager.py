# -*- coding: utf-8 -*-
"""
NexaTrans - Translation Manager (Stage 6)
Orchestrates parallel translation with ThreadPoolExecutor + caching.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("NexaTrans.TranslationManager")


class TranslationManager:
    """Manages translation tasks with parallel execution and caching."""

    def __init__(self, client, cache=None, max_workers: int = 3):
        self._client = client
        self._cache = cache
        self._max_workers = max(1, min(max_workers, 6))
        self._target_lang = "zh"
        self._executor = None

    @property
    def target_language(self) -> str:
        return self._target_lang

    @target_language.setter
    def target_language(self, v: str):
        self._target_lang = v

    def translate_regions(self, ocr_results: list) -> list:
        """
        Translate multiple OCR results in parallel.

        Args:
            ocr_results: List of dicts from Stage 5:
                {"id": int, "text": str, "box": list, "confidence": float, ...}

        Returns:
            List of dicts with translation added:
                {"id": int, "text": str, "translation": str, "box": list, ...}
        """
        if not ocr_results or not self._client.is_configured:
            return ocr_results

        # Separate into cached vs needs-translation
        to_translate = []
        results = []

        for r in ocr_results:
            text = r.get("text", "").strip()
            if not text:
                results.append(r)
                continue

            # Check cache
            if self._cache:
                cached = self._cache.get(text, self._target_lang)
                if cached is not None:
                    r["translation"] = cached
                    r["cached_translation"] = True
                    results.append(r)
                    continue

            to_translate.append(r)

        if not to_translate:
            logger.debug(f"Translation: all {len(results)} cached")
            return results

        # Parallel translate
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

        futures = {}
        for r in to_translate:
            futures[self._executor.submit(
                self._translate_one, r["text"]
            )] = r

        for future in as_completed(futures):
            r = futures[future]
            try:
                result = future.result(timeout=20)
                r["translation"] = result.get("translation", "")
                r["translation_error"] = result.get("error")
                r["translation_time_ms"] = result.get("time_ms", 0)

                # Update cache
                if r["translation"] and self._cache:
                    self._cache.put(r["text"], self._target_lang, r["translation"])

            except Exception as e:
                logger.error(f"Translation future failed: {e}")
                r["translation"] = ""
                r["translation_error"] = str(e)

            results.append(r)

        logger.info(
            f"Translation: {len(ocr_results)} regions, "
            f"{len(to_translate)} translated, {len(ocr_results) - len(to_translate)} cached"
        )
        return results

    def _translate_one(self, text: str) -> dict:
        return self._client.translate(text, target=self._target_lang)

    def save_cache(self):
        if self._cache:
            self._cache.save()

    def shutdown(self):
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
