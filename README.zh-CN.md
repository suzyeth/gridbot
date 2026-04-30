# gridbot

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

```bash
pip install gridbot[ocr]
```

`[ocr]` 这部分把 PaddleOCR 装上。PaddleOCR 很大（加模型 ~500MB），如果只需要截屏 + 输入层就跳过：

```bash
pip install gridbot
```

还需要 **`adb`** 二进制。两条路：

- 装 Android platform-tools，把 `adb` 加进 `PATH`；**或**
- 设环境变量 `GRIDBOT_ADB_PATH` 指到 adb 路径：
  ```bash
  export GRIDBOT_ADB_PATH=/path/to/adb            # macOS / Linux
  set    GRIDBOT_ADB_PATH=D:\LDPlayer\adb.exe     # Windows cmd
  $env:GRIDBOT_ADB_PATH = "D:\LDPlayer\adb.exe"   # Windows PowerShell
  ```

跑 `adb devices` 能看到一台 `device` 状态的设备就行。

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
│   ├── input.py         # AdbInput, KEY_* 常量
│   └── ocr.py           # OcrEngine, OcrResult, draw_results
├── examples/
│   └── 01_hello_world/  # 截屏 → OCR → 标注
├── tests/
├── pyproject.toml
└── LICENSE              # MIT
```

## 状态

**Alpha (0.1.x)。** 截屏 / 输入 / OCR 三层在一个真实下游项目里跑通过了，
但 API 还可能变。状态机、屏幕图、高层任务调度故意没放进来——它们属于 gridbot 之上的那一层，
游戏特定的逻辑放那里更合适。

## 致谢

- **PaddleOCR** ([Apache-2.0](https://github.com/PaddlePaddle/PaddleOCR))，OCR 全靠它。
- 黑盒自动化思路参考了
  [BetterGI](https://github.com/babalae/better-genshin-impact) 和
  [March7thAssistant](https://github.com/moesnow/March7thAssistant)。

## License

MIT — 见 [LICENSE](./LICENSE)。
