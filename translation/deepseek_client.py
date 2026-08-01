# -*- coding: utf-8 -*-
"""
NexaTrans - DeepSeek Client (Stage 6)
DeepSeek Chat API wrapper for game text translation.
Loads API key from .env file automatically.
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger("NexaTrans.DeepSeek")

SYSTEM_PROMPT = (
    "你是一个专业游戏翻译助手。请将以下文本翻译成简体中文。"
    "要求：1.保留人物语气 2.不增加解释 3.不改变专有名词 4.只输出译文"
)


def _load_env():
    """Load .env file from project root."""
    env = {}
    candidates = []
    # Try project root
    _frozen = getattr(sys, "frozen", False)
    cur = os.path.dirname(sys.executable) if _frozen else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(cur, ".env"))
    # Try current directory
    candidates.append(".env")
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, _, val = line.partition("=")
                            key = key.strip()
                            val = val.strip().strip("\"'")
                            env[key] = val
                logger.info(f"Loaded .env from {path}")
                break
            except Exception:
                pass
    return env


class DeepSeekClient:
    """DeepSeek Chat API client for translation."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = "deepseek-chat"):
        env = _load_env()
        self._api_key = api_key or env.get("DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
        self._base_url = base_url or env.get("DEEPSEEK_BASE_URL") or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self._model = model
        self._endpoint = f"{self._base_url}/v1/chat/completions"
        self._timeout = 15

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def translate(self, text: str, source: str = "auto", target: str = "zh") -> dict:
        if not text or not text.strip():
            return {"translation": "", "error": "Empty text", "time_ms": 0}
        if not self._api_key:
            return {"translation": "", "error": "No API key configured", "time_ms": 0}

        import time
        t0 = time.time()

        try:
            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text.strip()},
                ],
                "temperature": 0.3,
                "max_tokens": 256,
                "stream": False,
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self._endpoint,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            elapsed = (time.time() - t0) * 1000
            if "choices" in body and len(body["choices"]) > 0:
                translation = body["choices"][0]["message"]["content"].strip()
                return {"translation": translation, "error": None, "time_ms": elapsed}
            else:
                return {"translation": "", "error": "No response from API", "time_ms": elapsed}

        except urllib.error.HTTPError as e:
            elapsed = (time.time() - t0) * 1000
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            logger.error(f"DeepSeek HTTP {e.code}: {err_body}")
            return {"translation": "", "error": f"HTTP {e.code}", "time_ms": elapsed}
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            logger.error(f"DeepSeek error: {e}")
            return {"translation": "", "error": str(e), "time_ms": elapsed}
