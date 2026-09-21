# 聆页舟 Windows 预览版发布说明

版本：`v0.1.0-alpha.1`。Windows 10/11 x64 文件夹式 EXE，压缩包约 495 MB，解压约 1.22 GB。ZIP 不包含模型权重、录音、API 密钥或个人配置。解压整个文件夹后运行 `Lingyezhou.exe`，不要单独移动 EXE。

## 主要功能

- 拖放导入 WAV、MP3、M4A、FLAC；本地 Whisper、SenseVoice、Paraformer 按需下载，或使用豆包云端识别。
- DeepSeek、OpenAI 和自定义兼容服务用于校对、整理、角色推断及围绕录音提问。
- 自动归档每次转写、报告和问答；可选 2–8 次记录生成跨期复盘。
- 导出 TXT、Markdown、JSON、SRT、AI 报告及问答记录。

## 首次使用

1. 选择云端或本地转写。云端需要自行配置豆包语音凭据；本地推荐下载约 1.62 GB 的 Whisper large-v3-turbo。
2. 将录音拖入窗口，选择识别引擎，点击“开始转写”。
3. AI 整理和录音问答需另行配置文字 AI 凭据。默认预设为 DeepSeek `deepseek-flash`。

用户配置、历史和结果默认存放在 `%LOCALAPPDATA%\Lingyezhou`；原始录音保持在原位置。本地模型默认存放在其 `Lingyezhou-models` 子目录，也可在应用中更改。

## 已验证与已知限制

- 47 项自动测试通过；打包后启动、随包 FFmpeg 及本地 Whisper 中文示例离线识别通过。
- 包内不含模型；已审计 ZIP，无录音或私人配置。
- 未使用用户凭据实测豆包和 DeepSeek 的付费接口。云端标准版与极速版需要各自开通的资源权限。
- Whisper 当前不自动区分说话人；其他管线的说话人聚类也需要人工检查。
- EXE 尚未代码签名，也未在全新 Windows 虚拟机进行兼容性验证。
- 名称的公开检索不是商标权利清查，详见 [名称检索记录](name-review.md)。

## 开发与重建

使用 Python 3.11，运行 `setup.cmd` 安装依赖，`build_windows.cmd` 构建。完成 `scripts/run_release_checks.ps1` 后运行 `scripts/package_release.py` 生成 ZIP、SHA-256 和审计报告。模型、录音、日志、缓存及 `config.local.json` 均由 `.gitignore` 排除。
