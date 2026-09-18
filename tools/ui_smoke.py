# -*- coding: utf-8 -*-
"""
NexaTrans - headless UI smoke test.

Exercises the v2.0 UI wiring (config load/save round-trip, page switching,
toggles, sliders, toasts, region selector) without needing the AI models.

Usage:
    python tools/ui_smoke.py
"""

import os
import sys
import tempfile
import threading
import time
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer                 # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent                      # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget                   # noqa: E402

from config.config_manager import ConfigManager                    # noqa: E402
from ui.main_window import MainWindow                              # noqa: E402
from ui.widgets.controls import ToggleSwitch                       # noqa: E402
from ui.theme import (                                             # noqa: E402
    MODE_DARK, MODE_LIGHT, MODE_SYSTEM, apply_app_theme, set_theme_mode,
    system_accent, system_theme_mode, theme,
)

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}{(' -> ' + detail) if detail else ''}")
    if not condition:
        FAILURES.append(name)


def pump(app: QApplication, ms: int = 120) -> None:
    deadline = time.time() + ms / 1000.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.003)


def main() -> int:
    app = QApplication(sys.argv)
    apply_app_theme(app, MODE_SYSTEM)

    print("windows integration")
    check("system theme detected", system_theme_mode() in (MODE_LIGHT, MODE_DARK),
          system_theme_mode())
    accent = system_accent()
    check("system accent colour read from the registry",
          accent.startswith("#FF") and len(accent) == 9, accent)
    check("theme follows the system setting",
          theme().is_dark == (system_theme_mode() == MODE_DARK),
          f"accent={accent} dark={theme().is_dark}")

    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = os.path.join(tmp, "settings.json")
        config = ConfigManager(config_path=cfg_path)

        # seed a known state so the assertions below are meaningful
        config.save_region({"x": 53, "y": 631, "width": 677, "height": 460})
        ui_cfg = config.get_ui_config()
        ui_cfg.update({"show_mask": True, "show_boxes": False,
                       "show_ocr": True, "show_translation": True,
                       "fps_target": 10, "once_display_seconds": 5,
                       "once_hotkey_mod": "Ctrl", "once_hotkey_key": "T"})
        config.save_ui_config(ui_cfg)

        print("constructing MainWindow ...")
        window = MainWindow(config)
        window.show()
        pump(app, 400)

        print("\nstructure")
        check("two pages in the slide stack", window.stack.count() == 2)
        check("home page is current",
              window.stack.currentIndex() == 0)
        check("window is frameless",
              bool(window.windowFlags() & Qt.FramelessWindowHint))
        check("primary button exists and is labelled",
              window.start_btn.text() == "\u5f00\u59cb\u7ffb\u8bd1",
              window.start_btn.text())

        print("\nconfig -> widgets")
        check("mask toggle reflects config", window.mask_check.isChecked())
        check("boxes toggle reflects config",
              window.boxes_check.isChecked() is False)
        check("fps slider reflects config", window._s_fps.value() == 10)
        check("region label shows the stored region",
              "677" in window.region_info.text(), window.region_info.text())
        check("hotkey selectors reflect the stored hotkey",
              window._hotkey_mod_combo.currentText() == "Ctrl"
              and window._hotkey_key_combo.currentText() == "T",
              f"{window._hotkey_mod_combo.currentText()} + "
              f"{window._hotkey_key_combo.currentText()}")
        knob_ok = all(
            (t._p > 0.5) == t.isChecked()
            for t in (window.mask_check, window.boxes_check,
                      window.redbox_check, window.ocr_check, window.trans_check)
        )
        check("toggle knobs match their checked state", knob_ok)

        print("\ninteraction -> config")
        window.trans_check.setChecked(False)
        pump(app, 80)
        check("unchecking AI translation persists",
              config.get_ui_config()["show_translation"] is False)
        window.trans_check.setChecked(True)
        pump(app, 80)

        window._s_fps.setValue(24)
        pump(app, 80)
        check("moving the FPS slider persists",
              config.get_ui_config()["fps_target"] == 24)
        check("FPS value chip follows the slider",
              window._l_fps.text() == "24", window._l_fps.text())

        window._s_once_display.setValue(9)
        pump(app, 80)
        check("display duration is persisted (v1.2 never saved this)",
              config.get_ui_config().get("once_display_seconds") == 9)

        window._s_min_conf.setValue(72)
        pump(app, 80)
        check("filter slider writes text_processing config",
              abs(config.get_text_processing_config()["min_confidence"]
                  - 0.72) < 1e-6)
        check("filter value chip formatted",
              window._l_min_conf.text() == "0.72", window._l_min_conf.text())

        print("\nrestore filter defaults")
        window._s_min_conf.setValue(85)
        window._s_min_asp.setValue(27)
        window._s_max_icon.setValue(17)
        window._s_min_area.setValue(19)
        pump(app, 120)
        check("filter sliders are off-default before the reset",
              window._s_min_conf.value() == 85
              and window._s_min_area.value() == 19)
        window.reset_filter_btn.click()
        pump(app, 150)
        check("restore-defaults resets every filter slider",
              (window._s_min_conf.value(), window._s_min_asp.value(),
               window._s_max_icon.value(), window._s_min_area.value())
              == (50, 18, 14, 5),
              f"{window._s_min_conf.value()}/{window._s_min_asp.value()}/"
              f"{window._s_max_icon.value()}/{window._s_min_area.value()}")
        stored = config.get_text_processing_config()
        check("restore-defaults persists the defaults",
              abs(stored["min_confidence"] - 0.5) < 1e-6
              and abs(stored["min_text_aspect"] - 1.8) < 1e-6
              and abs(stored["max_icon_aspect"] - 1.4) < 1e-6
              and abs(stored["min_area_ratio"] - 0.005) < 1e-6,
              str({k: stored[k] for k in MainWindow.FILTER_KEYS}))
        check("restore-defaults refreshes the value chips",
              window._l_min_conf.text() == "0.50"
              and window._l_min_area.text() == "0.005",
              f"{window._l_min_conf.text()} / {window._l_min_area.text()}")
        check("restore-defaults leaves unrelated config alone",
              config.get_ui_config()["fps_target"] == 24)

        print("\npage transition")
        home_h = window.height()
        window.settings_btn.click()
        pump(app, 700)
        check("settings page is shown", window.stack.currentIndex() == 1)
        check("window grew for the settings page", window.height() > home_h,
              f"{home_h} -> {window.height()}")
        window.settings_btn.click()
        pump(app, 700)
        check("back to the home page", window.stack.currentIndex() == 0)
        check("window shrank back", abs(window.height() - home_h) <= 2,
              f"{window.height()} vs {home_h}")

        print("\nstatus + info bar")
        from ui.widgets.feedback import InfoBar
        window.status_badge.set_state("\u8fd0\u884c\u4e2d", "running")
        check("status badge running state",
              window.status_badge._timer.isActive())
        window.status_badge.set_state("\u5c31\u7eea", "idle")
        check("status badge idle state stops the pulse",
              not window.status_badge._timer.isActive())

        bar = window._notify("\u6d4b\u8bd5\u901a\u77e5", "info", 300)
        pump(app, 200)
        check("info bar is visible", bar.isVisible())
        check("info bar is anchored low so it cannot hide the status badge",
              bar.y() > window.height() // 2,
              f"y={bar.y()} of window height {window.height()}")
        check("info bar clears the footer",
              bar.y() + bar.height() <= window.height() - 32,
              f"bottom={bar.y() + bar.height()}")
        bar.dismiss()
        pump(app, 400)
        check("info bar dismissed itself", not bar.isVisible())

        window._chip_fps.set_value(42, animate_change=False)
        check("metric tile shows the new value",
              window._chip_fps._value == "42", window._chip_fps._value)

        print("\ntheme switching")
        set_theme_mode(MODE_LIGHT, app)
        check("light theme applied", theme().is_dark is False)
        check("style sheet is themed", "QComboBox" in app.styleSheet())
        set_theme_mode(MODE_DARK, app)
        check("dark theme applied", theme().is_dark is True)
        window.theme_combo.setCurrentIndex(
            window.theme_combo.findData(MODE_LIGHT))
        pump(app, 120)
        check("theme choice persists to config",
              config.get_ui_config().get("theme_mode") == MODE_LIGHT,
              str(config.get_ui_config().get("theme_mode")))
        set_theme_mode(MODE_SYSTEM, app)

        print("\nwindow geometry (no invisible border)")
        from ui.main_window import HOME_H, SHADOW_PAD, WINDOW_W
        check("no transparent padding constant", SHADOW_PAD == 0, str(SHADOW_PAD))
        check("window matches the visible panel width",
              window.width() == WINDOW_W, f"{window.width()} vs {WINDOW_W}")
        check("window matches the visible panel height",
              window.height() == HOME_H, f"{window.height()} vs {HOME_H}")
        check("shell fills the window rect (nothing hidden around it)",
              window.shell.geometry() == window.rect(),
              f"shell={window.shell.geometry()} window={window.rect()}")

        print("\nmodel loading (must not freeze the GUI thread)")
        fake_module = types.ModuleType("detection.dbnet_detector")
        gui_thread_name = threading.main_thread().name

        class SlowDetector:
            """Stands in for the ONNX/PaddleX predictors (seconds to build)."""

            DETECT_BOX = [[10, 10, 100, 10, 100, 40, 10, 40]]

            def __init__(self, limit_side_len=960):
                self.thread = threading.current_thread().name
                self.detect_threads = set()
                self.is_loaded = True
                time.sleep(0.45)

            def detect(self, img):
                self.detect_threads.add(threading.current_thread().name)
                return {"boxes": list(self.DETECT_BOX), "scores": [0.95]}

        fake_module.DBNetDetector = SlowDetector
        sys.modules["detection.dbnet_detector"] = fake_module

        window._s_fps.setValue(20)
        window.trans_check.setChecked(False)
        window.ocr_check.setChecked(False)
        window._pipeline = None
        window._pipeline_inited = False

        ticks = []
        probe = QTimer()
        probe.setInterval(15)
        probe.timeout.connect(lambda: ticks.append(time.time()))
        probe.start()

        began = time.time()
        window.start_btn.click()            # what the user does: press 开始翻译
        deadline = time.time() + 3.0
        while time.time() < deadline and window._pipeline is None:
            app.processEvents()
            time.sleep(0.002)
        elapsed = time.time() - began
        probe.stop()

        check("a queued start loads the models in the background",
              window._pipeline is not None, f"{elapsed:.2f}s")
        check("event loop kept ticking while models loaded", len(ticks) >= 8,
              f"{len(ticks)} timer ticks over {elapsed:.2f}s")
        check("detector was built off the GUI thread",
              getattr(window._pipeline.detector, "thread", gui_thread_name)
              != gui_thread_name,
              getattr(window._pipeline.detector, "thread", "?"))
        check("queued start ran once loading finished",
              window._pipeline.is_running)

        # the detection result must still reach the overlay through the
        # worker-thread -> queued-signal path.  (Enabling the mask performs one
        # synchronous detect at start-up, so only the periodic loop is checked.)
        window._pipeline.detector.detect_threads.clear()
        window._pipeline._frame_changed = lambda img: True
        window._pipeline._sent_boxes = None
        window._pipeline._sent_has_mask = None
        deadline = time.time() + 3.0
        while (time.time() < deadline
               and not window._pipeline.detector.detect_threads):
            app.processEvents()
            time.sleep(0.002)
        check("async detection result reaches the overlay",
              window._pipeline._sent_boxes == SlowDetector.DETECT_BOX,
              str(window._pipeline._sent_boxes))
        loop_threads = set(window._pipeline.detector.detect_threads)
        check("periodic inference runs off the GUI thread",
              loop_threads and gui_thread_name not in loop_threads,
              str(loop_threads))

        window._stop_all()
        check("stop returns the button to 开始翻译",
              window.start_btn.text() == "\u5f00\u59cb\u7ffb\u8bd1",
              window.start_btn.text())

        print("\ntranslation client must pick up a key saved later")
        import translation.deepseek_client as dsc
        from detection.detection_pipeline import DetectionPipeline

        class TinyDetector:
            is_loaded = True

            def detect(self, img):
                return {"boxes": [], "scores": []}

        real_load_env = dsc._load_env
        probe = None
        try:
            # first run: no .env / no key yet
            dsc._load_env = lambda: {}
            probe = DetectionPipeline(config, detector=TinyDetector())
            probe.trans_enabled = True
            check("client is unconfigured when no key exists",
                  probe._trans_client is not None
                  and not probe._trans_client.is_configured)

            # the user now saves their key in Settings, then presses start again
            dsc._load_env = real_load_env
            probe.trans_enabled = True
            check("re-enabling translation picks up the newly saved key",
                  probe._trans_client.is_configured)
        finally:
            dsc._load_env = real_load_env
            if probe is not None:
                probe.cleanup()

        print("\ntoggle hit area")
        from PySide6.QtTest import QTest
        from PySide6.QtCore import QPoint

        probe_switch = ToggleSwitch()
        probe_switch.show()
        pump(app, 60)
        QTest.mouseClick(probe_switch, Qt.LeftButton, Qt.NoModifier,
                         QPoint(probe_switch.width() - 6,
                                probe_switch.height() // 2))
        pump(app, 60)
        check("clicking the right edge of the switch toggles it",
              probe_switch.isChecked(),
              f"width={probe_switch.width()} clicked at "
              f"x={probe_switch.width() - 6}")

        QTest.mouseClick(probe_switch, Qt.LeftButton, Qt.NoModifier,
                         QPoint(probe_switch.width() // 2,
                                probe_switch.height() // 2))
        pump(app, 60)
        check("clicking the middle of the switch toggles it back",
              not probe_switch.isChecked())
        probe_switch.close()

        from ui.widgets.containers import SettingsRow
        row_switch = ToggleSwitch()
        row = SettingsRow("\u6587\u5b57\u8bc6\u522b", "\u4ece\u622a\u56fe\u4e2d\u63d0\u53d6\u6587\u5b57",
                          row_switch)
        row.resize(340, 56)
        row.show()
        pump(app, 60)
        QTest.mouseClick(row.title_label, Qt.LeftButton, Qt.NoModifier,
                         QPoint(6, 6))
        pump(app, 80)
        check("clicking the row label toggles the switch",
              row_switch.isChecked())
        check("the row exposes its description label",
              row.description_label is not None)
        row.close()

        print("\nhover fills keep their translucent alpha")
        from PySide6.QtGui import QImage, QPainter
        from ui.widgets.buttons import CaptionButton, IconButton

        # WinUI hover tokens already carry alpha (subtle_hover is a ~6% wash).
        # Passing an absolute alpha instead of scaling it painted opaque black
        # - a huge, obvious difference from the un-hovered render.
        holder = QWidget()
        holder.resize(400, 200)

        def render(widget, point):
            image = QImage(widget.width(), widget.height(),
                           QImage.Format_ARGB32_Premultiplied)
            image.fill(Qt.transparent)
            painter = QPainter(image)
            widget.render(painter, QPoint(0, 0))
            painter.end()
            return image.pixelColor(*point)

        hover_cases = (
            ("icon button", IconButton("\u2039", 32), (16, 4)),
            ("caption button min", CaptionButton(CaptionButton.MINIMIZE), (6, 16)),
        )
        for name, widget, point in hover_cases:
            widget.setParent(holder)
            widget._hover = 0.0
            base = render(widget, point).lightness()
            widget._hover = 1.0
            hovered = render(widget, point).lightness()
            check(f"{name} hover is a subtle wash, not opaque black",
                  hovered > 20 and abs(hovered - base) < 40,
                  f"lightness {base} -> {hovered}")

        # the close button is the exception: Win11 fills it with #C42B1C
        close_btn = CaptionButton(CaptionButton.CLOSE)
        close_btn.setParent(holder)
        close_btn._hover = 1.0
        close_color = render(close_btn, (6, 16))
        check("close caption button hover uses the Win11 red",
              close_color.red() > 140 and close_color.green() < 90,
              f"{close_color.name()}")

        probe_row = SettingsRow("\u663e\u793a\u68c0\u6d4b\u6846", "", ToggleSwitch())
        probe_row.setParent(holder)
        probe_row.resize(300, 56)
        probe_row._hover = 0.0
        row_base = render(probe_row, (296, 28)).lightness()
        probe_row._hover = 1.0
        row_hovered = render(probe_row, (296, 28)).lightness()
        check("settings row hover is a subtle wash, not opaque black",
              row_hovered > 20 and abs(row_hovered - row_base) < 40,
              f"lightness {row_base} -> {row_hovered}")

        print("\nregion selector")
        from ui.selector_window import SelectorWindow
        selector = SelectorWindow({"opacity": 0.5, "border": True})
        selector.setGeometry(0, 0, 1280, 720)
        pump(app, 150)
        captured = {}
        selector.region_selected.connect(lambda r: captured.update(r))
        for kind, pos in ((QEvent.MouseButtonPress, QPointF(100, 100)),
                          (QEvent.MouseMove, QPointF(500, 300)),
                          (QEvent.MouseButtonRelease, QPointF(500, 300))):
            buttons = Qt.LeftButton if kind != QEvent.MouseMove else Qt.NoButton
            event = QMouseEvent(kind, pos, pos, Qt.LeftButton, buttons,
                                Qt.NoModifier)
            if kind == QEvent.MouseButtonPress:
                selector.mousePressEvent(event)
            elif kind == QEvent.MouseMove:
                selector.mouseMoveEvent(event)
            else:
                selector.mouseReleaseEvent(event)
        pump(app, 120)
        check("selector emits the dragged region",
              captured.get("width") == 400 and captured.get("height") == 200,
              str(captured))
        check("selector emits integer geometry (QWidget.setGeometry needs ints)",
              all(isinstance(v, int) for v in captured.values()), str(captured))

        # feed it through the real handler -> exercises RegionOverlay.setGeometry
        try:
            window._on_region_done(dict(captured))
            pump(app, 150)
            check("region handler applies the new region",
                  "400" in window.region_info.text(), window.region_info.text())
        except Exception as exc:                       # noqa: BLE001
            check("region handler applies the new region", False, repr(exc))

        cancelled = {"v": False}
        selector2 = SelectorWindow({"opacity": 0.5, "border": True})
        selector2.cancelled.connect(lambda: cancelled.update(v=True))
        selector2.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape,
                                          Qt.NoModifier))
        pump(app, 80)
        check("ESC cancels the selection", cancelled["v"])

        print("\nstyling")
        check("tooltips/scrollbars themed globally",
              "QScrollBar" in app.styleSheet())

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
