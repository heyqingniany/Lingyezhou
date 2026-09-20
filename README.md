# InterviewLens

桌面界面采用侧栏配置与“转写原文 / AI 整理 / 说话人”工作区，AI 报告直接渲染 Markdown。应用图标位于 `assets/interviewlens.svg`、`assets/interviewlens.png` 和 `assets/interviewlens.ico`；可运行 `python scripts/build_icon.py` 从矢量源重新生成图标，无额外图片库依赖。

InterviewLens 是一款通用的 Windows 录音转写与 AI 整理工具。它可以处理会议、访谈、课程、技术讨论和面试录音：经 FFmpeg 标准化后由 FunASR 本地转写并区分说话人，再通过可选的 OpenAI-compatible API 生成摘要、话题、结论、待办或面试复盘。

## 当前功能

- 豆包云端录音文件识别极速版：直接 HTTPS 上传、自动标点、数字规整、说话人区分；需自行开通及配置凭据
- 导入 `.wav`、`.mp3`、`.m4a`、`.flac`，展示路径、时长和大小
- FFmpeg 转换为 mono / 16 kHz / PCM 16-bit WAV；缺失时在 GUI 中明确提示
- SenseVoiceSmall + FSMN-VAD + CT-Punc + CAM++（默认，中文强制识别以避免短片段语言误判）
- Paraformer + FSMN-VAD + CT-Punc + CAM++（实验性，支持热词）
- 句级时间戳、匿名 Speaker、结构化 JSON 和 Markdown 转写
- 手工 Speaker 角色映射，以及可选的 LLM 角色推断
- “通用录音整理”和“技术面试复盘”两种 AI 场景
- OpenAI-compatible API 配置与结构化内容整理
- TXT、Markdown、JSON、SRT 字幕和 AI 报告导出
- ASR 模型实例复用；音频处理、ASR、LLM 均不阻塞 GUI 主线程
- 详细日志写入 `logs/interviewlens.log`

## 环境

推荐：

- Windows 10 / 11
- Python 3.11（FunASR/PyTorch 生态对 3.11 的兼容性更稳妥；不建议 Python 3.14）
- 8 GB 以上内存；CPU 可运行，检测到 CUDA 时 SenseVoice 自动使用 GPU

## 安装

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

PyTorch 的 CUDA 版本与显卡驱动有关。如需 GPU，请先按 [PyTorch 官方安装器](https://pytorch.org/get-started/locally/)安装匹配版本，再安装其余依赖。CPU 环境可直接按上面的命令安装。

## FFmpeg

安装方式任选其一：

```powershell
winget install Gyan.FFmpeg
```

或从 [FFmpeg 官方下载页](https://ffmpeg.org/download.html)选择 Windows 构建，将解压目录中的 `bin` 加入系统 `PATH`。新开终端检查：

```powershell
ffmpeg -version
ffprobe -version
```

项目依赖会安装 `imageio-ffmpeg` 提供的便携 FFmpeg，因此通常不需要管理员权限或单独设置 PATH。程序也兼容系统安装的 `ffmpeg`/`ffprobe`。启动时会检查 FFmpeg，缺失时不会静默失败：GUI 顶部会显示警告。已符合 mono / 16 kHz / PCM 16-bit 的 WAV 可以直接使用。

程序也支持免管理员的便携布局：将 `ffmpeg.exe`、`ffprobe.exe` 放在项目的 `.tools/ffmpeg/bin/` 下即可自动发现。`.tools/` 已被 Git 忽略；正式发布时可以把该目录作为安装包资源提供。

## 启动

```powershell
python app.py
```

首次转写会通过 FunASR / ModelScope 默认缓存机制下载 SenseVoiceSmall、FSMN-VAD 和 CAM++，不会把大模型下载到项目目录。下载耗时取决于网络，磁盘需预留数 GB 空间。

## 使用流程

1. 选择录音，并选择“通用录音整理”或“技术面试复盘”。
2. 填写可选的专业词汇（SenseVoice 当前不接收热词；词表会保留，Paraformer 会使用）。
3. 点击“开始转写”。
4. 检查 Speaker，并手工填写“主讲人”“客户”“面试官”等角色；也可先配置 AI 后让模型推断，再人工确认。
5. 在“设置 → AI 设置”配置 OpenAI-compatible API 的 Base URL、API Key 和 Model。
6. 点击“AI 整理”，检查结果，并按需导出转写、字幕或 AI 报告。

## 云端转写（新增）

更新：服务设置现可选择“录音文件识别 2.0（标准版）”，默认使用 `volc.seedasr.auc` 的提交/查询流程。下方旧极速版步骤仅适用于单独开通 `volc.bigasr.auc_turbo` 的账户；两种资源不能混用。标准版已提交任务的 ID 保存在 `output/cloud_<请求ID>/task.json`，查询失败后可用 `scripts/query_cloud_task.py <请求ID> <原音频路径>` 继续获取，无需重复提交。

1. 根据[官方接入文档](https://www.volcengine.com/docs/6561/1631584?lang=zh)，在火山引擎豆包语音控制台开通“大模型录音文件识别极速版”，资源为 `volc.bigasr.auc_turbo`。
2. 软件“设置 → 服务设置”中填写新版语音 API Key；旧版控制台则填写 App ID 和 Access Token。它们与文字整理服务的 API Key 独立。
3. 选择“豆包云端（需配置 · 按量计费）”，导入录音并开始转写。软件将音频直接发送到火山引擎，无需公开音频链接。费用按该账户当前套餐及控制台计费规则结算，不套用官网其他产品的宣传单价。
4. 当前接入支持不超过 2 小时、预处理后不超过 100 MB 的录音。过大的文件会在上传前拒绝，不会自动拆分并重复计费。服务超时也不会自动重试。
5. 云端原始返回及转写存放在独立的 `output/cloud_<请求ID>/` 下。现有 TXT、Markdown、JSON、SRT 导出均适用。

当前云端热词仅保留供文字校对使用；请求级热词尚未接入。不会强制指定说话人数，也不会应用本地短发言合并规则。没有返回说话人标签时明确显示“未区分说话人”。

云端接口接入不等于已验证达到飞书妙记质量。需配置真实凭据，用同一原始录音核对数字、漏句、关键术语和说话人归属。可使用命令保存独立验收结果：

```powershell
.\.venv\Scripts\python.exe scripts\cloud_transcribe.py "C:\路径\录音.m4a"
```

该命令会执行实际付费识别。凭据只在本地服务设置中填写，不需粘贴到聊天中。

没有配置 LLM 时，文件导入、预处理、ASR、角色手工映射和 transcript 导出均可正常使用。API 配置保存在本机 `config.local.json`，该文件与 `.env` 已被 Git 忽略。配置文件目前是明文，请不要共享。

## 输出

转写后自动生成：

```text
output/transcript.json
output/transcript.md
```

AI 整理完成后会按场景自动生成：

```text
output/<原文件名>_summary.md
output/<原文件名>_interview_review.md
```

## 测试

无需模型的核心测试：

```powershell
python -m unittest discover -s tests -v
$env:QT_QPA_PLATFORM="offscreen"
python scripts/gui_smoke.py
```

真实 ASR 验收需要安装 FFmpeg/FunASR，并准备一段 2～5 分钟、已获授权使用的中文双人录音。项目不附带或自动上传任何录音。

## PyInstaller（核心流程稳定后）

```powershell
pip install pyinstaller
pyinstaller --noconfirm --windowed --name InterviewLens --icon assets/interviewlens.ico --add-data "assets;assets" --add-data "prompts;prompts" --collect-all funasr app.py
```

FunASR、PyTorch 和模型使安装包较大，且模型仍建议使用默认外部缓存。源码运行是当前 MVP 的首要支持方式。

## 项目结构

```text
app.py
interviewlens/
  analysis/          # LLM 编排与 Markdown 报告
  asr/               # ASRBackend、SenseVoice、Paraformer
  audio/             # FFmpeg 探测与转换
  llm/               # LLMProvider 与 OpenAI-compatible 实现
  models/            # transcript 数据模型
  ui/                # PySide6 主窗口、设置、后台任务
prompts/
  general_analysis.md
  interview_analysis.md
scripts/
  gui_smoke.py
tests/
output/ cache/ logs/
```

## 当前限制

- 角色表支持任意数量的 Speaker；AI 推断的角色仍建议人工确认。
- CAM++ 产生的是录音内匿名聚类标签，不是跨录音的身份识别；重叠讲话、噪声和短句会影响效果。
- SenseVoiceSmall 官方未承诺热词参数，程序不会伪装支持；需要热词时可试用 Paraformer。
- LLM 兼容服务需支持 Chat Completions。少数服务不接受 `response_format=json_object`，需由服务端开启兼容或后续增加兼容降级。
- API Key 当前明文保存在本机忽略文件，尚未接入 Windows Credential Manager。

## API 依据

实现使用当前 FunASR `AutoModel` 流程：SenseVoiceSmall 组合 FSMN-VAD 与 CAM++，从 `sentence_info` 读取时间戳、文本和 `spk`。参考 [FunASR 官方仓库](https://github.com/modelscope/FunASR)、[官方模型选择说明](https://github.com/modelscope/FunASR/blob/main/docs/model_selection.md)和 [SenseVoice 官方仓库](https://github.com/FunAudioLLM/SenseVoice)。
