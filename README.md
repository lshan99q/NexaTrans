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
- Dark themed Chinese UI

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
