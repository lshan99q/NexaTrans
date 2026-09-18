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
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6.QtCore import QEvent, QPointF, Qt                        # noqa: E402
from PySide6.QtGui import QKeyEvent, QMouseEvent                      # noqa: E402
from PySide6.QtWidgets import QApplication                           # noqa: E402

from config.config_manager import ConfigManager                    # noqa: E402
from ui.main_window import MainWindow                              # noqa: E402
from ui.theme import apply_app_theme                               # noqa: E402

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
    apply_app_theme(app)

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
        check("hotkey label shows the stored hotkey",
              "T" in window._hotkey_label.text(), window._hotkey_label.text())
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

        print("\nstatus + toast")
        from ui.widgets.feedback import Toast
        window.status_pill.set_state("\u8fd0\u884c\u4e2d", "running")
        check("status pill running state",
              window.status_pill._timer.isActive())
        window.status_pill.set_state("\u5c31\u7eea", "idle")
        check("status pill idle state stops the pulse",
              not window.status_pill._timer.isActive())

        toast = Toast.push(window.shell, "\u6d4b\u8bd5\u901a\u77e5", "info", 300)
        pump(app, 200)
        check("toast is visible", toast.isVisible())
        toast.dismiss()
        pump(app, 400)
        check("toast dismissed itself", not toast.isVisible())

        window._chip_fps.set_value(42, animate_change=False)
        check("stat chip shows the new value",
              window._chip_fps._value == "42", window._chip_fps._value)

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
