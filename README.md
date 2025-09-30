
# 🚀 AIGCPanel 模型自定义接入 - 简易接入示例

本项目用于演示如何在 AIGCPanel 中自定义接入 AI 模型，支持快速环境初始化和依赖安装，适用于 Windows、Linux 和 macOS。✨

## 📋 项目简介

- 🌍 支持多平台环境初始化
- 📁 提供示例配置文件和数据
- 🔧 便于二次开发和集成

## ⚙️ 环境初始化

> 请根据实际情况调整环境配置 🛠️

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

```shell
python run.py
```

## 📂 目录结构说明

- `run.py`：主程序入口 🏠
- `requirements.txt`：依赖包列表 📦
- `config.json`：主配置文件 ⚙️
- `example/`：示例数据与配置 📊

## 📄 License

MIT 📜
