# -*- mode: python ; coding: utf-8 -*-
"""NexaTrans PyInstaller spec - onedir build for installer packaging."""

import os
from PyInstaller.utils.hooks import collect_all

project_dir = r"D:\Desktop\NexaTrans-0.1"

# Collect everything from the heavy AI/runtime packages (proven to work).
paddlex_binaries, paddlex_datas, paddlex_hidden = collect_all("paddlex")
paddleocr_binaries, paddleocr_datas, paddleocr_hidden = collect_all("paddleocr")
onnx_binaries, onnx_datas, onnx_hidden = collect_all("onnxruntime")
pypdfium2_binaries, pypdfium2_datas, pypdfium2_hidden = collect_all("pypdfium2")
modelscope_binaries, modelscope_datas, modelscope_hidden = collect_all("modelscope")
aistudio_binaries, aistudio_datas, aistudio_hidden = collect_all("aistudio_sdk")
pyclipper_binaries, pyclipper_datas, pyclipper_hidden = collect_all("pyclipper")
shapely_binaries, shapely_datas, shapely_hidden = collect_all("shapely")

# opencv-contrib-python: only package its .dist-info so paddlex metadata check passes
# (cv2 modules already provided by opencv-python, avoid conflicts)
from importlib.metadata import distribution as _dist
_opencv_contrib_distinfo = str(_dist("opencv-contrib-python")._path)
_opencv_contrib_base = os.path.basename(_opencv_contrib_distinfo)

datas = [
    (os.path.join(project_dir, "config"), "config"),
    (os.path.join(project_dir, "models"), "models"),
    (_opencv_contrib_distinfo, _opencv_contrib_base),
]
datas.extend(paddlex_datas)
datas.extend(paddleocr_datas)
datas.extend(onnx_datas)
datas.extend(pypdfium2_datas)
datas.extend(modelscope_datas)
datas.extend(aistudio_datas)
datas.extend(pyclipper_datas)
datas.extend(shapely_datas)

binaries = []
binaries.extend(paddlex_binaries)
binaries.extend(paddleocr_binaries)
binaries.extend(onnx_binaries)
binaries.extend(pypdfium2_binaries)
binaries.extend(modelscope_binaries)
binaries.extend(aistudio_binaries)
binaries.extend(pyclipper_binaries)
binaries.extend(shapely_binaries)

hidden_imports = [
    "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets",
    "PySide6.QtNetwork", "PySide6.QtSvg",
    "cv2", "numpy", "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
    "mss", "ctypes",
    "onnxruntime", "onnxruntime.capi",
    "paddle", "paddlex", "paddleocr",
    "paddlex.inference", "paddlex.inference.models",
    "paddlex.inference.models.text_detection",
    "paddlex.inference.models.text_recognition",
    "paddlex.inference.common",
    "config", "config.config_manager",
    "detection", "detection.dbnet_detector", "detection.detection_pipeline",
    "ocr", "ocr.paddleocr_engine", "ocr.ocr_worker", "ocr.renderer",
    "overlay", "overlay.text_overlay", "overlay.ocr_overlay",
    "screen", "screen.screenshot",
    "text_processing", "text_processing.mask_generator",
    "text_processing.mask_refiner", "text_processing.text_merger",
    "text_processing.crop_processor", "text_processing.layout_analyzer",
    "translation", "translation.deepseek_client",
    "translation.translation_manager", "translation.translation_worker",
    "translation.cache",
    "ui", "ui.main_window", "ui.selector_window", "ui.region_overlay",
]
hidden_imports.extend(paddlex_hidden)
hidden_imports.extend(paddleocr_hidden)
hidden_imports.extend(onnx_hidden)
hidden_imports.extend(pypdfium2_hidden)
hidden_imports.extend(modelscope_hidden)
hidden_imports.extend(aistudio_hidden)
hidden_imports.extend(pyclipper_hidden)
hidden_imports.extend(shapely_hidden)

a = Analysis(
    [os.path.join(project_dir, "main.pyw")],
    pathex=[project_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "jedi", "tensorboard"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NexaTrans",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="NexaTrans",
)
