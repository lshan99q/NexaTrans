"""
NexaTrans - Detection Pipeline
Orchestrates the screenshot -> DBNet++ detection -> overlay loop.
Handles DPI scaling: screenshots in physical pixels, overlay in logical coords.
Converts tilted DBNet polygons to horizontal axis-aligned rectangles.
"""

import logging
import time
from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QApplication

from screen.screenshot import capture_region
from detection.dbnet_detector import DBNetDetector
from overlay.text_overlay import TextOverlay

logger = logging.getLogger("NexaTrans.DetectionPipeline")


class DetectionPipeline(QObject):
    """Runs the real-time text detection loop."""

    def __init__(self, config_manager, target_fps: int = 15, limit_side_len: int = 960):
        super().__init__()
        self._config = config_manager
        self._detector = DBNetDetector(limit_side_len=limit_side_len)
        self._overlay = TextOverlay()
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._running = False
        self._busy = False
        self._target_interval = int(1000 / max(target_fps, 1))
        self._frame_count = 0
        self._last_fps_time = time.time()
        self._fps = 0.0
        self._last_region = None
        self._dpr = 1.0

        logger.info(
            f"Detection pipeline initialized "
            f"(target={target_fps} FPS, limit={limit_side_len}px)"
        )

    @property
    def detector(self) -> DBNetDetector:
        return self._detector

    @property
    def overlay(self) -> TextOverlay:
        return self._overlay

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def fps(self) -> float:
        return self._fps

    def _get_dpr(self) -> float:
        """Get device pixel ratio from primary screen."""
        try:
            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    return screen.devicePixelRatio()
        except Exception:
            pass
        return 1.0

    @staticmethod
    def _polygon_to_rect(box: list) -> list:
        """
        Convert a 4-point polygon [x1,y1, x2,y2, x3,y3, x4,y4]
        to an axis-aligned horizontal rectangle [min_x,min_y, max_x,min_y, max_x,max_y, min_x,max_y].
        """
        if len(box) < 8:
            return box

        xs = [box[i] for i in range(0, len(box), 2)]
        ys = [box[i + 1] for i in range(0, len(box), 2)]

        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        return [min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y]

    def start(self):
        """Start the detection loop."""
        if not self._detector.is_loaded:
            logger.error("Cannot start: DBNet++ model not loaded")
            return False

        if self._running:
            return True

        self._running = True
        self._busy = False
        self._last_region = None
        self._frame_count = 0
        self._last_fps_time = time.time()
        self._dpr = self._get_dpr()

        region = self._config.load_region()
        self._overlay.update_region(region)

        self._overlay.show_overlay()
        self._timer.start(self._target_interval)
        logger.info(
            f"Detection pipeline started "
            f"(DPR={self._dpr}, {1000 // self._target_interval} FPS target)"
        )
        return True

    def stop(self):
        """Stop the detection loop."""
        self._running = False
        self._timer.stop()
        self._overlay.hide_overlay()
        logger.info("Detection pipeline stopped")

    def _tick(self):
        """One detection frame."""
        if self._busy:
            return

        self._busy = True

        try:
            region = self._config.load_region()

            if self._last_region != region:
                self._overlay.update_region(region)
                self._last_region = dict(region)

            # Screenshot captures at physical pixels
            image = capture_region(region)
            if image.size == 0:
                self._busy = False
                return

            # Detection boxes in physical pixels (may be tilted polygons)
            physical_boxes = self._detector.detect(image)

            # Convert: physical -> logical -> horizontal rectangle
            dpr = self._dpr
            logical_boxes = []
            for box in physical_boxes:
                # Step 1: physical -> logical
                logical_box = [int(round(c / dpr)) for c in box]
                # Step 2: tilted polygon -> horizontal rectangle
                rect = self._polygon_to_rect(logical_box)
                logical_boxes.append(rect)

            if logical_boxes:
                logger.debug(
                    f"Detected {len(logical_boxes)} boxes "
                    f"(first: [{logical_boxes[0][0]},{logical_boxes[0][1]}...], DPR={dpr})"
                )

            self._overlay.update_boxes(logical_boxes)

            self._frame_count += 1
            now = time.time()
            elapsed = now - self._last_fps_time
            if elapsed >= 1.0:
                self._fps = self._frame_count / elapsed
                self._frame_count = 0
                self._last_fps_time = now

        except Exception as e:
            logger.error(f"Detection tick failed: {e}", exc_info=True)
        finally:
            self._busy = False

    def cleanup(self):
        """Clean up resources."""
        self.stop()
        self._overlay.close()
        logger.info("Detection pipeline cleaned up")
