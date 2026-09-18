# NexaTrans v1.2

Real-time AI screen translation for games. Detects, recognizes, and translates on-screen text continuously or on-demand. Supports global hotkey for one-shot translation.

```
Screen → DBNet++ → Mask → PP-OCRv5 → DeepSeek → Overlay
```

## Features

- **Continuous translation**: real-time detection + OCR + translation loop
- **One-shot translation**: translate once via button, tray menu, or global hotkey (default `Ctrl+Shift+T`)
- DBNet++ text detection with frame-diff optimization
- PP-OCRv5 ONNX recognition with MD5 cache
- DeepSeek Chat API parallel translation with persistent cache
- Click-through overlay with mask background fill
- System tray: minimize to tray, background operation, tray controls
- Global hotkey support (configurable modifier + key)
- Configurable display duration for one-shot results (1-30 seconds)
- All settings persisted across sessions
- Configurable filters and FPS slider (1-30)
- Translation count statistics
- Windows 11 Fluent UI with light / dark themes - see [UI](#ui-windows-11-fluent) below

## UI (Windows 11 Fluent)

The interface follows the Windows 11 design system (WinUI 3): Segoe UI
Variable typography, 4/8px corner radii, the Fluent control fills and strokes,
Mica-style window material and a real Win11 caption bar.

**Theme** — follows the Windows personalisation setting by default
(`AppsUseLightTheme`) and can be pinned to light or dark in Settings.  The
accent colour is read from the registry
(`HKCU\Software\Microsoft\Windows\DWM\AccentColor`), so buttons, switches,
sliders and selection frames use *your* Windows accent, with the WinUI
light/dark accent variants derived automatically.

**Controls** reproduce the WinUI specs:

| Control | Behaviour |
|---------|-----------|
| Button | control fill + darker bottom edge, crossfaded hover, dimmed label while pressed, two-tone focus rectangle |
| Accent button | accent fill with black/white label chosen by luminance |
| Toggle switch | 40x20, outlined grey knob when off, accent fill when on |
| Slider | 4px rail, accent fill, **no handle at rest**, 20px circle on hover, accent dot while dragging |
| Caption bar | 32px, vector-drawn minimise/close glyphs, `#C42B1C` close hover |
| InfoBar | slides down below the caption bar instead of a modal popup |
| Page transition | WinUI slide-up + fade (250 ms) with an eased window resize |

**Layout**

```
ui/
├── theme.py            Fluent tokens (light + dark), system theme/accent
│                       detection, global QSS, cached soft shadows
├── main_window.py      frameless Mica shell, hero card, settings cards, tray
├── selector_window.py  Snipping-Tool style region picker
├── region_overlay.py   resident accent region frame
└── widgets/            reusable Fluent components
    ├── anim.py         named-slot value animations
    ├── buttons.py      FluentButton, IconButton, CaptionButton
    ├── controls.py     ToggleSwitch, FluentSlider
    ├── containers.py   Card, SettingsRow, Divider, TitleBar, FluentStack
    └── feedback.py     InfoBar, ProgressRing, StatusBadge, MetricTile
```

`ToggleSwitch` and `FluentSlider` subclass `QCheckBox` / `QSlider`, so they keep
the standard Qt API (`isChecked`, `setChecked`, `toggled`, `value`,
`valueChanged`) and drop into existing code unchanged.  Text styling is driven
by style-sheet *roles* (`label.setProperty("role", "caption")`) rather than
inline style sheets, so switching theme restyles everything at once.

### Previewing the UI headlessly

Both tools render with the Qt `offscreen` platform, so no desktop is needed:

```bash
python tools/ui_preview.py   # every state, light + dark -> _ui_preview/*.png
python tools/ui_smoke.py     # headless checks for the UI wiring
```

### Measuring UI responsiveness

`tools/ui_perf.py` runs the real pipeline against the local PaddleX models and
reports how long the Qt event loop is blocked, using a 10 ms heartbeat - the
largest gap between two heartbeats is the worst stall the user feels.

```bash
python tools/ui_perf.py 8 --force-change --profile
```

`--force-change` defeats the frame-diff optimisation so every tick runs real
detection + OCR (the worst case: scrolling game content).  `--profile` breaks
the GUI-thread cost down per stage.

Measured on this machine (Ryzen-class CPU, ONNX Runtime 1.28, 640x200 region):

| Phase | Worst GUI stall | Event-loop heartbeats |
|-------|-----------------|-----------------------|
| idle baseline | 12 ms | 80 / 80 |
| model load (before) | **4700 ms** (frozen) | - |
| model load (after) | **170-380 ms** once | 30+ ticks during the load |
| pipeline running, inference on the GUI thread | **337 ms**, 33 stalls > 100 ms | 283 / 800 |
| pipeline running, inference on a worker thread | **18 ms**, 0 stalls > 100 ms | 799 / 800 |


## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # then add your DEEPSEEK_API_KEY
python main.pyw
```

## Requirements

- Python 3.12+
- Windows 10/11

## Tech Stack

| Layer | Tech |
|-------|------|
| GUI | PySide6 |
| Detection | DBNet++ (PaddleX ONNX) |
| OCR | PP-OCRv5 (PaddleX ONNX) |
| Translation | DeepSeek Chat API |
| Image | OpenCV, NumPy |
| Screen | mss |

## Changelog

### Fixes: responsiveness (unreleased)
- **Removed the invisible border around the window.** The panel used to be
  drawn inside a 16px transparent padding that hosted a drop shadow; that band
  was part of the window, so it swallowed clicks on whatever was behind it and
  travelled with the app when dragged.  The window rect is now exactly the
  visible UI.
- **Model loading no longer freezes the app.** `DBNetDetector` and
  `PaddleOCREngine` were built on the GUI thread (4.7 s of complete freeze on
  start-up).  Both are pure Python/ONNX with no Qt dependency, so they are now
  built on a worker thread; only the pipeline object (which owns an overlay
  widget) is created on the GUI thread afterwards.  Worst stall during loading:
  4700 ms -> 170-380 ms, and the window keeps animating and stays draggable.
- **Detection no longer blocks the GUI thread.** `detector.detect()` measured
  94 ms mean / 354 ms max per call and ran on the GUI thread every tick.
  Inference now runs on a single-worker pool and the results are applied
  through a queued Qt signal.  With inference forced on every frame: worst
  stall 337 ms -> 18 ms, event-loop heartbeats 283/800 -> 799/800, stalls over
  100 ms 33 -> 0.
- **Fixed Qt widget calls from a worker thread.** The async translation
  thread called `TextOverlay.set_trans_results()` and `_update_overlay_display()`
  directly; touching widgets outside the GUI thread is undefined behaviour and
  showed up as random freezes when a translation completed.  Both now go
  through queued signals.
- Reduced UI-side churn while translating (status badge no longer re-lays out
  when its text is unchanged, metric tiles update without animation on the
  periodic tick, status poll 500 -> 800 ms).
- Added `tools/ui_perf.py` to measure GUI stalls with the real models.

### UI: Windows 11 Fluent (unreleased)
- Replaced the neon "Aurora" skin with the Windows 11 / WinUI 3 design system
- Light **and** dark themes; follows the Windows personalisation setting by
  default, with a theme selector in Settings
- Accent colour read from the Windows registry, with automatic light/dark
  accent variants (accent buttons, switches, sliders, selection frames)
- Fluent control kit: FluentButton, CaptionButton, ToggleSwitch, FluentSlider,
  Card / SettingsRow, InfoBar, ProgressRing, StatusBadge, MetricTile
- Win11 caption bar with vector-drawn minimise/close glyphs and the
  `#C42B1C` close-button hover
- WinUI page transition (slide-up + fade) and InfoBar notifications
- Region selector restyled after the Windows 11 Snipping Tool (accent frame,
  resize handles, size chip); region overlay restyled to an accent frame
- Settings reorganised into Win11 settings cards with dividers
- Text styling now uses style-sheet roles instead of inline style sheets, so a
  theme switch restyles the whole app at once
- Fixed: one-shot display duration is now persisted (it was read but never saved)
- Fixed: selector emitted float geometry into `QWidget.setGeometry`
- Added `tools/ui_preview.py` (offscreen render, light + dark) and
  `tools/ui_smoke.py` (36 headless wiring checks)

### v1.2
- One-shot translation: button, tray menu, global hotkey (Ctrl+Shift+T)
- Configurable hotkey (modifier + key combos)
- Display duration slider for one-shot results (1-30s, auto-dismiss)
- FPS slider (1-30) in settings
- Translation count statistics
- UI layout improvements
- Settings persistence improvements

### v1.1
- System tray minimize-to-tray
- Tray controls: start/stop, show UI, quit
- Running status in tray menu

### v1.0
- Unified UI with start/stop + settings panel
- Overlay toggles (mask, green boxes, red box, OCR, translation)
- DeepSeek API key management with connectivity test
- All user preferences persisted

### v0.5
- PP-OCRv5 ONNX recognition
- OCR result overlay display
- OCR cache system

### v0.4
- DBNet++ text detection
- Mask generation & refinement
- Text box filtering

### v0.3
- Screen region capture
- DBNet++ detection framework

### v0.1
- Initial release
- Region selection overlay
