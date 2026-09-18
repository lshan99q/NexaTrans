# -*- coding: utf-8 -*-
"""
NexaTrans - OCR + translation pipeline check.

Runs the real OCR engine and the real DeepSeek client against a synthetic
image, so a "recognises but does not translate" report can be diagnosed
without a game window.  It exercises exactly the code path used by
one-shot translation: filter -> crop -> OCR -> translate.

NOTE: this makes **one small API request** with the key from .env.

Usage:
    python tools/pipeline_check.py
"""

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import cv2                                                          # noqa: E402
import numpy as np                                                  # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402

import detection.detection_pipeline as dp                           # noqa: E402
from config.config_manager import ConfigManager                     # noqa: E402


class StubDetector:
    """Returns one box around the text we draw, so no models are needed."""

    is_loaded = True
    BOX = [[10, 40, 250, 40, 250, 85, 10, 85]]

    def detect(self, img):
        return {"boxes": [list(b) for b in self.BOX], "scores": [0.97]}


def main() -> int:
    app = QApplication(sys.argv)                                    # noqa: F841

    # synthetic "screen": black text on white
    image = np.full((120, 400, 3), 255, np.uint8)
    cv2.putText(image, "Start Game", (14, 74), cv2.FONT_HERSHEY_SIMPLEX,
                1.5, (0, 0, 0), 3, cv2.LINE_AA)
    dp.capture_region = lambda region: image

    tmp = tempfile.mkdtemp(prefix="nexatrans-check-")
    config = ConfigManager(config_path=os.path.join(tmp, "settings.json"))
    config.save_region({"x": 0, "y": 0, "width": 400, "height": 120})

    from ocr.paddleocr_engine import PaddleOCREngine
    print("loading OCR engine ...")
    ocr = PaddleOCREngine(lang="ch")
    print(f"  OCR loaded: {ocr.is_loaded}")

    pipeline = dp.DetectionPipeline(config, detector=StubDetector(),
                                    ocr_engine=ocr)
    pipeline.ocr_enabled = True
    pipeline.trans_enabled = True

    print(f"  translation_ready: {pipeline.translation_ready}")
    if not pipeline.translation_ready:
        print("\n=> FAIL: no usable DeepSeek client."
              " Check DEEPSEEK_API_KEY in .env (Settings -> DeepSeek API).")
        return 2

    print("running capture_once (this makes one API request) ...")
    result = pipeline.capture_once()
    if result is None:
        print("\n=> FAIL: capture_once returned None")
        return 3

    boxes = result.get("boxes") or []
    ocr_results = result.get("ocr") or []
    trans = result.get("trans") or []
    print(f"  boxes : {len(boxes)}")
    print(f"  ocr   : {[r.get('text') for r in ocr_results]}")
    print(f"  trans : {[r.get('translation') for r in trans]}")

    pipeline.cleanup()

    if ocr_results and trans:
        print("\n=> OK: recognition and translation both work.")
        return 0
    if ocr_results and not trans:
        print("\n=> FAIL: recognised text but produced no translation.")
        return 4
    print("\n=> FAIL: nothing recognised at all (OCR/model problem).")
    return 5


if __name__ == "__main__":
    sys.exit(main())
