# -*- coding: utf-8 -*-
"""
NexaTrans - Detection Pipeline v0.6.0

Normal mode: capture, diff, detect, OCR, translate, render.
Mask mode: capture WITH mask (for diff), only clean-capture when changed.
Stage 6: DeepSeek AI translation with parallel execution and caching.
"""

import logging, time, sys, ctypes, hashlib, threading, numpy as np, cv2
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QTimer, QObject, Signal, Qt
from PySide6.QtWidgets import QApplication
from screen.screenshot import capture_region
from detection.dbnet_detector import DBNetDetector
from overlay.text_overlay import TextOverlay

logger = logging.getLogger("NexaTrans.DetectionPipeline")

user32 = ctypes.windll.user32

OCR_CACHE_SIZE = 64


class DetectionPipeline(QObject):

    # Emitted from worker threads.  Qt delivers these to the slots below with a
    # queued connection, so the overlay is only ever touched on the GUI thread.
    # (Calling QWidget methods from a background thread is undefined behaviour
    # and showed up as random UI freezes when a translation completed.)
    transResultsReady = Signal(object)
    overlayRefreshRequested = Signal()
    # (raw detector output, source image, region, mask-wanted) -> GUI thread
    detectReady = Signal(object)

    def __init__(self, config_manager, target_fps=10, limit_side_len=960,
                 detector=None, ocr_engine=None):
        """
        ``detector`` / ``ocr_engine`` may be supplied pre-built.  Both are pure
        Python/ONNX objects with no Qt dependency, so callers can build them on
        a worker thread (they take seconds to load) and hand them over here -
        the pipeline itself owns a QWidget and must be built on the GUI thread.
        """
        super().__init__()
        self._config = config_manager
        self._detector = (detector if detector is not None
                          else DBNetDetector(limit_side_len=limit_side_len))
        self._overlay = TextOverlay()
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._running = False
        self._busy = False
        self._show_mask = False
        self._ocr_enabled = False
        self._trans_enabled = False
        self._ocr_engine = ocr_engine
        self._ocr_results = []
        self._trans_results = []
        self._ocr_cache = {}
        self._ocr_cache_order = []
        self._mask_gen = None
        self._mask_ref = None
        self._crop_proc = None
        self._layout_analyzer = None
        self._trans_client = None
        self._trans_manager = None
        self._trans_cache = None
        self._trans_pending = False
        self._trans_count = 0
        self._trans_lock = threading.Lock()
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

        # worker -> GUI thread marshalling
        self.transResultsReady.connect(self._on_trans_results,
                                       Qt.QueuedConnection)
        self.overlayRefreshRequested.connect(self._update_overlay_display,
                                             Qt.QueuedConnection)
        self.detectReady.connect(self._on_detect_ready, Qt.QueuedConnection)
        self._pool = None
        logger.info(f"Pipeline v0.6.0 ready (target={target_fps}FPS)")

    # ---- GUI-thread slots for background work ----
    def _on_trans_results(self, translated):
        self._trans_results = translated
        self._overlay.set_trans_results(translated)
        self._trans_count += 1
        logger.info(f"Translation complete: {len(translated)} results")

    # ---- properties ----
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
    @property
    def ocr_enabled(self): return self._ocr_enabled
    @property
    def trans_enabled(self): return self._trans_enabled
    @property
    def ocr_results(self): return self._ocr_results
    @property
    def trans_results(self): return self._trans_results

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

    @ocr_enabled.setter
    def ocr_enabled(self, v: bool):
        if v == self._ocr_enabled:
            return
        logger.info(f"OCR: {self._ocr_enabled} -> {v}")
        self._ocr_enabled = v
        if v:
            self._init_ocr()
            self._prev_frame = None
        else:
            self._ocr_results = []
            self._trans_results = []
            self._overlay.set_ocr_results([])
            self._overlay.show_translation = False
        self._update_overlay_display()

    @trans_enabled.setter
    def trans_enabled(self, v: bool):
        if v == self._trans_enabled:
            return
        logger.info(f"Translation: {self._trans_enabled} -> {v}")
        self._trans_enabled = v
        self._overlay.show_translation = v
        if v:
            self._init_translation()
            self._prev_frame = None
        else:
            self._trans_results = []
            self._overlay.set_trans_results([])
        self._update_overlay_display()

    def _update_overlay_display(self):
        """Refresh overlay with current data."""
        boxes = self._prev_boxes if self._prev_boxes else []
        has_mask = self._prev_mask is not None
        if has_mask:
            self._overlay.set_data(boxes, self._prev_mask, self._prev_colors)
        else:
            self._overlay.set_data(boxes, None, None)

    # ---- init methods ----
    def _init_ocr(self):
        if self._ocr_engine:
            return
        try:
            from ocr.paddleocr_engine import PaddleOCREngine
            self._ocr_engine = PaddleOCREngine(lang="ch")
            if self._ocr_engine.is_loaded:
                logger.info("OCR engine loaded")
            else:
                logger.error("OCR engine failed to load")
        except Exception as e:
            logger.error(f"OCR init failed: {e}", exc_info=True)

    def _init_translation(self):
        if self._trans_client and self._trans_manager:
            return
        try:
            from translation.deepseek_client import DeepSeekClient
            from translation.translation_manager import TranslationManager
            from translation.cache import TranslationCache
            import os

            self._trans_cache = TranslationCache(
                os.path.join(os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "translation_cache.json")
            )
            tc = self._config.get_translation_config()
            self._trans_client = DeepSeekClient(
                model=tc.get("model", "deepseek-chat")
            )
            if not self._trans_client.is_configured:
                logger.warning("DeepSeek API key not configured. Set DEEPSEEK_API_KEY in .env")
            else:
                logger.info("DeepSeek client ready")

            self._trans_manager = TranslationManager(
                self._trans_client,
                cache=self._trans_cache,
                max_workers=tc.get("max_workers", 3),
            )
            self._trans_manager.target_language = tc.get("target_language", "zh")
            logger.info("Translation manager ready")
        except Exception as e:
            logger.error(f"Translation init failed: {e}", exc_info=True)

    def _init_crop(self):
        if self._crop_proc:
            return
        try:
            from text_processing.crop_processor import CropProcessor
            from text_processing.layout_analyzer import LayoutAnalyzer
            self._crop_proc = CropProcessor()
            self._layout_analyzer = LayoutAnalyzer()
        except Exception as e:
            logger.error(f"Crop init failed: {e}")

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

    # ---- helpers ----
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

    def _apply_detection(self, img, region, raw):
        """
        Post-process a raw detector result.  GUI thread only.

        Split out from :meth:`_detect` so the expensive ONNX call can run on a
        worker thread while everything that touches Qt stays here.
        """
        pb = raw.get("boxes", [])
        ss = raw.get("scores", [])
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

        if self._ocr_enabled and self._ocr_engine and self._ocr_engine.is_loaded and lb:
            self._run_ocr(img, lb, region)

    def _detect(self, img, region):
        """Synchronous detect + apply, for the one-shot / mask-enable paths."""
        self._apply_detection(img, region, self._detector.detect(img))

    # ---- async detection (keeps the GUI thread free) ----

    def _submit_detect(self, img, region):
        """Run the ONNX inference on a worker; results come back via signal."""
        if self._pool is None:
            self._pool = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="NexaTrans-detect")
        self._pool.submit(self._detect_job, img, region, self._show_mask)

    def _detect_job(self, img, region, want_mask):
        """Worker thread: inference only - no Qt objects may be touched."""
        raw = None
        try:
            raw = self._detector.detect(img)
        except Exception as e:
            logger.error(f"Detection failed: {e}", exc_info=True)
        self.detectReady.emit((raw, img, region, want_mask))

    def _on_detect_ready(self, payload):
        """GUI thread: apply the finished job and release the tick gate."""
        try:
            raw, img, region, want_mask = payload
            if raw is not None:
                self._apply_detection(img, region, raw)
                if want_mask:
                    self._overlay.hide()
                    self._overlay.show()
                    self._overlay._apply_click_through()
                    self._sent_boxes = None
                    self._sent_has_mask = None
                self._push_boxes_to_overlay(
                    self._prev_mask is not None if want_mask else False)
        except Exception as e:
            logger.error(f"Apply detection failed: {e}", exc_info=True)
        finally:
            self._busy = False

    def _push_boxes_to_overlay(self, has_mask):
        boxes = self._prev_boxes if self._prev_boxes else []
        if boxes != self._sent_boxes or has_mask != self._sent_has_mask:
            if has_mask:
                self._overlay.set_data(boxes, self._prev_mask, self._prev_colors)
            else:
                self._overlay.set_data(boxes, None, None)
            self._sent_boxes = list(boxes) if boxes else None
            self._sent_has_mask = has_mask

    def _run_ocr(self, img, boxes, region):
        self._init_crop()
        if not self._crop_proc:
            return
        try:
            h_l, w_l = region["height"], region["width"]
            ocr_img = cv2.resize(img, (w_l, h_l))
            crops = self._crop_proc.crop(ocr_img, boxes)
            layouts = self._layout_analyzer.analyze(boxes) if self._layout_analyzer else []
            dir_map = {ll["id"]: ll["direction"] for ll in layouts}

            results = []
            tp = self._config.get_text_processing_config()
            min_conf = tp.get("min_confidence", 0.5)

            for c in crops:
                crop_img = c["image"]
                if crop_img is None or crop_img.size == 0:
                    continue
                img_hash = hashlib.md5(crop_img.tobytes()).hexdigest()
                if img_hash in self._ocr_cache:
                    cached = dict(self._ocr_cache[img_hash])
                    cached["id"] = c["id"]
                    cached["box"] = c["box"]
                    cached["direction"] = dir_map.get(c["id"], "horizontal")
                    cached["cached"] = True
                    results.append(cached)
                    continue

                t0 = time.time()
                enhanced = self._ocr_engine.preprocess(crop_img)
                rec = self._ocr_engine.recognize(enhanced)
                if rec["confidence"] >= min_conf and rec["text"]:
                    entry = {
                        "id": c["id"],
                        "box": c["box"],
                        "direction": dir_map.get(c["id"], "horizontal"),
                        "text": rec["text"],
                        "confidence": rec["confidence"],
                        "cached": False,
                        "time_ms": (time.time() - t0) * 1000,
                    }
                    results.append(entry)
                    self._ocr_cache[img_hash] = dict(entry)
                    self._ocr_cache_order.append(img_hash)
                    if len(self._ocr_cache_order) > OCR_CACHE_SIZE:
                        old = self._ocr_cache_order.pop(0)
                        self._ocr_cache.pop(old, None)

            if results:
                self._ocr_results = results
                self._overlay.set_ocr_results(results)
                logger.info(f"OCR: {len(results)} results")

                # Stage 6: Fire-and-forget translation (non-blocking)
                if self._trans_enabled and self._trans_manager:
                    self._start_async_translation(results)

        except Exception as e:
            logger.error(f"OCR run failed: {e}", exc_info=True)

    def _start_async_translation(self, ocr_results):
        """Start translation in background thread, non-blocking."""
        with self._trans_lock:
            if self._trans_pending:
                return
            self._trans_pending = True

        def _do_translate():
            # NOTE: this runs on a worker thread - never touch widgets here,
            # hand the result back to the GUI thread via a queued signal.
            try:
                translated = self._trans_manager.translate_regions(ocr_results)
                self.transResultsReady.emit(translated)
            except Exception as e:
                logger.error(f"Translation failed: {e}", exc_info=True)
            finally:
                with self._trans_lock:
                    self._trans_pending = False
                self.overlayRefreshRequested.emit()

        t = threading.Thread(target=_do_translate, daemon=True)
        t.start()

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
        # never run the predictor concurrently with an in-flight tick job
        if self._busy:
            logger.debug("Clean detect skipped: pipeline busy")
            return
        region = self._config.load_region()
        hwnd = int(self._overlay.winId())
        user32.ShowWindow(hwnd, 0)
        try:
            img = capture_region(region)
            if img is not None and img.size > 0:
                self._detect(img, region)
        finally:
            user32.ShowWindow(hwnd, 4)
            self._overlay.hide()
            self._overlay.show()
            self._overlay._apply_click_through()
        self._sent_boxes = None
        self._sent_has_mask = None

    def capture_once(self):
        """One-shot capture, detect, OCR, and translate. Returns results dict."""
        if self._busy:
            logger.warning("Pipeline busy, cannot capture_once")
            return None
        if not self._detector.is_loaded:
            return None
        region = self._config.load_region()
        if region.get("width", 0) <= 0 or region.get("height", 0) <= 0:
            logger.warning("No region selected")
            return None
        self._busy = True
        try:
            self._overlay.update_region(region)
            self._overlay.show_overlay()
            hwnd = int(self._overlay.winId())
            user32.ShowWindow(hwnd, 0)
            try:
                img = capture_region(region)
            finally:
                user32.ShowWindow(hwnd, 4)
            if img is None or img.size == 0:
                logger.warning("Capture failed")
                return None
            r = self._detector.detect(img)
            pb = r.get("boxes", [])
            ss = r.get("scores", [])
            dpr = self._dpr
            lb = [self._to_rect([int(round(c / dpr)) for c in b]) for b in pb]
            if lb and ss:
                lb = self._filter(lb, ss, region["width"], region["height"])
            boxes = lb
            self._prev_boxes = boxes
            logger.info(f"capture_once: {len(boxes)} boxes")
            mask = None
            colors = None
            if boxes and self._show_mask:
                self._init_mask()
                if self._mask_gen:
                    h_l, w_l = region["height"], region["width"]
                    if self._mask_ref:
                        mk = self._mask_gen.generate((h_l, w_l), boxes)
                        mask = self._mask_ref.refine(mk)
                    else:
                        mask = np.zeros((h_l, w_l), np.uint8)
                        for b in boxes:
                            xs = [b[i] for i in range(0, len(b), 2)]
                            ys = [b[i + 1] for i in range(0, len(b), 2)]
                            cv2.fillPoly(mask, [np.array([[min(xs), min(ys)], [max(xs), min(ys)], [max(xs), max(ys)], [min(xs), max(ys)]], np.int32)], 255)
                    img_resized = cv2.resize(img, (w_l, h_l))
                    colors = [self._bg_color(img_resized, b) for b in boxes]
                self._prev_mask = mask
                self._prev_colors = colors
            ocr_results = []
            if boxes and self._ocr_engine and self._ocr_engine.is_loaded:
                self._init_crop()
                if self._crop_proc:
                    h_l, w_l = region["height"], region["width"]
                    ocr_img = cv2.resize(img, (w_l, h_l))
                    crops = self._crop_proc.crop(ocr_img, boxes)
                    layouts = self._layout_analyzer.analyze(boxes) if self._layout_analyzer else []
                    dir_map = {ll["id"]: ll["direction"] for ll in layouts}
                    tp = self._config.get_text_processing_config()
                    min_conf = tp.get("min_confidence", 0.5)
                    results_ocr = []
                    for c in crops:
                        crop_img = c["image"]
                        if crop_img is None or crop_img.size == 0:
                            continue
                        img_hash = hashlib.md5(crop_img.tobytes()).hexdigest()
                        if img_hash in self._ocr_cache:
                            cached = dict(self._ocr_cache[img_hash])
                            cached["id"] = c["id"]
                            cached["box"] = c["box"]
                            cached["direction"] = dir_map.get(c["id"], "horizontal")
                            cached["cached"] = True
                            results_ocr.append(cached)
                            continue
                        t0 = time.time()
                        enhanced = self._ocr_engine.preprocess(crop_img)
                        rec = self._ocr_engine.recognize(enhanced)
                        if rec["confidence"] >= min_conf and rec["text"]:
                            entry = {
                                "id": c["id"],
                                "box": c["box"],
                                "direction": dir_map.get(c["id"], "horizontal"),
                                "text": rec["text"],
                                "confidence": rec["confidence"],
                                "cached": False,
                                "time_ms": (time.time() - t0) * 1000,
                            }
                            results_ocr.append(entry)
                            self._ocr_cache[img_hash] = dict(entry)
                            self._ocr_cache_order.append(img_hash)
                            if len(self._ocr_cache_order) > OCR_CACHE_SIZE:
                                old_h = self._ocr_cache_order.pop(0)
                                self._ocr_cache.pop(old_h, None)
                    self._ocr_results = results_ocr
                    ocr_results = list(results_ocr)
                    logger.info(f"capture_once: OCR {len(results_ocr)} results")
            trans_results = []
            if ocr_results and self._trans_manager and self._trans_client and self._trans_client.is_configured:
                trans_results = self._trans_manager.translate_regions(ocr_results)
                self._trans_results = trans_results
                self._trans_count += 1
                logger.info(f"capture_once: translated {len(trans_results)} results")
            return {"boxes": boxes, "ocr": ocr_results, "trans": trans_results, "mask": mask, "colors": colors}
        finally:
            self._busy = False
    def _frame_changed(self, img):
        if self._prev_frame is None:
            return True
        if self._prev_frame.shape != img.shape:
            return True
        d = np.mean(np.abs(img.astype(np.int16) - self._prev_frame.astype(np.int16))) / 255.0
        return d >= self._diff_thresh

    # ---- start / stop ----

    def set_fps(self, fps: int):
        self._interval = int(1000 / max(fps, 1))
        if self._running:
            self._timer.setInterval(self._interval)
        logger.info(f"FPS target set to {fps}")

    @property
    def trans_count(self) -> int:
        return self._trans_count

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
        self._ocr_cache = {}
        self._ocr_cache_order = []
        self._ocr_results = []
        self._trans_results = []
        self._trans_pending = False
        self._trans_count = 0
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
        self._prev_frame = None
        self._ocr_cache = {}
        self._ocr_cache_order = []
        self._ocr_results = []
        self._trans_results = []
        self._trans_pending = False
        self._trans_count = 0
        if self._trans_cache:
            self._trans_cache.save()
        if self._trans_manager:
            self._trans_manager.shutdown()
        logger.info("Stopped")

    # ---- main tick ----
    def _tick(self):
        if self._busy or not self._running:
            return
        # _busy is released by _on_detect_ready when a detection job was
        # submitted, so a slow inference can never overlap the next tick.
        async_started = False
        self._busy = True
        try:
            region = self._config.load_region()
            if self._last_region != region:
                self._overlay.update_region(region)
                self._last_region = dict(region)
                self._prev_frame = None
                self._sent_boxes = None

            if self._show_mask:
                async_started = self._tick_mask(region)
            else:
                async_started = self._tick_normal(region)

            self._frame_count += 1
            now = time.time()
            if now - self._last_fps >= 1.0:
                self._fps = self._frame_count / (now - self._last_fps)
                self._frame_count = 0
                self._last_fps = now
        except Exception as e:
            logger.error(f"Tick: {e}", exc_info=True)
            async_started = False
        finally:
            if not async_started:
                self._busy = False

    def _tick_normal(self, region):
        """Returns True when an async detection job was submitted."""
        if self._ocr_enabled or self._trans_enabled:
            hwnd = int(self._overlay.winId())
            user32.ShowWindow(hwnd, 0)
            try:
                img = capture_region(region)
            finally:
                user32.ShowWindow(hwnd, 4)
        else:
            img = capture_region(region)

        if img.size == 0:
            return False

        changed = self._frame_changed(img)
        self._frame_static = not changed
        if changed:
            self._prev_frame = img.copy()
            self._submit_detect(img, region)
            return True

        self._push_boxes_to_overlay(False)
        return False

    def _tick_mask(self, region):
        """Returns True when an async detection job was submitted."""
        img = capture_region(region)
        if img.size == 0:
            return False
        changed = self._frame_changed(img)
        self._frame_static = not changed
        if changed:
            self._prev_frame = img.copy()
            hwnd = int(self._overlay.winId())
            user32.ShowWindow(hwnd, 0)
            try:
                clean = capture_region(region)
            finally:
                user32.ShowWindow(hwnd, 4)
            if clean.size > 0:
                self._submit_detect(clean, region)
                return True
            self._overlay.hide()
            self._overlay.show()
            self._overlay._apply_click_through()
            self._sent_boxes = None
            self._sent_has_mask = None
        self._push_boxes_to_overlay(self._prev_mask is not None)
        return False

    def cleanup(self):
        self.stop()
        if self._pool is not None:
            self._pool.shutdown(wait=False)
            self._pool = None
        self._overlay.close()
