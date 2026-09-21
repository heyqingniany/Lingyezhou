# 聆页舟

**让声音落成文字。** 通用录音转写与 AI 整理，支持会议、课程、访谈和面试复盘。

## 本机快速启动

双击项目目录中的 `start.cmd`。它会自动进入项目目录并使用 `.venv` 中的 Python，无需激活环境。

源码运行时，在新电脑上先安装 Python 3.11，再双击 `setup.cmd` 安装依赖。EXE 发布包无需安装 Python。首次打开会引导选择云端或本地转写；选择本地后，在“本地模型 · 下载与管理”中确认下载。Whisper、SenseVoice 和 Paraformer 都按需安装，转写不会偷偷触发下载。

`setup.cmd` 使用官方 PyPI 和 `requirements-windows.lock.txt` 中记录的版本约束，安装后自动检查依赖与音频转换。可单独运行 `.venv\Scripts\python.exe scripts\check_runtime.py` 检查环境。

本次已完成默认模型下载及示例转写验证，详见 [本机部署记录](docs/deployment.md)。模型准备和示例验证命令：`.venv\Scripts\python.exe scripts\prepare_models.py --smoke`。

云端识别与 AI 整理需要在软件的“设置 → 服务设置”中填写自己的服务凭据。本地转写无需 API Key。

程序记住首次选择的云端 / 本地偏好，也可以随时切换引擎。云端转写无需下载模型。

名称已从 InterviewLens 改为聆页舟（Lingyezhou）；代码包为 `lingyezhou`。项目所在文件夹可继续使用原路径。名称公开检索范围与未完成的商标核查见 [名称检索记录](docs/name-review.md)。

桌面界面采用侧栏配置与“转写原文 / AI 整理 / 说话人 / 历史记录 / 多次复盘”工作区，AI 报告直接渲染 Markdown。应用图标位于 `assets/lingyezhou.svg`、`assets/lingyezhou.png` 和 `assets/lingyezhou.ico`；可运行 `python scripts/build_icon.py` 从矢量源重新生成图标，无额外图片库依赖。

聆页舟 是一款通用的 Windows 录音转写与 AI 整理工具。它可以处理会议、访谈、课程、技术讨论和面试录音：经 FFmpeg 标准化后进行本地或云端转写，再通过可选的 DeepSeek、OpenAI 或其他 OpenAI-compatible API 生成摘要、话题、结论、待办或面试复盘。

源码以 [MIT 许可证](LICENSE)开放。Windows 预览版下载与限制见 [发布说明](docs/release.md)。

## 当前功能

- 豆包云端录音文件识别标准版 2.0 与极速版：直接 HTTPS 上传、自动标点、数字规整、说话人区分；需自行开通及配置凭据
- 导入 `.wav`、`.mp3`、`.m4a`、`.flac`，展示路径、时长和大小
- 将单个录音拖放到窗口任意位置导入，拖入时高亮；也支持点击导入和 `Ctrl+O`
- 后台读取文件信息；无效文件保留当前内容，新文件读取成功后清空上一份转写和报告
- FFmpeg 转换为 mono / 16 kHz / PCM 16-bit WAV；缺失时在 GUI 中明确提示
- Whisper large-v3-turbo / faster-whisper（默认推荐，准确率优先，自动识别语言并支持术语提示）
- SenseVoiceSmall + FSMN-VAD + CT-Punc + CAM++（速度优先）
- Paraformer + FSMN-VAD + CT-Punc + CAM++（中文热词优先）
- 句级时间戳、匿名 Speaker、结构化 JSON 和 Markdown 转写
- 手工 Speaker 角色映射，以及可选的 LLM 角色推断
- “通用录音整理”和“技术面试复盘”两种 AI 场景
- DeepSeek（默认推荐）、OpenAI 和自定义 OpenAI-compatible 文字 AI 服务
- AI 整理页直接导出 Markdown 报告、JSON 数据和录音问答记录
- 围绕当前录音连续提问，回答引用时间点并区分原文事实、推断和待核实事项
- 每次转写自动归入本机历史，保留文字、角色与单次 AI 报告，不复制原始录音
- 勾选 2–8 次同类记录生成跨期复盘，从表达、结构、知识和行动等维度比较有证据的变化
- TXT、Markdown、JSON、SRT 字幕和 AI 报告导出
- ASR 模型实例复用；音频处理、ASR、LLM 均不阻塞 GUI 主线程
- 详细日志写入 `logs/lingyezhou.log`

## 环境

推荐：

- Windows 10 / 11
- Python 3.11（FunASR/PyTorch 生态对 3.11 的兼容性更稳妥；不建议 Python 3.14）
- 8 GB 以上内存；CPU 可运行，Whisper 检测到可用 CUDA 时优先使用 GPU并在加载失败时回退 CPU

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

点击“本地模型 · 下载与管理”，可查看预计大小和目录，再确认下载。默认存放于 `%LOCALAPPDATA%\Lingyezhou\Lingyezhou-models`，支持更换位置、暂停、续传、失败重试和删除。推荐的 Whisper large-v3-turbo 约 1.62 GB；SenseVoice 完整管线约 2.15 GB，Paraformer 与它共用分段、标点和说话人模型。更换位置不会移动或删除原目录；删除某个引擎时保留其他已安装引擎所需的共用文件。

模型来自 ModelScope，按官方文件清单进行 SHA-256 校验后才标记就绪。已有 ModelScope 默认缓存中的相同文件会经校验后复制复用，不会删除原缓存。下载和删除使用目录锁，避免多个窗口同时改写同一份模型。识别只使用专用目录中的已安装文件，不会自动联网更新模型。

## 使用流程

1. 将录音拖入窗口（一次一个），或点击导入 / 按 `Ctrl+O`；选择“通用录音整理”或“技术面试复盘”。导入不会自动开始转写或上传。
2. 填写可选的专业词汇（Whisper 将其作为上下文提示，Paraformer 作为热词；SenseVoice 仅保留供 AI 校对）。
3. 点击“开始转写”。
4. 检查 Speaker，并手工填写“主讲人”“客户”“面试官”等角色；也可先配置 AI 后让模型推断，再人工确认。
5. 打开“服务设置 → AI 整理”。默认推荐价格较低的 DeepSeek，也可切换 OpenAI 或填写其他兼容接口。
6. 点击“AI 整理”，检查结果，并按需导出转写、字幕或 AI 报告。
7. 在“基于录音提问”中继续追问承诺、分歧、证据和未确认事项；问答会随历史记录保存，也可导出 Markdown。
8. 每次转写会自动进入“历史记录”。勾选 2–8 条场景相近的记录，点击“生成多次复盘”可比较进步、退步、反复问题和下一步行动。

## AI 整理服务

DeepSeek 是默认预设，推荐先使用成本较低的 `deepseek-flash`。软件也提供 OpenAI 预设，并允许配置其他兼容 Chat Completions 的服务。API Key、接口地址和模型只需在“服务设置 → AI 整理”中填写；校对、角色推断、单次整理和多次复盘共用这项设置。

AI 功能只发送转写文字，不发送原始录音。未配置文字 AI 时，本地/云端转写、历史归档、角色手工编辑以及 TXT、Markdown、JSON、SRT 导出仍可使用。

录音问答适合整理离职协商、合同沟通、买房谈话等复杂材料：它会引用录音时间点，列出明确事实、合理推断、证据缺口和下一步。法律类回答只用于材料梳理和一般信息参考，不会把未核验的模型结论写成正式法律意见；具体权利义务仍需结合地区、事件日期、合同全文和当地专业意见判断。

历史档案默认保存在 `%LOCALAPPDATA%\Lingyezhou\history`。档案包含结构化转写和报告，原始音频仍在用户原来的位置；移动或删除音频后，历史文字仍可阅读和导出。在历史页删除一条记录只会删除归档文字和报告，不会删除原始录音。多次复盘按时间顺序向 AI 提供已选记录，优先使用已有单次报告，并限制发送文本总量。它只报告有原文证据支持的变化，不把录音时长或发言多少当作能力进步。

## 云端转写（新增）

更新：服务设置现可选择“录音文件识别 2.0（标准版）”，默认使用 `volc.seedasr.auc` 的提交/查询流程。下方旧极速版步骤仅适用于单独开通 `volc.bigasr.auc_turbo` 的账户；两种资源不能混用。标准版已提交任务的 ID 保存在 `output/cloud_<请求ID>/task.json`，查询失败后可用 `scripts/query_cloud_task.py <请求ID> <原音频路径>` 继续获取，无需重复提交。

1. 根据[官方接入文档](https://www.volcengine.com/docs/6561/1631584?lang=zh)，在火山引擎豆包语音控制台开通“大模型录音文件识别极速版”，资源为 `volc.bigasr.auc_turbo`。
2. 软件“设置 → 服务设置”中填写新版语音 API Key；旧版控制台则填写 App ID 和 Access Token。它们与文字整理服务的 API Key 独立。
3. 选择“豆包云端（需配置 · 按量计费）”，导入录音并开始转写。软件将音频直接发送到火山引擎，无需公开音频链接。费用按该账户当前套餐及控制台计费规则结算，不套用官网其他产品的宣传单价。
4. 标准版要求录音短于 5 小时、上传文件小于 512 MB；极速版要求短于 2 小时、上传文件小于 100 MB。软件优先上传服务支持的原始 MP3/M4A/WAV，格式不兼容或文件过大时压缩为 64 kbps 单声道 MP3。仍超限时会在上传前拒绝，不会自动拆分并重复计费。服务超时也不会自动重试。
5. 云端原始返回及转写存放在独立的 `output/cloud_<请求ID>/` 下。现有 TXT、Markdown、JSON、SRT 导出均适用。

当前云端热词仅保留供文字校对使用；请求级热词尚未接入。不会强制指定说话人数，也不会应用本地短发言合并规则。没有返回说话人标签时明确显示“未区分说话人”。

云端接口接入不等于已验证达到飞书妙记质量。需配置真实凭据，用同一原始录音核对数字、漏句、关键术语和说话人归属。可使用命令保存独立验收结果：

```powershell
.\.venv\Scripts\python.exe scripts\cloud_transcribe.py "C:\路径\录音.m4a"
```

该命令会执行实际付费识别。凭据只在本地服务设置中填写，不需粘贴到聊天中。

没有配置文字 AI 时，文件导入、预处理、ASR、历史归档、角色手工映射和 transcript 导出均可正常使用。服务配置保存在本机 `config.local.json`，该文件与 `.env` 已被 Git 忽略。配置文件目前是明文，请不要共享。

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

## Windows EXE 发布包（不含模型）

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt -c requirements-windows.lock.txt
.\build_windows.cmd
```

产物为 `dist/Lingyezhou/Lingyezhou.exe`。这是文件夹式 EXE 发布包，必须分发整个 `Lingyezhou` 文件夹（包括 `_internal`），不能只复制 EXE。打包配置为 `packaging/lingyezhou.spec`，只包含代码、界面资源、提示词和运行库，不包含模型、密钥、录音、日志或模型缓存。PyTorch/FunASR 运行库仍会占用一定空间。

EXE 把配置、日志和结果保存到 `%LOCALAPPDATA%\Lingyezhou`，不会向安装目录写入。模型按用户选择独立下载。详见 [发布说明](docs/release.md)。

## 项目结构

```text
app.py
lingyezhou/
  analysis/          # LLM 编排与 Markdown 报告
  asr/               # ASRBackend、Whisper、SenseVoice、Paraformer
  audio/             # FFmpeg 探测与转换
  llm/               # LLMProvider 与 OpenAI-compatible 实现
  models/            # transcript 数据模型
  ui/                # PySide6 主窗口、设置、后台任务
prompts/
  general_analysis.md
  history_analysis.md
  interview_analysis.md
scripts/
  gui_smoke.py
tests/
output/ cache/ logs/
```

## 当前限制

- 角色表支持任意数量的 Speaker；AI 推断的角色仍建议人工确认。
- CAM++ 产生的是录音内匿名聚类标签，不是跨录音的身份识别；重叠讲话、噪声和短句会影响效果。
- Whisper 暂不提供说话人身份，结果显示为单一说话人；需要自动分角色时可使用 FunASR 管线或后续 AI 推断。
- SenseVoiceSmall 官方未承诺热词参数，程序不会伪装支持；需要严格中文热词时可试用 Paraformer。
- 自定义文字 AI 服务需兼容 Chat Completions，并支持 JSON Object 响应格式。
- 多次复盘依赖转写和单次报告的质量；不同类型、不同目标的录音不适合直接比较，结论应回到原文核对。
- API Key 当前明文保存在本机忽略文件，尚未接入 Windows Credential Manager。

## API 依据

实现使用当前 FunASR `AutoModel` 流程：SenseVoiceSmall 组合 FSMN-VAD 与 CAM++，从 `sentence_info` 读取时间戳、文本和 `spk`。参考 [FunASR 官方仓库](https://github.com/modelscope/FunASR)、[官方模型选择说明](https://github.com/modelscope/FunASR/blob/main/docs/model_selection.md)和 [SenseVoice 官方仓库](https://github.com/FunAudioLLM/SenseVoice)。
