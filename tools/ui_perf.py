# -*- coding: utf-8 -*-
"""
NexaTrans - GUI responsiveness probe.

Measures how long the Qt event loop is blocked (the freeze the user feels)
while the AI models load and while the detection pipeline is running, using a
10 ms heartbeat timer: the largest gap between two heartbeats is the worst
stall on the GUI thread.

Runs headless (offscreen) and uses the real DBNet / PaddleOCR models if they
are available in the PaddleX cache.

Usage:
    python tools/ui_perf.py [seconds] [--force-change]

``--force-change`` defeats the frame-diff optimisation so that every tick runs
real detection + OCR, reproducing the worst case (scrolling game content).
"""

import os
import statistics
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6.QtCore import QTimer                                   # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402

from config.config_manager import ConfigManager                     # noqa: E402
from ui.main_window import MainWindow                               # noqa: E402
from ui.theme import MODE_DARK, apply_app_theme                     # noqa: E402

LOAD_TIMEOUT = 180.0
HEARTBEAT_MS = 10


class Heartbeat:
    """Records the gap between successive event-loop timer callbacks."""

    def __init__(self, app: QApplication):
        self._app = app
        self._last = time.time()
        self.gaps: list[float] = []
        self._timer = QTimer()
        self._timer.setInterval(HEARTBEAT_MS)
        self._timer.timeout.connect(self._beat)

    def _beat(self):
        now = time.time()
        self.gaps.append(now - self._last)
        self._last = now

    def start(self):
        self.gaps.clear()
        self._last = time.time()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def pump(self, seconds: float) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline:
            self._app.processEvents()
            time.sleep(0.001)

    # -- statistics -----------------------------------------------------

    def worst(self) -> float:
        return max(self.gaps) if self.gaps else 0.0

    def median(self) -> float:
        return statistics.median(self.gaps) if self.gaps else 0.0


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    force_change = "--force-change" in sys.argv
    run_seconds = float(args[0]) if args else 6.0

    app = QApplication(sys.argv)
    apply_app_theme(app, MODE_DARK)

    tmp = tempfile.mkdtemp(prefix="nexatrans-perf-")
    config = ConfigManager(config_path=os.path.join(tmp, "settings.json"))
    config.save_region({"x": 0, "y": 0, "width": 640, "height": 200})
    ui = config.get_ui_config()
    ui.update({"show_mask": False, "show_boxes": True, "show_ocr": True,
               "show_translation": True, "fps_target": 10})
    config.save_ui_config(ui)

    window = MainWindow(config)
    window.show()

    beat = Heartbeat(app)
    beat.start()
    beat.pump(0.8)
    print(f"idle baseline      : worst stall {beat.worst() * 1000:7.1f} ms "
          f"({len(beat.gaps)} heartbeats)")

    # ---- 1. model loading ------------------------------------------
    beat.start()
    began = time.time()
    window.start_btn.click()
    while window._pipeline is None and time.time() - began < LOAD_TIMEOUT:
        beat.pump(0.05)
    load_elapsed = time.time() - began
    beat.pump(0.4)

    if window._pipeline is None:
        print(f"model load FAILED after {load_elapsed:.1f}s "
              f"(status: {window.status_badge._text})")
        return 2

    detector = window._pipeline.detector
    print(f"model load         : {load_elapsed:5.1f} s wall clock, "
          f"worst GUI stall {beat.worst() * 1000:7.1f} ms")
    print(f"  detector loaded  : {getattr(detector, 'is_loaded', False)}")
    print(f"  OCR engine       : {window._pipeline._ocr_engine is not None}")

    # ---- 2. running the pipeline -----------------------------------
    if force_change:
        # defeat the frame-diff optimisation so every tick runs real
        # detection + OCR, which is what happens on scrolling game content
        window._pipeline._frame_changed = lambda img: True
        print("  (frame-diff disabled: every tick runs detection + OCR)")

    if "--profile" in sys.argv:
        stage_times = {"detect": [], "ocr": [], "mask": []}
        detector = window._pipeline.detector
        original_detect = detector.detect

        def timed_detect(img, _t=original_detect, _s=stage_times):
            began_stage = time.time()
            out = _t(img)
            _s["detect"].append(time.time() - began_stage)
            return out

        detector.detect = timed_detect

        original_ocr = window._pipeline._run_ocr

        def timed_ocr(img, boxes, region, _f=original_ocr, _s=stage_times):
            began_stage = time.time()
            out = _f(img, boxes, region)
            _s["ocr"].append(time.time() - began_stage)
            return out

        window._pipeline._run_ocr = timed_ocr
        original_mask = window._pipeline._build_mask

        def timed_mask(boxes, region, img, _f=original_mask, _s=stage_times):
            began_stage = time.time()
            out = _f(boxes, region, img)
            _s["mask"].append(time.time() - began_stage)
            return out

        window._pipeline._build_mask = timed_mask

    beat.start()
    print(f"\nrunning for {run_seconds:.0f}s ...")
    beat.pump(run_seconds)
    beat.stop()

    gaps = beat.gaps
    over_100 = sum(1 for g in gaps if g > 0.1)
    print(f"pipeline running   : worst GUI stall {beat.worst() * 1000:7.1f} ms, "
          f"median {beat.median() * 1000:5.1f} ms")
    print(f"  heartbeats       : {len(gaps)} "
          f"(expected ~{run_seconds / (HEARTBEAT_MS / 1000):.0f})")
    print(f"  stalls > 100 ms  : {over_100} "
          f"({over_100 / max(1, len(gaps)) * 100:.0f}% of heartbeats)")
    print(f"  pipeline FPS     : {window._pipeline.fps:.1f}")

    if "--profile" in sys.argv:
        print("\nper-stage cost on the GUI thread")
        print(f"  {'stage':<8} {'calls':>6} {'total ms':>10} {'mean ms':>9} "
              f"{'max ms':>8}")
        for stage, samples in stage_times.items():
            if not samples:
                print(f"  {stage:<8} {0:>6} {'-':>10} {'-':>9} {'-':>8}")
                continue
            total = sum(samples) * 1000
            print(f"  {stage:<8} {len(samples):>6} {total:>10.0f} "
                  f"{total / len(samples):>9.1f} {max(samples) * 1000:>8.1f}")

    window._stop_all()
    beat.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
