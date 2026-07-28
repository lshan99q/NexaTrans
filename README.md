# NexaTrans v1.0

Screen real-time AI translation for games. Detects text on screen, recognizes it with OCR, translates via DeepSeek AI, and overlays the translation.

## Pipeline

```
Screen → DBNet++ → Mask → PP-OCRv5 → DeepSeek → Overlay
```

## Features

- One-click start: detection + OCR + translation in a single button
- DBNet++ text detection with frame-diff optimization
- PP-OCRv5 ONNX recognition with MD5 cache
- DeepSeek Chat API parallel translation
- Translation cache (persistent JSON)
- Configurable filters (confidence, aspect ratio, area)
- Click-through overlay (never blocks game input)
- All settings persisted across sessions
- Dark themed UI

## Quick Start

```bash
# Install
py -m pip install -r requirements.txt

# Set API key (create .env from .env.example)
echo DEEPSEEK_API_KEY=your_key_here > .env

# Run (no console window)
py main.pyw
```

## Requirements

- Python 3.12+
- Windows 10/11
- CUDA GPU optional

## Tech Stack

| Layer | Tech |
|-------|------|
| GUI | PySide6 |
| Detection | DBNet++ (PaddleX ONNX) |
| OCR | PP-OCRv5 (PaddleX ONNX) |
| Translation | DeepSeek Chat API |
| Image | OpenCV, NumPy |
| Screen Capture | mss |

## License

MIT
