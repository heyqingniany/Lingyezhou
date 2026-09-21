# 聆页舟本机部署记录

验证日期：2026-09-20。平台：Windows，Python 3.11.0，项目独立 `.venv`，CPU 推理。已升级为按需下载模型版，发布包说明见 `release.md`。

## 启动

双击项目根目录的 `start.cmd`，或运行 `.venv\Scripts\python.exe app.py`。
安装及重装入口为 `setup.cmd`；版本约束保存在 `requirements-windows.lock.txt`。

## 已完成的验证

- 47 项核心与界面测试通过，包含模型下载、续传及删除保护。
- `pip check` 未发现依赖冲突。
- PySide6、FunASR、ModelScope、PyTorch、torchaudio、OpenAI SDK 导入成功。
- 通过随包 FFmpeg 实际生成 MP3，读取时长并转换为单声道 / 16 kHz / PCM 16-bit WAV。
- 界面冒烟检查通过，截图在 `output/lingyezhou-smoke.png`。
- 实际桌面窗口启动成功，标题为“聆页舟 — 录音转写与 AI 整理”，进程正常响应。
- SenseVoiceSmall、FSMN-VAD、CT-Punc、CAM++ 下载并加载成功。
- faster-whisper、CTranslate2 与 Whisper large-v3-turbo 已接入；模型按需下载，不打入 EXE。
- 使用模型自带的中文示例 `example/zh.mp3`，经过应用的 FFmpeg 和 SenseVoiceBackend 完整流程，成功输出非空转写；结果为 `output/runtime-smoke/transcript.json` 和 `transcript.md`。

主要版本：PySide6 6.11.2、FunASR 1.4.16、ModelScope 1.40.1、torch 2.14.0、torchaudio 2.11.0、openai 2.54.0、imageio-ffmpeg 0.6.0。完整依赖以锁定文件为准。

应用使用 `%LOCALAPPDATA%\Lingyezhou\Lingyezhou-models` 专用模型目录。模型未提交到仓库，也不打入 EXE。Whisper 是默认推荐的本地高质量引擎；SenseVoice 为极速模式，Paraformer 为中文热词模式。`scripts/prepare_models.py --engine whisper --smoke --audio <录音路径>` 可准备 Whisper 并验证转写；省略 `--audio` 时使用已有 SDK 缓存中的中文示例。

## 验证范围

本次验证证明本机默认转写流程可运行，不代表长音频、噪声或多人说话场景的准确率验收。
未提供云端及 LLM API 凭据，故没有实际调用收费云端识别和 AI 整理服务；请在应用“服务设置”中配置。首次启动引导选择云端或本地；之后记住该偏好。

名称已修改，但商标权利清查未完成，详见 `name-review.md`。
