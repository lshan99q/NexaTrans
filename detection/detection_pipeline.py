"""
NexaTrans - Detection Pipeline v0.4.4

Both modes use proper frame-diff to detect content changes:
- Normal mode: capture (thin green lines negligible) -> diff -> detect if changed
- Mask mode: clean capture (brief setVisible) -> diff -> detect ONLY if changed -> render cached mask
- Mask toggle ON: generate mask from cached detection (no hide/show needed!)
"""

import logging, time, ctypes, numpy as np, cv2
from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QApplication
from screen.screenshot import capture_region
from detection.dbnet_detector import DBNetDetector
from overlay.text_overlay import TextOverlay

logger = logging.getLogger("NexaTrans.DetectionPipeline")


class DetectionPipeline(QObject):

    def __init__(self, config_manager, target_fps=15, limit_side_len=960):
        super().__init__()
        self._config = config_manager
        self._detector = DBNetDetector(limit_side_len=limit_side_len)
        self._overlay = TextOverlay()
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._running = False
        self._busy = False
        self._show_mask = False
        self._mask_gen = None
        self._mask_ref = None
        self._interval = int(1000 / max(target_fps, 1))
        self._frame_count = 0
        self._last_fps = time.time()
        self._fps = 0.0
        self._last_region = None
        self._dpr = 1.0
        self._prev_image = None
        self._prev_boxes = None
        self._prev_mask = None
        self._prev_colors = None
        self._sent_boxes = None
        self._sent_has_mask = None
        self._diff_thresh = 0.008
        self._tick_count = 0
        logger.info(f"Pipeline v0.4.4 ready (target={target_fps}FPS)")

    # ── properties ──────────────────────────────────────────────
    @property
    def detector(self): return self._detector
    @property
    def overlay(self): return self._overlay
    @property
    def is_running(self): return self._running
    @property
    def fps(self): return self._fps
    @property
    def show_mask(self): return self._show_mask

    @show_mask.setter
    def show_mask(self, v: bool):
        if v == self._show_mask:
            return
        logger.info(f"Mask toggle: {self._show_mask} -> {v}")
        self._show_mask = v

        if v:
            self._init_mask()
            self._generate_mask_from_cache()
        else:
            self._prev_mask = None
            self._prev_colors = None
            boxes = self._prev_boxes if self._prev_boxes else []
            self._overlay.set_data(boxes, None, None)
            self._overlay.repaint()
            QApplication.processEvents()
            self._sent_boxes = list(boxes) if boxes else None
            self._sent_has_mask = False
            self._prev_image = None
            self._tick_count = 0

    # ── init ────────────────────────────────────────────────────
    def _init_mask(self):
        if self._mask_gen:
            return
        try:
            from text_processing.mask_generator import MaskGenerator
            from text_processing.mask_refiner import MaskRefiner
            tp = self._config.get_text_processing_config()
            self._mask_gen = MaskGenerator()
            self._mask_ref = MaskRefiner(tp["dilate_size"], tp["blur_size"])
            logger.info("Mask modules loaded")
        except Exception as e:
            logger.error(f"Mask init failed: {e}")

    def _dpr_get(self):
        try:
            a = QApplication.instance()
            if a and a.primaryScreen():
                return a.primaryScreen().devicePixelRatio()
        except Exception:
            pass
        return 1.0

    # ── helpers ─────────────────────────────────────────────────
    @staticmethod
    def _to_rect(b):
        if len(b) < 8:
            return b
        xs = [b[i] for i in range(0, len(b), 2)]
        ys = [b[i + 1] for i in range(0, len(b), 2)]
        return [min(xs), min(ys), max(xs), min(ys), max(xs), max(ys), min(xs), max(ys)]

    @staticmethod
    def _bg_color(img, box, margin=3):
        h, w = img.shape[:2]
        xs = [box[i] for i in range(0, len(box), 2)]
        ys = [box[i + 1] for i in range(0, len(box), 2)]
        x1, y1 = max(0, min(xs)), max(0, min(ys))
        x2, y2 = min(w, max(xs)), min(h, max(ys))
        px = []
        m = margin
        for sx in range(x1, x2):
            if 0 <= y1 - m < h:
                px.append(img[y1 - m, sx])
            if 0 <= y2 + m < h:
                px.append(img[y2 + m, sx])
        for sy in range(y1, y2):
            if 0 <= x1 - m < w:
                px.append(img[sy, x1 - m])
            if 0 <= x2 + m < w:
                px.append(img[sy, x2 + m])
        if px:
            return tuple(int(c) for c in np.median(np.array(px, np.float32), 0).astype(np.uint8))
        return (128, 128, 128)

    def _filter(self, boxes, scores, rw, rh):
        tp = self._config.get_text_processing_config()
        mc = tp.get("min_confidence", 0.5)
        ma = tp.get("min_text_aspect", 1.8)
        mi = tp.get("max_icon_aspect", 1.4)
        mr = tp.get("min_area_ratio", 0.005)
        ra = rw * rh
        out_b = []
        icon_count = conf_count = size_count = 0
        for b, s in zip(boxes, scores):
            xs = [b[i] for i in range(0, len(b), 2)]
            ys = [b[i + 1] for i in range(0, len(b), 2)]
            bw, bh = max(xs) - min(xs), max(ys) - min(ys)
            if bw <= 0 or bh <= 0:
                size_count += 1; continue
            if bw * bh < ra * mr:
                size_count += 1; continue
            if s < mc:
                conf_count += 1; continue
            asp = bw / max(bh, 1)
            if 1 / mi <= asp <= mi and s < 0.85:
                icon_count += 1; continue
            out_b.append(b)
        if icon_count or conf_count or size_count:
            logger.debug(
                f"Filtered: icons={icon_count}, conf={conf_count}, "
                f"size={size_count} ({len(boxes)}->{len(out_b)})"
            )
        return out_b

    def _run_detect(self, img, region):
        """Run DBNet detection + mask generation on a clean image."""
        r = self._detector.detect(img)
        pb = r.get("boxes", [])
        ss = r.get("scores", [])
        dpr = self._dpr
        lb = [self._to_rect([int(round(c / dpr)) for c in b]) for b in pb]
        if lb and ss:
            lb = self._filter(lb, ss, region["width"], region["height"])
        self._prev_boxes = lb

        if self._show_mask and lb:
            self._build_mask(lb, region, img)
        else:
            self._prev_mask = None
            self._prev_colors = None

    def _build_mask(self, boxes, region, img):
        """Generate mask + sample colors from boxes and image."""
        h_l, w_l = region["height"], region["width"]
        if self._mask_gen and self._mask_ref:
            mk = self._mask_gen.generate((h_l, w_l), boxes)
            self._prev_mask = self._mask_ref.refine(mk)
        else:
            self._prev_mask = np.zeros((h_l, w_l), np.uint8)
            for b in boxes:
                xs = [b[i] for i in range(0, len(b), 2)]
                ys = [b[i + 1] for i in range(0, len(b), 2)]
                cv2.fillPoly(self._prev_mask,
                    [np.array([[min(xs), min(ys)], [max(xs), min(ys)],
                               [max(xs), max(ys)], [min(xs), max(ys)]], np.int32)], 255)
        img_resized = cv2.resize(img, (w_l, h_l))
        self._prev_colors = [self._bg_color(img_resized, b) for b in boxes]

    def _generate_mask_from_cache(self):
        """Generate mask from cached detection results. NO hide/show!"""
        if not self._prev_boxes or self._prev_image is None:
            logger.warning("No cached detection to generate mask from")
            return
        region = self._config.load_region()
        self._build_mask(self._prev_boxes, region, self._prev_image)
        boxes = self._prev_boxes
        self._overlay.set_data(boxes, self._prev_mask, self._prev_colors)
        self._overlay.repaint()
        QApplication.processEvents()
        self._sent_boxes = list(boxes)
        self._sent_has_mask = True
        logger.info(f"Mask generated from cache: {len(boxes)} boxes")

    def _frame_diff(self, img):
        """Compare img with previous clean frame. Returns True if changed."""
        if self._prev_image is None:
            return True
        if self._prev_image.shape != img.shape:
            return True
        d = np.mean(np.abs(img.astype(np.int16) - self._prev_image.astype(np.int16))) / 255.0
        return d >= self._diff_thresh

    # ── start / stop ────────────────────────────────────────────
    def start(self):
        if not self._detector.is_loaded:
            return False
        if self._running:
            return True
        self._running = True
        self._busy = False
        self._last_region = None
        self._prev_image = None
        self._prev_boxes = None
        self._prev_mask = None
        self._prev_colors = None
        self._sent_boxes = None
        self._sent_has_mask = None
        self._tick_count = 0
        self._frame_count = 0
        self._last_fps = time.time()
        self._dpr = self._dpr_get()
        region = self._config.load_region()
        self._overlay.update_region(region)
        self._last_region = dict(region)
        self._overlay.show_overlay()
        self._timer.start(self._interval)
        logger.info(f"Started (DPR={self._dpr})")
        return True

    def stop(self):
        self._running = False
        self._timer.stop()
        self._overlay.hide_overlay()
        self._prev_image = None
        logger.info("Stopped")

    # ── main tick ───────────────────────────────────────────────
    def _tick(self):
        if self._busy or not self._running:
            return
        self._busy = True
        try:
            region = self._config.load_region()
            if self._last_region != region:
                self._overlay.update_region(region)
                self._last_region = dict(region)
                self._prev_image = None
                self._sent_boxes = None
                self._sent_has_mask = None

            self._tick_count += 1

            if self._show_mask:
                self._tick_mask_mode(region)
            else:
                self._tick_normal_mode(region)

            self._frame_count += 1
            now = time.time()
            if now - self._last_fps >= 1.0:
                self._fps = self._frame_count / (now - self._last_fps)
                self._frame_count = 0
                self._last_fps = now
        except Exception as e:
            logger.error(f"Tick: {e}", exc_info=True)
        finally:
            self._busy = False

    # ── normal mode (mask OFF) ──────────────────────────────────
    def _tick_normal_mode(self, region):
        """Capture directly (green lines negligible), frame-diff, detect if changed."""
        img = capture_region(region)
        if img.size == 0:
            return

        if self._frame_diff(img):
            self._prev_image = img.copy()
            self._run_detect(img, region)

        boxes = self._prev_boxes if self._prev_boxes else []
        if boxes != self._sent_boxes or self._sent_has_mask:
            self._overlay.set_data(boxes, None, None)
            self._sent_boxes = list(boxes) if boxes else None
            self._sent_has_mask = False

    # ── mask mode (mask ON) ─────────────────────────────────────
    def _tick_mask_mode(self, region):
        """Clean capture for frame-diff. Re-detect ONLY if content changed.
        Always render cached mask data - no flicker from re-rendering."""
        # Clean capture for frame-diff (brief setVisible toggle)
        self._overlay.setVisible(False)
        QApplication.processEvents()
        img = capture_region(region)
        self._overlay.setVisible(True)

        if img.size == 0:
            return

        # Frame-diff: only re-detect if game content actually changed
        if self._frame_diff(img):
            self._prev_image = img.copy()
            self._run_detect(img, region)

        # Always render cached data (stable, no flicker)
        boxes = self._prev_boxes if self._prev_boxes else []
        has_mask = self._prev_mask is not None

        if boxes != self._sent_boxes or has_mask != self._sent_has_mask:
            if has_mask:
                self._overlay.set_data(boxes, self._prev_mask, self._prev_colors)
            else:
                self._overlay.set_data(boxes, None, None)
            self._sent_boxes = list(boxes) if boxes else None
            self._sent_has_mask = has_mask

    # ── cleanup ─────────────────────────────────────────────────
    def cleanup(self):
        self.stop()
        self._overlay.close()