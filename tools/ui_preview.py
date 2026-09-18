# -*- coding: utf-8 -*-
"""
NexaTrans - offscreen UI preview harness.

Renders every UI state to PNG using the Qt "offscreen" platform plugin, so
the visual result can be reviewed (and regressions caught) without a real
desktop session.

Usage:
    python tools/ui_preview.py [output_dir]
"""

import os
import sys
import time
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PySide6.QtCore import QRect, Qt, QTimer                     # noqa: E402
from PySide6.QtGui import (
    QColor, QFontDatabase, QLinearGradient, QPainter, QPixmap,
)                                                                # noqa: E402
from PySide6.QtWidgets import QApplication                       # noqa: E402

from config.config_manager import ConfigManager                  # noqa: E402
from ui.main_window import MainWindow, SHADOW_PAD                # noqa: E402
from ui.theme import apply_app_theme                             # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_ui_preview")
DESKTOP_TOP = QColor("#232C3D")
DESKTOP_BOTTOM = QColor("#0C1017")


def pump(app: QApplication, ms: int) -> None:
    """Run the event loop (so animations advance) for ``ms`` milliseconds."""
    deadline = time.time() + ms / 1000.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.004)


def shoot(widget, path: str, margin: int = 0) -> None:
    """Grab ``widget`` and composite it over a desktop-like backdrop."""
    pix = widget.grab()
    canvas = QPixmap(pix.width() + margin * 2, pix.height() + margin * 2)
    painter = QPainter(canvas)
    grad = QLinearGradient(0, 0, 0, canvas.height())
    grad.setColorAt(0.0, DESKTOP_TOP)
    grad.setColorAt(1.0, DESKTOP_BOTTOM)
    painter.fillRect(canvas.rect(), grad)
    painter.drawPixmap(margin, margin, pix)
    painter.end()
    canvas.save(path)
    print(f"  saved {os.path.relpath(path, ROOT)}  "
          f"({canvas.width()}x{canvas.height()})")


def register_fonts() -> None:
    """
    The Qt "offscreen" plugin ships no font database, which would render every
    label as tofu.  Load the real Windows fonts explicitly so the preview
    matches what the application shows on a normal desktop.
    """
    windir = os.environ.get("WINDIR", r"C:\Windows")
    font_dir = os.path.join(windir, "Fonts")
    if not os.path.isdir(font_dir):
        print("  ! no system font dir - text may render as boxes")
        return
    os.environ.setdefault("QT_QPA_FONTDIR", font_dir)
    loaded = []
    for name in ("msyh.ttc", "msyhbd.ttc", "msyhl.ttc", "segoeui.ttf",
                 "segoeuib.ttf", "seguisym.ttf", "consola.ttf",
                 "CascadiaMono.ttf", "CascadiaCode.ttf", "seguiemj.ttf"):
        path = os.path.join(font_dir, name)
        if os.path.exists(path) and QFontDatabase.addApplicationFont(path) >= 0:
            loaded.append(name)
    print(f"  fonts registered: {', '.join(loaded) if loaded else 'none'}")


def make_config() -> ConfigManager:
    tmp = os.path.join(OUT, "_cfg")
    os.makedirs(tmp, exist_ok=True)
    cfg_path = os.path.join(tmp, "settings.json")
    cfg = ConfigManager(config_path=cfg_path)
    cfg.save_region({"x": 53, "y": 631, "width": 677, "height": 460})
    ui = cfg.get_ui_config()
    ui.update({"fps_target": 14, "show_mask": True, "show_boxes": False,
               "once_hotkey_mod": "Ctrl", "once_hotkey_key": "A"})
    cfg.save_ui_config(ui)
    return cfg


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    app = QApplication(sys.argv)
    register_fonts()
    apply_app_theme(app)

    print("building MainWindow ...")
    window = MainWindow(make_config())
    window.show()
    pump(app, 500)

    print("rendering states ...")
    shoot(window, os.path.join(OUT, "01_home.png"), margin=0)

    # ---- running state -------------------------------------------------
    window.start_btn.setText("\u505c\u6b62\u7ffb\u8bd1")
    window.start_btn.set_variant("danger")
    window.hero.set_active(True)
    window.status_pill.set_state("\u9759\u6001 \u8bc6\u522b\u4e2d", "running")
    window.region_btn.setEnabled(False)
    window._chip_fps.set_value(58, animate_change=False)
    window._chip_boxes.set_value(12, animate_change=False)
    window._chip_trans.set_value(37, animate_change=False)
    pump(app, 220)
    shoot(window, os.path.join(OUT, "02_home_running.png"))

    # ---- toast ---------------------------------------------------------
    from ui.widgets.feedback import Toast
    Toast.push(window.shell, "\u2713  \u7ffb\u8bd1\u5b8c\u6210\uff0c12 \u6761\u7ed3\u679c",
               "success", 60000)
    pump(app, 420)
    shoot(window, os.path.join(OUT, "03_toast.png"))

    # ---- settings ------------------------------------------------------
    window._on_toggle_settings()
    pump(app, 900)
    shoot(window, os.path.join(OUT, "04_settings.png"))

    # scrolled to the bottom
    scroll = window.stack.currentWidget().findChild(
        __import__("PySide6.QtWidgets", fromlist=["QScrollArea"]).QScrollArea)
    if scroll is not None:
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        pump(app, 250)
        shoot(window, os.path.join(OUT, "05_settings_bottom.png"))

    # ---- widget gallery (states / hovers) ------------------------------
    from ui.widgets import (Card, GlowButton, NeonSlider, StatChip,  # noqa
                            StatusPill, ToggleSwitch, ui_font)
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

    gallery = QWidget()
    gallery.setFixedSize(430, 330)
    gl = QVBoxLayout(gallery)
    gl.setContentsMargins(18, 18, 18, 18)
    gl.setSpacing(12)

    card = Card("Widget gallery", "states of the Aurora component kit",
                icon="\u25c8", accent="#38BDF8")
    row = QHBoxLayout()
    for text, variant in (("\u4e3b\u64cd\u4f5c", "primary"),
                          ("\u526f\u64cd\u4f5c", "accent"),
                          ("\u505c\u6b62", "danger"),
                          ("\u5b8c\u6210", "success")):
        b = GlowButton(text, variant, font_size=12)
        b.setMinimumHeight(38)
        row.addWidget(b)
    card.add(row)

    row2 = QHBoxLayout()
    for state, text in (("idle", "\u5c31\u7eea"), ("running", "\u8fd0\u884c\u4e2d"),
                        ("busy", "\u52a0\u8f7d\u4e2d"), ("error", "\u5931\u8d25")):
        row2.addWidget(StatusPill(text, state))
    row2.addStretch(1)
    card.add(row2)

    row3 = QHBoxLayout()
    for on in (True, False):
        t = ToggleSwitch()
        t.setChecked(on)
        row3.addWidget(t)
    for v in (20, 65, 90):
        s = NeonSlider(0, 100, v)
        s.setFixedWidth(90)
        row3.addWidget(s)
    row3.addStretch(1)
    card.add(row3)
    gl.addWidget(card)

    stats = QHBoxLayout()
    stats.setSpacing(8)
    for cap, val, accent in (("FPS", "58", "#38BDF8"), ("\u8bc6\u522b\u6846", "12", "#22D3EE"),
                             ("\u7ffb\u8bd1\u6b21\u6570", "37", "#8B5CF6")):
        chip = StatChip(cap, val, accent)
        stats.addWidget(chip, 1)
    gl.addLayout(stats)
    gl.addStretch(1)
    gallery.setStyleSheet(f"background: #0B111D; border-radius: 12px;")
    gallery.show()
    pump(app, 300)
    shoot(gallery, os.path.join(OUT, "06_widgets.png"))

    # ---- selector overlay ---------------------------------------------
    from ui.selector_window import SelectorWindow
    sel = SelectorWindow({"opacity": 0.5, "border": True})
    sel.setGeometry(QRect(0, 0, 1280, 720))
    pump(app, 250)
    shoot(sel, os.path.join(OUT, "07_selector_idle.png"))

    from PySide6.QtCore import QPoint
    sel._start_point = QPoint(340, 220)
    sel._end_point = QPoint(940, 470)
    sel.update()
    pump(app, 250)
    shoot(sel, os.path.join(OUT, "08_selector_drag.png"))
    sel.close()

    # ---- region border overlay ----------------------------------------
    from ui.region_overlay import RegionOverlay
    ov = RegionOverlay()
    ov.update_region({"x": 0, "y": 0, "width": 677, "height": 300})
    ov.set_test_visible(True)
    pump(app, 700)
    shoot(ov, os.path.join(OUT, "09_region_overlay.png"))
    ov.close()

    print("\nlayout diagnostics")
    print(f"  window        : {window.width()}x{window.height()}")
    print(f"  home min hint : {window.stack._pages[0].minimumSizeHint()}")
    print(f"  settings hint : {window.stack._pages[1].minimumSizeHint()}")
    for name in ("mask_check", "boxes_check", "redbox_check", "ocr_check",
                 "trans_check"):
        t = getattr(window, name)
        print(f"  {name:<13}: checked={t.isChecked()!s:<5} knob={t._p:.2f}")
    print("done.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
