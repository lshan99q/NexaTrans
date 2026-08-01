# -*- coding: utf-8 -*-
"""
NexaTrans - Translation Cache (Stage 6)
MD5-based translation cache to avoid repeated API calls.
"""

import hashlib
import json
import os
import logging
from collections import OrderedDict

logger = logging.getLogger("NexaTrans.TranslationCache")

MAX_MEMORY_CACHE = 128


class TranslationCache:
    """In-memory + optional JSON-file translation cache."""

    def __init__(self, file_path: str = None):
        self._file_path = file_path
        self._memory = OrderedDict()
        self._load()

    def _compute_key(self, text: str, target: str) -> str:
        raw = f"{text.strip()}|{target}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def get(self, text: str, target: str = "zh") -> str | None:
        key = self._compute_key(text, target)
        if key in self._memory:
            self._memory.move_to_end(key)
            return self._memory[key]
        return None

    def put(self, text: str, target: str, translation: str):
        key = self._compute_key(text, target)
        self._memory[key] = translation
        self._memory.move_to_end(key)
        if len(self._memory) > MAX_MEMORY_CACHE:
            self._memory.popitem(last=False)

    def _load(self):
        if not self._file_path or not os.path.exists(self._file_path):
            return
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                key = entry.get("key", "")
                translation = entry.get("translation", "")
                if key and translation:
                    self._memory[key] = translation
            logger.info(f"Loaded {len(self._memory)} cached translations")
        except Exception as e:
            logger.warning(f"Failed to load translation cache: {e}")

    def save(self):
        if not self._file_path:
            return
        try:
            data = [
                {"key": k, "translation": v}
                for k, v in self._memory.items()
            ]
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save translation cache: {e}")

    def clear(self):
        self._memory.clear()
