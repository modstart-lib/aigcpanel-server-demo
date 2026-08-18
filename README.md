
# 🚀 AIGCPanel 模型自定义接入 - 队列模式示例

本项目演示如何在 AIGCPanel 中自定义接入 AI 模型，核心是 `while config := aigcpanelserver.watchNext():` 的**持续队列（watch）模式**：模型服务进程常驻，通过轮询 `aigcpanel-queue/` 目录持续消费任务。

## 📁 目录结构

- `run.py`：主程序入口（`appPrepare` → `while watchNext()` 队列循环 → `end`）🏠
- `aigcpanelserver.py`：轻量自包含 SDK（仅保留 `appPrepare` / `watchNext` / `result` / `resultEnd` / `resultEnv` / `localCache` / `urlForResult` / `filterText` / `end` 等必要接口）
- `tests/single.py`：非队列（单次）模式测试
- `tests/queue.py`：队列模式测试（子进程启动服务 → 投递任务 → 校验结果）
- `config.json`：服务端配置（`mode.type = watch` 开启队列模式）
- `example-config/`：任务配置示例
- `example-file/`：示例媒体文件

## 🧠 队列模式工作原理

```
run.py
  │  appPrepare()            读取启动配置，初始化环境
  ▼
while config := watchNext():   ─┐
  │  处理一个任务并输出结果      │ 首轮返回启动配置
  │                            │ 之后持续轮询 aigcpanel-queue/
  ▼                            │ 中的 *.queue.json 新任务
（无新任务到达超过 watchDelay 秒）
  ▼
end()                         退出进程
```

- 首个 `watchNext()` 返回启动时传入的配置（`sys.argv[1]`）
- 之后每次调用轮询 `aigcpanel-queue/` 目录，按文件名顺序消费 `*.queue.json`
- 进程在任务之间保持存活，**模型只需加载一次**即可服务所有队列任务
- `config.json` 中 `mode.watchDelay`（秒）控制空闲保活窗口，超时无新任务则退出

## 🎯 两种运行模式

| 模式 | 触发方式 | 行为 |
| ---- | ---- | ---- |
| **队列模式**（推荐） | `config.json` 中 `mode.type = "watch"` | 处理首个任务后持续轮询队列，常驻服务 |
| **非队列模式**（单次） | 启动配置命名为 `*.example.json` | 处理一个任务后立即退出 |

两种模式由 `watchNext()` 统一实现：首轮都返回启动配置；之后若 `mode.type == "watch"` 则轮询队列，否则（或超时）返回 `None` 结束循环。

## ⚙️ 环境初始化

### 🪟 Windows

```shell
conda 'shell.powershell' 'hook' | Out-String | Invoke-Expression
conda create --prefix ./_aienv -y python=3.10
conda activate ./_aienv
pip install -r requirements.txt
```

### 🐧 Linux / macOS

```shell
eval "$(conda shell.bash hook)"
conda create --prefix ./_aienv -y python=3.10
conda activate ./_aienv
pip install -r requirements.txt
```

## ▶️ 运行示例

### 队列模式（推荐）

终端 1 - 启动常驻服务：

```shell
python run.py example-config/soundTts.json
```

终端 2 - 持续投递任务（可任意多次）：

```shell
python -c "import json,os; json.dump(json.load(open('example-config/textToImage.json')), open('aigcpanel-queue/t1.queue.json','w'), ensure_ascii=False)"
python -c "import json,os; json.dump(json.load(open('example-config/asr.json')), open('aigcpanel-queue/t2.queue.json','w'), ensure_ascii=False)"
```

服务每处理完一个任务，会输出一行 `AigcPanelRunResult[id][base64]`（供 launcher/UI 解析），队列文件处理完毕后随即被删除。

> 提示：把任意任务配置放入 `aigcpanel-queue/` 目录（文件名以 `.queue.json` 结尾）即完成投递。

### 非队列模式（单次运行）

```shell
python run.py example-config/soundTts.json
```

将启动配置改名为 `xxx.example.json`（如 `example-config/soundTts.example.json`）即可让进程处理完一个任务后自动退出。

## 🧪 运行测试

```shell
# 非队列（单次）模式测试
python tests/single.py

# 队列模式测试：子进程启动服务 -> 投递任务 -> 校验所有结果
python tests/queue.py
```

## 🚀 一键加载 + 功能测试（通过 AIGCPanel CLI）

```shell
python3 launchtest.py
```

实现为单文件 `launchtest.py`，全部基于 aigcpanel CLI 完成：

1. `aigcpanel serverInstall --dir .`：将当前目录模型加载到 AigcPanel 的已安装服务列表
2. `aigcpanel serverList`：校验服务已成功加载
3. `aigcpanel serverCall`：依次调用全部功能（`soundTts` / `soundClone` / `videoGen` / `asr` / `textToImage` / `imageToImage` / `textToVideo` / `imageToVideo`）并等待结果

自动行为：

- **AigcPanel 未运行时自动启动**：从默认安装位置查找（macOS 的 `/Applications/AigcPanel.app`、Windows 的 `%LOCALAPPDATA%` 安装目录、Linux 的 `/opt` 等），启动后等待 HTTP 服务就绪（最多 60s）
- **CLI 自动定位**：在与当前项目同级的 aigcpanel 源码目录（`dist-cli`）中自动查找 `aigcpanel` 命令，缺失时用 go 自动构建当前平台版本

## 🧩 支持的模型功能

| 功能 | 配置示例 | 输出 |
| ---- | ---- | ---- |
| 语音合成 soundTts | `example-config/soundTts.json` | `url` |
| 语音克隆 soundClone | `example-config/soundClone.json` | `url` |
| 视频合成 videoGen | `example-config/videoGen.json` | `url` + `Duration` |
| 语音识别 asr | `example-config/asr.json` | `records` |
| 文生图 textToImage | `example-config/textToImage.json` | `url` |
| 图生图 imageToImage | `example-config/imageToImage.json` | `url` |
| 文生视频 textToVideo | `example-config/textToVideo.json` | `url` |
| 图生视频 imageToVideo | `example-config/imageToVideo.json` | `url` |
| 通用模型 general | `example-config/general.json` | `file` / `files` / `text`（按 config.json `general[].result` 定义展示） |

本示例不加载真实模型，用 `example-file/` 中的媒体文件模拟推理结果；接入真实模型时，只需在 `run.py` 的循环外加载一次模型，替换各分支中的模拟代码即可。

## 📄 License

MIT 📜
