# NexaTrans - Game Screen Real-time AI Translation Software

## Version v0.4 - Stage 4: Text Region Refinement & OCR Preparation

### Overview

NexaTrans is a game screen real-time AI translation tool.

- **Stage 1**: Screen translation region selection system ✅
- **Stage 2**: Screen region screenshot system ✅
- **Stage 3**: DBNet++ text detection with overlay ✅
- **Stage 4**: Text mask generation, refinement, merging & filtering ✅ ← Current

### Current Features

- ✅ **Main Interface**: Displays current translation region coordinates and dimensions
- ✅ **Region Selection**: Full-screen transparent overlay for mouse-based region selection
- ✅ **Red Border + Corner Markers**: Screenshot-tool style visual feedback
- ✅ **Dark Overlay**: Reduces screen brightness to highlight selected region
- ✅ **Operation Hints**: On-screen guidance text
- ✅ **Persistent Test Box**: Optional always-on red border overlay for selected region
- ✅ **Coordinate Normalization**: Supports arbitrary drag directions
- ✅ **Config Persistence**: Auto-saves region config to `config/settings.json`
- ✅ **Auto Load**: Restores last selected region on restart
- ✅ **Exception Handling**: Global exception capture + Qt message handling + logging
- ✅ **ESC Cancel**: Press ESC to cancel selection without saving
- ✅ **DBNet++ Text Detection**: Auto-detect text regions in selected area
- ✅ **Multi-box Overlay**: Simultaneous display of all detected text regions
- ✅ **Screen Coordinate Conversion**: Local detection coords → absolute screen coords
- ✅ **Real-time Detection Loop**: Configurable FPS target (default 15 FPS), frame-diff optimization
- ✅ **GPU Inference**: CUDA acceleration when available, CPU fallback
- ✅ **Text Mask Generation**: Polygon-to-pixel mask generation via OpenCV
- ✅ **Mask Refinement**: Dilation + Gaussian blur for clean text masks
- ✅ **Smart Background Color**: Mask color auto-matches text background
- ✅ **Icon/UI Filtering**: Adjustable filters to exclude non-text UI elements
- ✅ **Text Merging**: Merge adjacent text boxes into logical groups
- ✅ **Crop Processing**: Generate OCR-ready text region crops
- ✅ **Layout Analysis**: Horizontal/vertical text direction detection
- ✅ **Filter Parameter UI**: Real-time adjustable confidence, aspect ratio, and area filters
- ✅ **Screenshot Preview**: Visual verification of captured region
- ✅ **Chinese UI**: Fully localized interface

### Project Structure

```
NexaTrans/
├── main.py                    # Application entry: logging, exceptions, initialization
├── ui/
│   ├── main_window.py         # Main interface + detection controls + filter sliders
│   ├── region_overlay.py      # Persistent region test box (red border)
│   └── selector_window.py     # Transparent full-screen region selector
├── config/
│   ├── settings.json          # Config file: region coords + text processing params
│   └── config_manager.py      # Config manager: JSON read/write
├── screen/
│   ├── __init__.py
│   └── screenshot.py          # Screen region capture (mss / PIL backend)
├── detection/
│   ├── __init__.py
│   ├── dbnet_detector.py      # DBNet++ model loading + text detection
│   └── detection_pipeline.py  # Screenshot → detect → transform → mask → overlay loop
├── text_processing/
│   ├── __init__.py
│   ├── mask_generator.py      # Polygon to pixel mask conversion
│   ├── mask_refiner.py        # Dilation + Gaussian blur optimization
│   ├── text_merger.py         # Adjacent text box merging
│   ├── crop_processor.py      # OCR input crop generation
│   └── layout_analyzer.py     # Reading direction analysis
├── overlay/
│   ├── __init__.py
│   └── text_overlay.py        # Always-on-top detection box + mask overlay
├── models/
│   └── dbnet/                 # Custom model files (optional)
├── logs/
│   └── app.log                # Runtime log (auto-rotating)
├── requirements.txt           # Project dependencies
└── README.md                  # Project documentation
```

### Installation & Running

#### Requirements

- Python 3.12+
- Windows 10 / Windows 11
- CUDA-capable GPU (optional, for GPU inference)

#### Install Dependencies

```bash
py -m pip install -r requirements.txt
```

> **Note**: PaddlePaddle with CUDA support requires additional setup. See [PaddlePaddle Installation Guide](https://www.paddlepaddle.org.cn/install/quick).
> For CPU-only inference, replace `paddlepaddle` with `paddlepaddle-cpu` in requirements.txt.

#### Run

```bash
py main.py
```

### Config File

`config/settings.json`:

```json
{
    "region": {
        "x": 400,
        "y": 900,
        "width": 500,
        "height": 80
    },
    "overlay": {
        "opacity": 0.5,
        "border": true
    },
    "text_processing": {
        "dilate_size": 5,
        "blur_size": 3,
        "merge_distance": 20,
        "height_ratio": 0.6,
        "crop_padding": 2,
        "min_confidence": 0.5,
        "min_text_aspect": 1.8,
        "max_icon_aspect": 1.4,
        "min_area_ratio": 0.005
    }
}
```

### Usage

1. **Select Region**: Click "框选区域" and drag to select a translation area
2. **Verify Region**: Enable "显示红框" to see the red border, or click "截图预览"
3. **Adjust Filters**: Use sliders to tune confidence, aspect ratio, and icon filtering
4. **Start Detection**: Click "开始检测" to begin DBNet++ text detection
5. **Enable Mask**: Toggle "显示Mask" to overlay colored masks on detected text
6. **Stop Detection**: Click "停止检测" to end the detection loop

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| GUI Framework | PySide6 |
| Config Management | JSON |
| Text Detection | DBNet++ (via PaddleOCR) |
| OCR Engine | PaddleOCR |
| Image Processing | OpenCV, NumPy |
| Morphological Processing | cv2.dilate, cv2.fillPoly, GaussianBlur |
| Mask Generation | OpenCV polygon rasterization |
| Screen Capture | mss |
| GPU Acceleration | CUDA (optional) |

### Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| Stage 1 | Screen region selection | ✅ Completed |
| Stage 2 | Screen capture | ✅ Completed |
| Stage 3 | DBNet++ text detection | ✅ Completed |
| Stage 4 | Text mask & region refinement | ✅ Completed |
| Stage 5 | OCR text recognition | 📋 Planned |
| Stage 6 | AI translation | 📋 Planned |
| Stage 7 | Translation overlay rendering | 📋 Planned |

### Changelog

#### v0.4 (2026-07-28)

**Stage 4: Text Region Refinement & OCR Preparation**

- ✅ Polygon-to-pixel mask generation (OpenCV fillPoly)
- ✅ Mask dilation + Gaussian blur for clean edges
- ✅ Smart background color sampling for mask fill
- ✅ Icon/UI element filtering (adjustable aspect ratio + confidence)
- ✅ Text box merging for adjacent regions
- ✅ OCR crop output generation
- ✅ Layout direction analysis (horizontal/vertical)
- ✅ Real-time filter parameter adjustment UI
- ✅ Frame-diff optimization (skip re-detection on static frames)
- ✅ Mask overlay flicker-free rendering
- ✅ Screenshot preview for region verification
- ✅ Fully Chinese UI with no garbled text

#### v0.3 (2026-07-27)

**Stage 3: DBNet++ Text Detection**

- ✅ DBNet++ text detection via PaddleOCR
- ✅ Automatic screen text region detection
- ✅ Detection box overlay display
- ✅ Screen coordinate transformation
- ✅ Real-time detection pipeline (target 15 FPS)
- ✅ GPU inference support (CUDA)
- ✅ Multi-box simultaneous display
- ✅ Model loaded once, reused across frames
- ✅ Error handling: model missing, detection failure, screenshot failure

#### v0.1 (2025-07-17)

**Stage 1: Region Selection System**

- ✅ Main interface with region info display
- ✅ Full-screen transparent overlay selection
- ✅ Real-time rectangle drawing
- ✅ Red border + corner markers
- ✅ Dark semi-transparent overlay
- ✅ Size tag display
- ✅ Coordinate normalization
- ✅ Config persistence
- ✅ Global exception handling + logging
- ✅ ESC cancel
- ✅ Minimum region validation (10px)
- ✅ Multi-monitor support (primary screen)