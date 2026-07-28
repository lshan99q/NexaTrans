# NexaTrans v1.1

Real-time AI screen translation for games. Detects, recognizes, and translates on-screen text with one click.

```
Screen → DBNet++ → Mask → PP-OCRv5 → DeepSeek → Overlay
```

## Features

- One-click start: detection + OCR + translation
- DBNet++ text detection with frame-diff optimization
- PP-OCRv5 ONNX recognition with MD5 cache
- DeepSeek Chat API parallel translation with persistent cache
- Click-through overlay (never blocks input)
- System tray: minimize to tray, background operation, tray controls
- All settings persisted across sessions
- Configurable filters
- Dark themed Chinese UI
- No console window (`main.pyw`)

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
