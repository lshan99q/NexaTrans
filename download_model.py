"""
临时脚本：预下载 EasyOCR 模型文件
首次使用需要联网下载，后续不需要
"""
print("正在下载 EasyOCR 模型（中英文识别）...")
print("首次下载可能需要几分钟，取决于网络速度")
print()

import easyocr
reader = easyocr.Reader(
    ['ch_sim', 'en'],
    gpu=False,
    verbose=True
)
print()
print("✅ 模型下载完成！")
print("后续启动将不再需要下载")