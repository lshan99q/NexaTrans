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
- Animated dark UI (v2.0 "Aurora") - see [UI](#ui-v20-aurora) below

## UI (v2.0 "Aurora")

The interface was rebuilt around a small design system and an animated
component kit. All v1.2 behaviour (tray, hotkeys, pipeline, config file
format) is unchanged - only the presentation layer is new.

**Look**: frameless translucent window with a custom title bar, rounded glass
cards, a cyan/indigo gradient accent and a soft aurora glow in the corner.

**Animation**

| Element | Motion |
|---------|--------|
| Primary button | gradient hover, animated glow, press feedback, click ripple, busy spinner |
| Settings transition | pages slide horizontally; the window height eases between views |
| Settings cards | staggered fade-in on first open |
| Toggle switches | eased knob travel with a gradient track |
| Sliders | gradient fill, handle grows on hover/drag |
| Metric chips | values count up to the new number |
| Status pill | pulsing dot while detecting |
| Region selector | animated marching-ants frame, corner brackets, live size badge, crosshair + spotlight |
| Region overlay | breathing glow, marching ants, size chip |
| Notifications | toasts slide up from the bottom instead of modal popups |

**Layout**

```
ui/
├── theme.py            design tokens, global QSS, cached soft shadows
├── main_window.py      frameless shell, hero panel, settings page, tray
├── selector_window.py  full-screen region picker
├── region_overlay.py   resident region frame
└── widgets/            reusable animated components
    ├── anim.py         named-slot value animations
    ├── buttons.py      GlowButton, IconButton
    ├── controls.py     ToggleSwitch, NeonSlider
    ├── containers.py   Card, LogoMark, TitleBar, SlideStack
    └── feedback.py     StatusPill, StatChip, Toast, Spinner, form rows
```

`ToggleSwitch` and `NeonSlider` subclass `QCheckBox` / `QSlider`, so they keep
the standard Qt API (`isChecked`, `setChecked`, `toggled`, `value`,
`valueChanged`) and drop into existing code unchanged.

### Previewing the UI headlessly

Both tools render with the Qt `offscreen` platform, so no desktop is needed:

```bash
python tools/ui_preview.py   # renders every state to _ui_preview/*.png
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

### v2.0 UI "Aurora" (unreleased)
- New design system (`ui/theme.py`) + reusable animated widget kit (`ui/widgets/`)
- Frameless translucent window with custom title bar, glass cards and gradient accents
- Animated page transition between the home and settings views, with an eased window resize
- Staggered card reveal, animated toggles/sliders, counting metric chips, pulsing status dot
- Toast notifications replace several modal dialogs
- Modernized region selector (marching ants, corner brackets, size badge) and region overlay
- Fixed: one-shot display duration is now persisted (it was read but never saved)

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
