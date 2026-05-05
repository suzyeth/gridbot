# gridbot

[![tests](https://github.com/suzyeth/gridbot/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/suzyeth/gridbot/actions/workflows/test.yml)
[![python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://github.com/suzyeth/gridbot/blob/main/pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![status](https://img.shields.io/badge/status-alpha-orange)](#%E7%8A%B6%E6%80%81)

[English README](./README.md)

**黑盒 Android 自动化工具包。** 用 ADB 截屏、发点击/滑动、用 OCR 识别屏幕上的文字驱动 UI——
不读 app 内部、不打桩、不需要 root。

```python
from gridbot import AdbCapture, AdbInput, OcrEngine

cap = AdbCapture()
inp = AdbInput()
ocr = OcrEngine.get(fast=True)

img = cap.screenshot()
btn = ocr.find_text(img, "设置")
if btn:
    inp.tap(*btn.center)
```

整个项目的核心思路就这几行。

## 适合什么场景

- 你想自动化一个**改不了源码的第三方 Android app 或游戏**。
- OCR + ADB 比 UIAutomator / Appium 更合适——大部分游戏用自定义渲染引擎，标准的 view 树检查拿不到东西。
- 能接受"看人眼看到的东西"这种黑盒方式：像素进，点击出。

## 不适合什么场景

- App 是你自己写的——用 Espresso / UIAutomator / Appium 测试更干净。
- 需要毫秒级时序——OCR 每次查询要 50–500ms。
- 要测 iOS——这个工具只支持 ADB。

## 安装

> ⚠️ **Alpha 阶段，还没上 PyPI。** 0.1.x 之间公共 API 可能变。等 v0.2 上 PyPI 后规范命令就是 `pip install gridbot[ocr]`，目前先从本仓库直接装。

**从 clone 装**（如果想跑自带的 example，推荐这种）：

```bash
git clone https://github.com/suzyeth/gridbot
cd gridbot
pip install -e ".[ocr]"
```

**不 clone 直接装**：

```bash
pip install "gridbot[ocr] @ git+https://github.com/suzyeth/gridbot.git"
```

`[ocr]` 这部分把 PaddleOCR 装上（加模型缓存 ~500MB）。如果只需要 capture / input / recorder 层，去掉它：

```bash
pip install "gridbot @ git+https://github.com/suzyeth/gridbot.git"
```

> 🐍 **Python 3.13 备注。** PaddlePaddle 出新 Python 版本的 wheel 比 CPython 慢一拍。如果 3.13 上 `pip install gridbot[ocr]` 失败，先退到 3.12。不带 OCR 的安装（`pip install gridbot`）在 3.9+ 全部可用。

还需要 **`adb`** 二进制。两条路：

- 装 Android platform-tools，把 `adb` 加进 `PATH`；**或**
- 设环境变量 `GRIDBOT_ADB_PATH` 指到 adb 路径：
  ```bash
  export GRIDBOT_ADB_PATH=/path/to/adb            # macOS / Linux
  set    GRIDBOT_ADB_PATH=D:\LDPlayer\adb.exe     # Windows cmd
  $env:GRIDBOT_ADB_PATH = "D:\LDPlayer\adb.exe"   # Windows PowerShell
  ```

跑 `adb devices` 能看到一台 `device` 状态的设备就行。

或者用自带的 CLI 一键体检：

```bash
gridbot doctor
```

会逐项检查 Python 版本、必装依赖、可选 OCR 依赖、PaddleOCR 模型缓存、adb 二进制、连上的设备——每一项失败都给出具体修复命令。

## 首次运行的几件事

不踩一次坑就不知道：

- **OCR 模型懒加载**——首次调用从 PaddleOCR CDN 下载 ~30MB 到 `~/.paddlex/official_models/`。装完后跑一次 `gridbot warmup` 提前下好，网络受限的环境特别有用。
- **Linux + USB 真机** 需要 udev 规则，否则非 root 用户访问不了。按 Android [官方指南](https://developer.android.com/studio/run/device.html#setting-up) 写到 `/etc/udev/rules.d/51-android.rules`。模拟器没这个问题。
- **连了多台设备？** `AdbCapture` / `AdbInput` / `ScreenRecorder` 默认挑第一台 `device` 状态的。要锁定某一台传 `serial="..."` 或 `--serial ...`。
- **OCR 语言** 默认 `"ch"`——PaddleOCR 的全能模型，简繁中文 + 英文一把抓。其它语言给 `OcrEngine.get` 传 `lang="en"` / `"ja"` / `"ko"` 等，或者 CLI 用 `gridbot ocr --lang en`。

## CLI 快速参考

`pip install` 之后 `gridbot` 命令就在 PATH 里了：

```bash
gridbot doctor                                # 体检（不需要设备）
gridbot devices                               # 列出连上的设备
gridbot screenshot ./shot.png                 # 截一张
gridbot ocr ./shot.png --fast                 # OCR 一张本地图（默认 lang=ch）
gridbot ocr ./shot.png --lang en              # 纯英文 OCR
gridbot ocr ./shot.png --save-annotated       # 加画检测框
gridbot watch --interval 2                    # 实时截屏 + OCR 循环
gridbot warmup                                # 提前下载 OCR 模型
```

装完先验证、写代码前先扫屏，都不用打开编辑器。

## 快速上手

```python
from gridbot import AdbCapture, AdbInput, OcrEngine

cap = AdbCapture()             # 自动选第一台连上的设备
inp = AdbInput()
ocr = OcrEngine.get(fast=True) # mobile 模型——更快，精度略低

# 1) 截屏
img = cap.screenshot()                          # BGR ndarray
cap.screenshot_to_file("debug.png")             # 顺便存盘

# 2) 把屏幕上所有文字读出来
results = ocr.read(img)
for r in results:
    print(f"{r.text!r}  置信度={r.confidence:.2f}  中心={r.center}")

# 3) 找指定按钮然后点它
btn = ocr.find_text(img, "设置", results=results)
if btn:
    inp.tap(*btn.center)

# 4) 或者只 OCR 某一块区域，速度更快
header = ocr.read_region(img, 0, 0, img.shape[1], 200)
```

完整可运行版本见 [`examples/01_hello_world/`](./examples/01_hello_world/)。

## 公共 API

| 符号 | 作用 |
|---|---|
| `AdbCapture(serial=None, *, adb_path=None)` | ADB 截屏。 |
| `AdbCapture.screenshot()` | 返回一帧 BGR ndarray。 |
| `AdbCapture.screenshot_to_file(path=None)` | 同上 + 存 PNG。 |
| `AdbInput(serial=None, *, adb_path=None)` | 发输入事件。 |
| `AdbInput.tap(x, y)` | 单击。 |
| `AdbInput.swipe(x1, y1, x2, y2, duration_ms=300)` | 拖动 / 滑动。 |
| `AdbInput.long_press(x, y, duration_ms=1000)` | 长按。 |
| `AdbInput.keyevent(code)` / `back()` / `home()` | 硬件键。 |
| `AdbInput.text(content)` | 输入 ASCII（不支持中文 / emoji）。 |
| `OcrEngine.get(lang="ch", fast=False)` | 拿缓存的 PaddleOCR 引擎。 |
| `OcrEngine.read(image)` | 全图 OCR。 |
| `OcrEngine.read_region(image, x1, y1, x2, y2)` | 裁剪 OCR（快 5–10 倍）。 |
| `OcrEngine.find_text(image, keyword, *, results=None, ...)` | 找第一个匹配。 |
| `OcrEngine.find_all_texts(...)` | 找所有匹配。 |
| `OcrResult.text / .confidence / .center / .rect` | 检测结果。 |
| `draw_results(image, results)` | 把识别框画到图上调试用。 |

## 项目结构

```
gridbot/
├── gridbot/
│   ├── _adb.py          # adb 路径发现 + 设备列举
│   ├── capture.py       # AdbCapture
│   ├── cli.py           # `gridbot` CLI（doctor / devices / screenshot / ocr / watch）
│   ├── input.py         # AdbInput, KEY_* 常量
│   ├── navigator.py     # Navigator + screens.yaml schema（BFS 状态图驱动）
│   ├── ocr.py           # OcrEngine, OcrResult, draw_results
│   ├── recorder.py      # ScreenRecorder（阻塞 + 异步两种模式）
│   └── state.py         # StateRule, StateDetector
├── examples/
│   ├── 00_no_device/    # 拿自带图测 OCR——5 秒验证装好了
│   ├── 01_hello_world/  # 截屏 → OCR → 标注（需要真设备）
│   ├── 02_state_navigator/  # screens.yaml + StateDetector + Navigator.goto
│   └── 03_screen_recording/ # ScreenRecorder 阻塞 + 异步示例
├── tests/
├── .github/workflows/test.yml  # pytest + ruff matrix
├── pyproject.toml
└── LICENSE              # MIT
```

## 状态

**Alpha (0.1.x)。** 截屏 / 输入 / OCR 三层在一个真实下游项目里跑通过了，
state / navigator / recorder 是新加的，可能还会动。公共 API 还没锁版本，
在意的话固定一下版本号。

## 致谢

- **PaddleOCR** ([Apache-2.0](https://github.com/PaddlePaddle/PaddleOCR))，OCR 全靠它。
- 黑盒自动化思路参考了
  [BetterGI](https://github.com/babalae/better-genshin-impact) 和
  [March7thAssistant](https://github.com/moesnow/March7thAssistant)。

## License

MIT — 见 [LICENSE](./LICENSE)。
