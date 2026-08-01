with open("detection/detection_pipeline.py", "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace("        self._trans_pending = False", "        self._trans_pending = False\n        self._trans_count = 0")

new_method = """
    def set_fps(self, fps: int):
        self._interval = int(1000 / max(fps, 1))
        if self._running:
            self._timer.setInterval(self._interval)
        logger.info(f"FPS target set to {fps}")

    @property
    def trans_count(self) -> int:
        return self._trans_count

    def start"""

c = c.replace("    def start(", new_method)

c = c.replace(
    'logger.info(f"Translation complete: {len(translated)} results")',
    'self._trans_count += 1\n                logger.info(f"Translation complete: {len(translated)} results")'
)

c = c.replace(
    "        self._trans_pending = False\n        if self._trans_cache",
    "        self._trans_pending = False\n        self._trans_count = 0\n        if self._trans_cache"
)

with open("detection/detection_pipeline.py", "w", encoding="utf-8") as f:
    f.write(c)
print("OK")
