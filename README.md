# NexaTrans - 游戏屏幕实时 AI 翻译软件

## 版本 v0.2-alpha - Phase 2-A：区域内容获取与 OCR 显示

### 功能概述

NexaTrans 是一款游戏屏幕实时 AI 翻译软件。Phase 2-A 实现了从区域选择到 OCR 识别的完整闭环。

### 当前功能

- ✅ **主界面**：显示当前翻译区域的坐标和尺寸信息
- ✅ **框选区域**：点击按钮进入全屏透明覆盖模式
- ✅ **鼠标框选**：拖动鼠标选择矩形区域，实时显示选择框
- ✅ **红色边框 + 四角标记**：类似截图工具风格，醒目易用
- ✅ **深色遮罩**：降低屏幕亮度，突出选择区域
- ✅ **操作提示**：屏幕中央显示操作引导文字
- ✅ **常驻测试框**：可选在屏幕上显示所选区域的红色边框（通过复选框开关）
- ✅ **坐标归一化**：支持任意方向拖动（左上→右下、右下→左上等）
- ✅ **配置持久化**：区域配置自动保存至 `config/settings.json`
- ✅ **自动加载**：重启软件自动恢复上次选择的区域
- ✅ **异常处理**：全局异常捕获 + Qt 消息处理 + 日志记录
- ✅ **ESC 取消**：按 ESC 键取消选择，不保存更改
- ✅ **屏幕截图**：读取配置文件，截取指定区域
- ✅ **OCR 识别**：支持中英文文字识别（基于 EasyOCR）
- ✅ **测试OCR**：一键测试截图 + OCR 识别流程
- ✅ **OCR 结果显示**：在界面中显示识别出的文字
- ✅ **懒加载初始化**：OCR 模型首次使用时才加载

### 项目结构

```
NexaTrans/
├── main.py                    # 应用入口：日志系统、异常保护、初始化
├── download_model.py          # 临时脚本：预下载 EasyOCR 模型
├── ui/
│   ├── main_window.py         # 主界面：区域信息 + 框选入口 + OCR 测试
│   ├── region_overlay.py      # 常驻区域测试框（透明置顶红色边框）
│   └── selector_window.py     # 透明覆盖窗口：全屏鼠标框选交互
├── capture/
│   └── screen_capture.py      # 屏幕截图模块（PIL ImageGrab）
├── ocr/
│   ├── __init__.py
│   └── ocr_engine.py          # OCR 识别引擎（EasyOCR）
├── config/
│   ├── settings.json          # 配置文件：区域坐标 + 覆盖层设置
│   └── config_manager.py      # 配置管理器：读写 JSON 配置
├── logs/
│   └── app.log                # 运行日志（自动轮转）
├── requirements.txt           # 项目依赖
└── README.md                  # 项目说明文档
```

### 安装与运行

#### 环境要求

- Python 3.12+
- Windows 10 / Windows 11

#### 安装依赖

```bash
py -m pip install -r requirements.txt
```

#### 预下载 OCR 模型（首次使用）

```bash
py download_model.py
```

#### 运行软件

```bash
py main.py
```

### 配置文件说明

`config/settings.json`：

```json
{
    "region": {
        "x": 400,       // 区域左上角 X 坐标
        "y": 900,       // 区域左上角 Y 坐标
        "width": 500,   // 区域宽度
        "height": 80    // 区域高度
    },
    "overlay": {
        "opacity": 0.5, // 遮罩透明度
        "border": true  // 是否显示选择框边框
    }
}
```

### 技术栈

| 组件 | 技术 |
|------|------|
| 开发语言 | Python 3.14 |
| GUI 框架 | PySide6 6.11 |
| 屏幕截图 | Pillow (PIL) 12.2 |
| OCR 引擎 | EasyOCR 1.7 (Torch 2.13 + CPU) |
| 配置管理 | JSON 文件 |

### 后续计划

| Phase | 功能 | 状态 |
|-------|------|------|
| Phase 1 | 屏幕翻译区域选择 | ✅ 已完成 |
| Phase 2-A | 区域内容获取与 OCR 显示 | ✅ 已完成 |
| Phase 2-B | 实时捕获优化 | 📅 规划中 |
| Phase 3 | OCR 识别优化 | 📅 规划中 |
| Phase 4 | AI 翻译模块 | 📅 规划中 |
| Phase 5 | 翻译 Overlay 显示 | 📅 规划中 |
| Phase 6-8 | 后续功能 | 📅 规划中 |

### 更新日志

#### v0.2-alpha (2025-07-17)

**Phase 2-A：区域内容获取与 OCR 显示**

- ✨ 新增 `capture/screen_capture.py` — 基于 PIL.ImageGrab 的屏幕截图模块
- ✨ 新增 `ocr/ocr_engine.py` — 基于 EasyOCR 的文字识别引擎（中英文）
- ✨ OCR 模型懒加载，首次识别时自动初始化
- ✨ 主界面增加「测试OCR」按钮，一键完成截图→识别→显示
- ✨ 主界面增加 OCR 结果文本框，显示识别出的文字
- ✨ OCR 结果按置信度排序，高置信度文字排在前面
- ✨ 完善的异常处理：无区域提示 / 截图失败提示 / 无文字提示
- 🔧 使用 EasyOCR 替代 PaddleOCR（兼容 Python 3.14）
- 🔧 依赖升级：新增 easyocr, torch, torchvision, opencv-python-headless

#### v0.1 (2025-07-17)

**Phase 1：屏幕翻译区域选择系统**

- ✨ 实现主界面，显示当前翻译区域信息
- ✨ 实现全屏透明覆盖窗口，支持鼠标框选
- ✨ 实时矩形绘制，跟随鼠标动态更新
- ✨ 红色边框 + 四角标记，类似截图工具风格
- ✨ 深色半透明遮罩，降低屏幕亮度突出选择区域
- ✨ 选择区域尺寸实时显示
- ✨ 常驻区域测试框，勾选后在屏幕上实时显示所选区域红色边框
- ✨ 坐标归一化处理，支持任意方向拖动
- ✨ 配置持久化，自动保存和加载区域设置
- ✨ 全局异常保护与日志记录系统
- ✨ ESC 取消选择功能
- ✨ 区域过小校验（< 10px 拒绝保存）
- ✨ 多显示器支持（使用主屏幕）