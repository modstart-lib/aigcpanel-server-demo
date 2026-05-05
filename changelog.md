# Changelog

## [Unreleased]

### Improvements / 改进

- Added auth.json patterns to `.gitignore` to prevent authentication credentials from being committed
  在 `.gitignore` 中添加 auth.json 模式，防止身份验证凭据被提交

- Enhanced example config files with explicit `type` field for better clarity and consistency
  在示例配置文件中添加显式 `type` 字段，增强清晰度和一致性

- Fixed launcher-data path handling to use absolute paths, ensuring compatibility across different working directories
  修复 launcher-data 路径处理，使用绝对路径以确保跨不同工作目录的兼容性

- Reduced simulated processing delay from 10 seconds to 1 second for all model types (soundTts, soundClone, videoGen, asr, textToImage, imageToImage)
  将所有模型类型（soundTts、soundClone、videoGen、asr、textToImage、imageToImage）的模拟处理延迟从 10 秒缩短为 1 秒

- Reorganized example directory into `example-config/` (JSON config samples) and `example-file/` (media assets such as images, audio, and video files) for clearer separation of concerns
  将示例目录拆分为 `example-config/`（JSON 配置示例）和 `example-file/`（图片、音频、视频等媒体文件），职责更加清晰

- Updated all path references in `run.py` to point to the new `example-config/` and `example-file/` directories
  更新 `run.py` 中所有路径引用，指向新的 `example-config/` 和 `example-file/` 目录

- Updated `README.md` to reflect the new directory structure
  更新 `README.md` 以反映新的目录结构
