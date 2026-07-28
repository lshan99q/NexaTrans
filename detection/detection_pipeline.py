"""
NexaTrans - Detection Pipeline v0.4.10

Normal mode: capture directly (green lines fine), diff, detect, render.
Mask mode: capture WITH mask (for diff), only clean-capture when changed.
Overlay never hides during normal ticks - only briefly for clean detection.
"""

import logging, time, ctypes, numpy as np, cv2
from PySide6.QtCore import QTimer, QObject
from PySide6.QtWidgets import QApplication
from screen.screenshot import capture_region
from detection.dbnet_detector import DBNetDetector
from ocr.ocr_manager import OCRManager
from overlay.text_overlay import TextOverlay

logger = logging.getLogger("NexaTrans.DetectionPipeline")

user32 = ctypes.windll.user32


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
        self._prev_frame = None
        self._prev_boxes = None
        self._prev_mask = None
        self._prev_colors = None
        self._sent_boxes = None
        self._sent_has_mask = None
        self._diff_thresh = 0.008
        self._frame_static = True
        self._ocr_manager = None
        logger.info(f"Pipeline v0.4.10 ready (target={target_fps}FPS)")

    # 鈹€鈹€ properties 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
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
    @property
    def is_static(self): return self._frame_static

    @show_mask.setter
    def show_mask(self, v: bool):
        if v == self._show_mask:
            return
        logger.info(f"Mask: {self._show_mask} -> {v}")
        self._show_mask = v
        if v:
            self._init_mask()
            self._do_clean_detect()
        else:
            self._prev_mask = None
            self._prev_colors = None
        self._sent_boxes = None
        self._sent_has_mask = None

    # 鈹€鈹€ init 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
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

    # 鈹€鈹€ helpers 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
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

    def _detect(self, img, region):
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

    def _do_clean_detect(self):
        """One-time: hide, clean capture, detect, show with full window reset."""
        region = self._config.load_region()
        hwnd = int(self._overlay.winId())
        user32.ShowWindow(hwnd, 0)
        try:
            img = capture_region(region)
        finally:
            user32.ShowWindow(hwnd, 4)
        if img.size == 0:
            return
        self._prev_frame = img.copy()
        self._detect(img, region)
        self._overlay.hide()
        self._overlay.show()
        self._sent_boxes = None
        self._sent_has_mask = None
        logger.info(f"Clean detect: {len(self._prev_boxes) if self._prev_boxes else 0} boxes")

    def _frame_changed(self, img):
        if self._prev_frame is None:
            return True
        if self._prev_frame.shape != img.shape:
            return True
        d = np.mean(np.abs(img.astype(np.int16) - self._prev_frame.astype(np.int16))) / 255.0
        return d >= self._diff_thresh

    # 鈹€鈹€ start / stop 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    def start(self):
        if not self._detector.is_loaded:
            return False
        if self._running:
            return True
        self._running = True
        self._busy = False
        self._last_region = None
        self._prev_frame = None
        self._prev_boxes = None
        self._prev_mask = None
        self._prev_colors = None
        self._sent_boxes = None
        self._sent_has_mask = None
        self._frame_static = True
        self._ocr_manager = None
        self._frame_count = 0
        self._last_fps = time.time()
        self._dpr = self._dpr_get()
        region = self._config.load_region()
        self._overlay.update_region(region)
        self._last_region = dict(region)
        self._overlay.show_overlay()
        self._timer.start(self._interval)
        self._start_ocr()
        logger.info(f"Started (DPR={self._dpr})")
        return True

    def stop(self):
        self._running = False
        self._timer.stop()
        self._overlay.hide_overlay()
        self._stop_ocr()
        self._prev_frame = None
        logger.info("Stopped")

    # 鈹€鈹€ main tick 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    def _tick(self):
        if self._busy or not self._running:
            return
        self._busy = True
        try:
            region = self._config.load_region()
            if self._last_region != region:
                self._overlay.update_region(region)
                self._last_region = dict(region)
                self._prev_frame = None
                self._sent_boxes = None

            if self._show_mask:
                self._tick_mask(region)
            else:
                self._tick_normal(region)

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

    # 鈹€鈹€ normal mode: direct capture, no hide 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€
    def _tick_normal(self, region):
        img = capture_region(region)
        if img.size == 0:
            return

        changed = self._frame_changed(img)
        self._frame_static = not changed
        if changed:
            self._prev_frame = img.copy()
            self._detect(img, region)
            self._submit_ocr(img, region)

        boxes = self._prev_boxes if self._prev_boxes else []
        if boxes != self._sent_boxes or self._sent_has_mask:
            self._overlay.set_data(boxes, None, None)
            self._sent_boxes = list(boxes) if boxes else None
            self._sent_has_mask = False

    # 鈹€鈹€ mask mode: capture with mask for diff, clean on change 鈹€鈹€
    def _tick_mask(self, region):
        # Capture with mask visible (for frame-diff)
        img = capture_region(region)
        if img.size == 0:
            return

        changed = self._frame_changed(img)
        self._frame_static = not changed

        if changed:
            self._prev_frame = img.copy()
            # Clean capture for detection (brief hide)
            hwnd = int(self._overlay.winId())
            user32.ShowWindow(hwnd, 0)
            try:
                clean = capture_region(region)
            finally:
                user32.ShowWindow(hwnd, 4)
            if clean.size > 0:
                self._detect(clean, region)
                self._submit_ocr(clean, region)
            # Reset window to ensure rendering works
            self._overlay.hide()
            self._overlay.show()
            self._sent_boxes = None
            self._sent_has_mask = None

        # Always render cached data
        boxes = self._prev_boxes if self._prev_boxes else []
        has_mask = self._prev_mask is not None
        if boxes != self._sent_boxes or has_mask != self._sent_has_mask:
            if has_mask:
                self._overlay.set_data(boxes, self._prev_mask, self._prev_colors)
            else:
                self._overlay.set_data(boxes, None, None)
            self._sent_boxes = list(boxes) if boxes else None
            self._sent_has_mask = has_mask



    # ── OCR integration ─────────────────────────────────────────
    def _start_ocr(self):
        try:
            cfg = self._config.get_ocr_config()
            def on_result(results):
                # Update overlay with OCR text
                self._overlay.set_ocr_results(results)
            self._ocr_manager = OCRManager(cfg, on_result=on_result)
            self._ocr_manager.start()
            logger.info("OCR manager started")
        except Exception as e:
            logger.error(f"OCR start failed: {e}")
            self._ocr_manager = None

    def _stop_ocr(self):
        if self._ocr_manager:
            self._ocr_manager.stop()
            self._ocr_manager = None

    def _submit_ocr(self, img, region):
        if self._ocr_manager is None or not self._prev_boxes:
            return
        try:
            self._ocr_manager.submit(img, self._prev_boxes)
        except Exception as e:
            logger.debug(f"OCR submit: {e}")
    def cleanup(self):
        self._stop_ocr()
        self.stop()
        self._overlay.close()