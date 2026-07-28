# NexaTrans - Game Screen Real-time AI Translation Software

## Version v0.6 - Stage 6: AI Multi-Region Translation

### Overview

NexaTrans is a game screen real-time AI translation tool.

- **Stage 1**: Screen translation region selection system ✅
- **Stage 2**: Screen region screenshot system ✅
- **Stage 3**: DBNet++ text detection with overlay ✅
- **Stage 4**: Text mask generation, refinement, merging & filtering ✅
- **Stage 5**: PP-OCRv5 text recognition & overlay display ✅
- **Stage 6**: DeepSeek AI translation & parallel processing ✅ ← Current

### Full Pipeline

```
Screen → DBNet++ → Mask → PP-OCRv5 → DeepSeek → Translation Overlay
```

### Current Features

- ✅ **Main Interface**: Region info, detection controls, filter sliders, OCR & translation toggles
- ✅ **Region Selection**: Full-screen transparent overlay for mouse-based selection
- ✅ **DBNet++ Text Detection**: Auto-detect text regions, frame-diff optimization
- ✅ **Text Mask Generation**: Polygon-to-pixel mask with smart background color
- ✅ **Icon/UI Filtering**: Adjustable filters for confidence, aspect ratio, area
- ✅ **PP-OCRv5 Recognition**: ONNX-based OCR with MD5 cache
- ✅ **DeepSeek AI Translation**: Multi-region parallel translation via ThreadPoolExecutor
- ✅ **Translation Cache**: MD5-based persistent cache (translation_cache.json)
- ✅ **Translation Overlay**: Translated text displayed on screen (light blue)
- ✅ **OCR Overlay**: Recognized text displayed on screen (white)
- ✅ **API Key Security**: .env file (git-ignored), never hardcoded
- ✅ **Chinese UI**: Fully localized interface

### Project Structure

```
NexaTrans/
├── main.py                    # Entry: logging, exceptions, initialization
├── ui/
│   ├── main_window.py         # Main UI: detection, OCR, translation controls
│   ├── region_overlay.py      # Red border region overlay
│   └── selector_window.py     # Transparent full-screen region selector
├── config/
│   ├── settings.json          # Config: region, filters, OCR, translation
│   └── config_manager.py      # JSON read/write manager
├── screen/
│   └── screenshot.py          # Screen capture (mss/PIL)
├── detection/
│   ├── dbnet_detector.py      # DBNet++ ONNX detection
│   └── detection_pipeline.py  # Main loop: capture→detect→OCR→translate→overlay
├── text_processing/
│   ├── mask_generator.py      # Polygon to mask
│   ├── mask_refiner.py        # Dilation + blur
│   ├── text_merger.py         # Box merging
│   ├── crop_processor.py      # Region cropping
│   └── layout_analyzer.py     # Direction analysis
├── ocr/
│   ├── paddleocr_engine.py    # PP-OCRv5 rec engine
│   └── renderer.py            # PIL text renderer
├── translation/
│   ├── deepseek_client.py     # DeepSeek Chat API wrapper
│   ├── translation_manager.py # Parallel translation orchestrator
│   └── cache.py               # MD5 translation cache
├── overlay/
│   └── text_overlay.py        # Detection boxes + masks + OCR + translation
├── .env.example               # API key template (committed)
├── .env                       # Your API key (git-ignored)
├── .gitignore
├── requirements.txt
└── README.md
```

### Setup

#### Requirements

- Python 3.12+
- Windows 10 / 11
- CUDA GPU (optional)

#### Install

```bash
py -m pip install -r requirements.txt
```

#### API Key

Copy `.env.example` to `.env` and add your DeepSeek API key:

```
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

Get a key at: https://platform.deepseek.com

#### Run

```bash
py main.py
```

### Usage

1. **Select Region**: Click "框选区域" and drag
2. **Verify**: "显示红框" or "截图预览"
3. **Start Detection**: Click "开始检测"
4. **Enable OCR**: Toggle "启用OCR" for text recognition
5. **Enable Translation**: Toggle "启用翻译" for AI translation
6. **View Results**: Translation appears in blue on overlay and in results panel
7. **Adjust Filters**: Tune confidence/aspect/area filters as needed

### Tech Stack

| Component | Technology |
|-----------|-----------|
| GUI | PySide6 |
| Detection | DBNet++ (PaddleX ONNX) |
| OCR | PP-OCRv5 (PaddleX ONNX) |
| Translation | DeepSeek Chat API |
| Image | OpenCV, NumPy, PIL |
| Screen | mss |
| GPU | CUDA (optional) |

### Roadmap

| Stage | Feature | Status |
|-------|---------|--------|
| Stage 1 | Region selection | ✅ |
| Stage 2 | Screen capture | ✅ |
| Stage 3 | DBNet++ detection | ✅ |
| Stage 4 | Text mask & refinement | ✅ |
| Stage 5 | OCR recognition | ✅ |
| Stage 6 | AI translation | ✅ |
| Stage 7 | Text rendering & typesetting | 📋 |

### Changelog

#### v0.6 (2026-07-28)

**Stage 6: AI Multi-Region Translation**

- ✅ DeepSeek Chat API integration (urllib, no extra deps)
- ✅ Multi-region parallel translation (ThreadPoolExecutor)
- ✅ MD5-based persistent translation cache
- ✅ Translation overlay (light blue text on screen)
- ✅ UI translation toggle
- ✅ .env API key management (git-ignored)
- ✅ OCR→Translate→Overlay full pipeline

#### v0.5 (2026-07-28)

- ✅ PP-OCRv5 mobile rec model
- ✅ Inline OCR with MD5 cache
- ✅ OCR text overlay (white text)

#### v0.4 (2026-07-28)

- ✅ Mask generation, refinement, merging
- ✅ Icon/UI filtering, frame-diff optimization

#### v0.3 (2026-07-27)

- ✅ DBNet++ text detection, overlay, GPU inference

#### v0.1 (2025-07-17)

- ✅ Region selection, config persistence, logging
