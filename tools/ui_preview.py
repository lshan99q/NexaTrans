# -*- coding: utf-8 -*-
"""
NexaTrans - offscreen UI preview harness (Windows 11 Fluent theme).

Renders every UI state to PNG using the Qt "offscreen" platform plugin so the
result can be reviewed - and regressions caught - without a desktop session.
Both the light and the dark theme are rendered side by side.

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

from PySide6.QtCore import QPoint, QRect, Qt                      # noqa: E402
from PySide6.QtGui import (
    QColor, QFontDatabase, QLinearGradient, QPainter, QPixmap,
)                                                                 # noqa: E402
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)                                                                 # noqa: E402

from config.config_manager import ConfigManager                   # noqa: E402
from ui.main_window import HOME_H, MainWindow                        # noqa: E402
from ui.theme import (                                            # noqa: E402
    MODE_DARK, MODE_LIGHT, apply_app_theme, qc, set_theme_mode, theme,
)
from ui.widgets import (                                          # noqa: E402
    Card, FluentButton, FluentSlider, InfoBar, LogoMark, MetricTile,
    ProgressRing, StatusBadge, ToggleSwitch,
)

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_ui_preview")

DESKTOP = {
    "dark": (QColor("#191C22"), QColor("#0A0C10")),
    "light": (QColor("#DCE3EC"), QColor("#B9C4D2")),
}


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
    for name in ("SegUIVar.ttf", "msyh.ttc", "msyhbd.ttc", "segoeui.ttf",
                 "segoeuib.ttf", "seguisym.ttf", "consola.ttf",
                 "CascadiaMono.ttf", "seguiemj.ttf"):
        path = os.path.join(font_dir, name)
        if os.path.exists(path) and QFontDatabase.addApplicationFont(path) >= 0:
            loaded.append(name)
    print(f"  fonts registered: {', '.join(loaded) if loaded else 'none'}")
    print(f"  families: {[f for f in QFontDatabase.families() if 'Variable' in f]}")


def pump(app: QApplication, ms: int) -> None:
    """Run the event loop (so animations advance) for ``ms`` milliseconds."""
    deadline = time.time() + ms / 1000.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.004)


def shoot(widget, path: str) -> None:
    """Grab ``widget`` and composite it over a desktop-like backdrop."""
    pix = widget.grab()
    canvas = QPixmap(pix.size())
    painter = QPainter(canvas)
    top, bottom = DESKTOP["dark" if theme().is_dark else "light"]
    grad = QLinearGradient(0, 0, 0, canvas.height())
    grad.setColorAt(0.0, top)
    grad.setColorAt(1.0, bottom)
    painter.fillRect(canvas.rect(), grad)
    painter.drawPixmap(0, 0, pix)
    painter.end()
    canvas.save(path)
    print(f"  saved {os.path.relpath(path, ROOT)}  "
          f"({canvas.width()}x{canvas.height()})")


class Surface(QWidget):
    """Preview scaffold painted with the current theme's window colour."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), qc(theme().window))


def make_config() -> ConfigManager:
    tmp = os.path.join(OUT, "_cfg")
    os.makedirs(tmp, exist_ok=True)
    cfg = ConfigManager(config_path=os.path.join(tmp, "settings.json"))
    cfg.save_region({"x": 53, "y": 631, "width": 677, "height": 460})
    ui = cfg.get_ui_config()
    ui.update({"fps_target": 14, "show_mask": True, "show_boxes": False,
               "once_hotkey_mod": "Ctrl", "once_hotkey_key": "A"})
    cfg.save_ui_config(ui)
    return cfg


def widget_gallery(app) -> None:
    """A sheet showing every custom control in its resting/mixed states."""
    gallery = Surface()
    gallery.setFixedSize(430, 470)
    gl = QVBoxLayout(gallery)
    gl.setContentsMargins(16, 16, 16, 16)
    gl.setSpacing(12)

    card = Card("Fluent control kit",
                "states of the Windows 11 widget set")
    row = QHBoxLayout()
    row.setSpacing(8)
    for text, variant in (("\u4e3b\u64cd\u4f5c", "accent"),
                          ("\u6b21\u8981", "standard"),
                          ("\u8f7b\u91cf", "subtle"),
                          ("\u5220\u9664", "critical")):
        b = FluentButton(text, variant, font_size=13)
        b.setMinimumHeight(32)
        row.addWidget(b)
    card.add(row)

    row2 = QHBoxLayout()
    row2.setSpacing(10)
    for state, text in (("idle", "\u5c31\u7eea"), ("running", "\u8fd0\u884c\u4e2d"),
                        ("busy", "\u52a0\u8f7d\u4e2d"), ("error", "\u5931\u8d25")):
        row2.addWidget(StatusBadge(text, state))
    row2.addStretch(1)
    card.add(row2)

    row3 = QHBoxLayout()
    row3.setSpacing(12)
    for on in (True, False):
        sw = ToggleSwitch()
        sw.setChecked(on)
        row3.addWidget(sw)
    for value in (25, 65, 90):
        sl = FluentSlider(0, 100, value)
        sl.setFixedWidth(84)
        row3.addWidget(sl)
    ring = ProgressRing(18)
    ring.show()
    row3.addWidget(ring)
    row3.addStretch(1)
    card.add(row3)
    gl.addWidget(card)

    from ui.widgets.containers import SettingsRow
    hover_card = Card("Settings rows")
    normal_row = SettingsRow("\u663e\u793a\u68c0\u6d4b\u6846",
                             "\u6807\u51fa\u68c0\u6d4b\u5230\u7684\u6587\u5b57\u4f4d\u7f6e",
                             ToggleSwitch())
    hovered_row = SettingsRow("\u663e\u793a\u533a\u57df\u8fb9\u6846",
                              "\u6807\u51fa\u5f53\u524d\u7ffb\u8bd1\u533a\u57df\u7684\u8303\u56f4",
                              ToggleSwitch())
    hovered_row._hover = 1.0          # simulate the pointer being over the row
    hover_card.add(normal_row)
    hover_card.add(hovered_row)
    gl.addWidget(hover_card)

    stats = QHBoxLayout()
    stats.setSpacing(8)
    for cap, val in (("FPS", "58"), ("\u8bc6\u522b\u6846", "12"),
                     ("\u7ffb\u8bd1\u6b21\u6570", "37")):
        stats.addWidget(MetricTile(cap, val), 1)
    gl.addLayout(stats)
    gl.addStretch(1)
    gallery.show()
    pump(app, 250)
    shoot(gallery, os.path.join(OUT, "gallery.png"))
    gallery.close()


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    app = QApplication(sys.argv)
    register_fonts()
    apply_app_theme(app, MODE_DARK)

    config = make_config()
    window = MainWindow(config)
    window.show()
    pump(app, 450)

    for mode in (MODE_DARK, MODE_LIGHT):
        set_theme_mode(mode, app)
        window._settings_visible = False
        window.stack.setCurrentIndex(0, False)
        window.setFixedHeight(HOME_H)
        window.settings_btn.setText("\u8bbe\u7f6e")
        pump(app, 300)
        print(f"\n[{mode}]")
        shoot(window, os.path.join(OUT, f"home_{mode}.png"))

        # running state
        window.start_btn.setText("\u505c\u6b62\u7ffb\u8bd1")
        window.start_btn.set_variant("standard")
        window.status_badge.set_state("\u8fd0\u884c\u4e2d", "running")
        window.region_btn.setEnabled(False)
        window._chip_fps.set_value(58, animate_change=False)
        window._chip_boxes.set_value(12, animate_change=False)
        window._chip_trans.set_value(37, animate_change=False)
        pump(app, 220)
        shoot(window, os.path.join(OUT, f"home_running_{mode}.png"))

        window._notify("\u7ffb\u8bd1\u5b8c\u6210\uff0c12 \u6761\u7ed3\u679c",
                       "success", 60000)
        pump(app, 420)
        shoot(window, os.path.join(OUT, f"infobar_{mode}.png"))

        # reset + settings page
        window.start_btn.setText("\u5f00\u59cb\u7ffb\u8bd1")
        window.start_btn.set_variant("accent")
        window.status_badge.set_state("\u5c31\u7eea", "idle")
        window.region_btn.setEnabled(True)
        window._chip_fps.set_value(0, animate_change=False)
        window._chip_boxes.set_value(0, animate_change=False)
        window._chip_trans.set_value(0, animate_change=False)
        window._on_toggle_settings()
        pump(app, 900)
        shoot(window, os.path.join(OUT, f"settings_{mode}.png"))

        window._on_toggle_settings()
        pump(app, 700)

    widget_gallery(app)

    from ui.selector_window import SelectorWindow
    for mode in (MODE_DARK, MODE_LIGHT):
        set_theme_mode(mode, app)
        sel = SelectorWindow({"opacity": 0.5, "border": True})
        sel.setGeometry(QRect(0, 0, 1280, 720))
        pump(app, 250)
        shoot(sel, os.path.join(OUT, f"selector_idle_{mode}.png"))

        sel._start_point = QPoint(340, 220)
        sel._end_point = QPoint(940, 470)
        sel._is_selecting = True
        pump(app, 250)
        shoot(sel, os.path.join(OUT, f"selector_drag_{mode}.png"))
        sel.close()

        from ui.region_overlay import RegionOverlay
        ov = RegionOverlay()
        ov.update_region({"x": 0, "y": 0, "width": 677, "height": 300})
        ov.set_test_visible(True)
        pump(app, 500)
        shoot(ov, os.path.join(OUT, f"region_overlay_{mode}.png"))
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
