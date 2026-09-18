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
