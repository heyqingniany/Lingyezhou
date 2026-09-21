from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from lingyezhou.analysis.interview_analyzer import InterviewAnalyzer
from lingyezhou.analysis.report import (
    render_general_report, render_history_report, render_qa_answer,
    render_qa_conversation, render_report,
)
from lingyezhou.asr.paraformer import ParaformerBackend
from lingyezhou.asr.doubao import DoubaoBackend
from lingyezhou.asr.sensevoice import SenseVoiceBackend
from lingyezhou.asr.whisper import WhisperBackend
from lingyezhou.asr.model_store import ModelStore
from lingyezhou.audio.ffmpeg import AudioInfo, FFmpegProcessor
from lingyezhou.config import AppConfig
from lingyezhou.history import HistoryStore
from lingyezhou.llm.openai_compatible import OpenAICompatibleProvider
from lingyezhou.models.transcript import Transcript
from lingyezhou.ui.config_dialog import ConfigDialog
from lingyezhou.ui.workers import TaskWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("聆页舟 — 录音转写与 AI 整理")
        self.resize(1180, 820)
        self.config = AppConfig.load()
        self.model_store = ModelStore(self.config.model_directory)
        self.history_store = HistoryStore()
        self.ffmpeg = FFmpegProcessor()
        self.backends = {
            "豆包云端（需配置 · 按量计费）": None,
            "Whisper · 高质量（本地推荐）": WhisperBackend(store=self.model_store),
            "SenseVoice · 极速（本地）": SenseVoiceBackend(store=self.model_store),
            "Paraformer · 中文热词（本地）": ParaformerBackend(store=self.model_store),
        }
        self.backend_engines = {
            "豆包云端（需配置 · 按量计费）": None,
            "Whisper · 高质量（本地推荐）": "whisper",
            "SenseVoice · 极速（本地）": "sensevoice",
            "Paraformer · 中文热词（本地）": "paraformer",
        }
        self.audio_path: Path | None = None
        self.transcript: Transcript | None = None
        self.analysis_data: dict | None = None
        self.analysis_mode: str | None = None
        self.report_markdown: str = ""
        self.current_history_id: str | None = None
        self.comparison_data: dict | None = None
        self.qa_messages: list[dict] = []
        self._threads: list[QThread] = []
        self._workers: list[TaskWorker] = []
        self._busy = False
        self._build_ui()
        self.refresh_history()
        # Editable child widgets otherwise consume file drops as text/URLs.
        for widget in self.findChildren(QWidget):
            widget.setAcceptDrops(False)
        self.setAcceptDrops(True)
        self.import_action = QAction("导入录音", self)
        self.import_action.setShortcut(QKeySequence.StandardKey.Open)
        self.import_action.triggered.connect(self.choose_audio)
        self.addAction(self.import_action)
        self._apply_style()
        self._update_llm_state()
        self._check_ffmpeg()

    def _build_ui(self) -> None:
        from lingyezhou.ui.workspace_view import build_workspace
        build_workspace(self)

    def _apply_style(self) -> None:
        from lingyezhou.ui.workspace_view import STYLE
        self.setStyleSheet(STYLE)


    def _scene_changed(self, index: int = -1) -> None:
        interview = self.scene_combo.currentIndex() == 1
        self.report_title.setText("AI 面试复盘  ·  Markdown" if interview else "AI 整理结果  ·  Markdown")
        self.analyze_button.setText("生成面试复盘" if interview else "AI 整理")
        selected_mode = "interview" if interview else "general"
        if self.analysis_mode and self.analysis_mode != selected_mode:
            self.analysis_data = None
            self.analysis_mode = None
            self.report_markdown = ""
            self.report_view.clear()
            self.statusBar().showMessage("整理场景已切换，请重新生成 AI 报告")
            self._update_llm_state()

    def _check_ffmpeg(self) -> None:
        if self.ffmpeg.is_available():
            self.ffmpeg_banner.setText("● 音频转换已就绪")
            self.ffmpeg_banner.setToolTip("FFmpeg 已安装，M4A 等格式可自动转换。")
        else:
            self.ffmpeg_banner.setText(
                "⚠ 未检测到 FFmpeg：MP3、M4A、FLAC 和非 16 kHz WAV 无法预处理。"
                "请运行 pip install -r requirements.txt，或安装 FFmpeg 后重启。标准 mono 16 kHz PCM WAV 仍可直接使用。"
            )
            self.ffmpeg_banner.setStyleSheet("background:#fff3cd;color:#664d03;padding:8px;border-radius:4px;")

    def _update_llm_state(self) -> None:
        ready = self.config.llm_ready
        provider_names = {"deepseek": "DeepSeek", "openai": "OpenAI", "custom": "自定义服务"}
        self.llm_status.setText(
            f"AI：{provider_names.get(self.config.ai_provider, '自定义服务')} · {self.config.model}"
            if ready else "AI：未配置（ASR 不受影响）"
        )
        available = ready and self.transcript is not None
        self.detect_roles_button.setEnabled(available)
        self.polish_button.setEnabled(available)
        self.analyze_button.setEnabled(available)
        self.export_button.setEnabled(bool(self.report_markdown or self.transcript))
        self.report_export_button.setEnabled(bool(self.analysis_data or self.qa_messages))
        if hasattr(self, "compare_button"):
            self.compare_button.setEnabled(ready and not self._busy)
        self._update_chat_button()

    def _update_chat_button(self) -> None:
        if not hasattr(self, "chat_send_button"):
            return
        self.chat_send_button.setEnabled(
            not self._busy
            and self.config.llm_ready
            and self.transcript is not None
            and bool(self.chat_input.text().strip())
        )

    def choose_audio(self) -> None:
        if self._busy:
            return
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择录音", str(self.audio_path.parent) if self.audio_path else "",
            "音频文件 (*.wav *.mp3 *.m4a *.flac)"
        )
        if filename:
            self.import_audio(Path(filename))

    def _drop_path(self, mime) -> Path:
        if self._busy:
            raise ValueError("任务处理中，请完成后再导入录音。")
        urls = mime.urls()
        if len(urls) != 1:
            raise ValueError("请一次拖入一个录音文件，暂不支持批量导入。")
        if not urls[0].isLocalFile():
            raise ValueError("请拖入电脑上的录音文件，不支持网页链接。")
        path = Path(urls[0].toLocalFile())
        self._validate_audio(path)
        return path

    @staticmethod
    def _validate_audio(path: Path) -> None:
        if not path.is_file():
            raise ValueError("请导入一个可访问的录音文件，不支持文件夹。")
        if path.suffix.lower() not in {".wav", ".mp3", ".m4a", ".flac"}:
            raise ValueError("支持 WAV、MP3、M4A、FLAC，请选择这些格式的录音。")

    def _highlight_drop(self, active: bool) -> None:
        self.drop_zone.setProperty("dragActive", active)
        self.drop_zone.style().unpolish(self.drop_zone)
        self.drop_zone.style().polish(self.drop_zone)
        self.drop_zone.setText("松开鼠标，导入这段录音" if active else
                               "拖放录音到窗口，即可导入\n或点击选择文件 · Ctrl+O")

    def dragEnterEvent(self, event) -> None:
        try:
            self._drop_path(event.mimeData())
        except ValueError as exc:
            self._highlight_drop(False)
            self.statusBar().showMessage(str(exc), 6000)
            event.ignore()
            return
        self._highlight_drop(True)
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dragMoveEvent(self, event) -> None:
        self.dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:
        self._highlight_drop(False)
        event.accept()

    def dropEvent(self, event) -> None:
        self._highlight_drop(False)
        try:
            path = self._drop_path(event.mimeData())
        except ValueError as exc:
            self.statusBar().showMessage(str(exc), 6000)
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self.import_audio(path)

    def import_audio(self, path: Path) -> None:
        if self._busy:
            return
        try:
            self._validate_audio(path)
        except ValueError as exc:
            self._show_error("无法读取音频", str(exc))
            return
        self._set_busy(True, f"正在读取录音：{path.name}…")
        self._run_task(lambda progress: self.ffmpeg.probe(path), self._audio_loaded)

    def _audio_loaded(self, info: AudioInfo) -> None:
        self.audio_path = info.path
        self.transcript = None
        self.analysis_data = None
        self.analysis_mode = None
        self.report_markdown = ""
        self.current_history_id = None
        self.qa_messages = []
        self.transcript_view.clear()
        self.report_view.clear()
        self.chat_view.clear()
        self.chat_input.clear()
        self.role_table.setRowCount(0)
        self.tabs.setCurrentIndex(0)
        self.file_path.setText(str(info.path))
        self.file_path.setToolTip(str(info.path))
        self.file_info.setText(
            f"文件名：{info.path.name}    时长：{Transcript.format_time(int(info.duration_seconds * 1000))}"
            f"    大小：{info.readable_size}"
        )
        self.document_info.setText(f"{info.path.name}  ·  已导入，点击「开始转写」")
        self.document_info.setToolTip(str(info.path))
        self._set_busy(False, f"已导入：{info.path.name} · 点击「开始转写」")

    def _hotword_list(self) -> list[str]:
        return [line.strip() for line in self.hotwords.toPlainText().splitlines() if line.strip()]

    def start_transcription(self) -> None:
        if not self.audio_path:
            return
        audio_path = self.audio_path
        engine = self.model_combo.currentData()
        cloud = engine is None
        if not cloud:
            if not self.model_store.ready(engine):
                self.open_models(engine)
                return
        if cloud and not self.config.cloud_ready:
            self.open_settings()
            if not self.config.cloud_ready:
                return
        backend = (
            DoubaoBackend(self.config.cloud_api_key, self.config.cloud_app_id, self.config.cloud_access_token, self.config.cloud_mode)
            if cloud else self.backends[self.model_combo.currentText()]
        )
        hotwords = self._hotword_list()

        def task(progress: Callable[[str], None]) -> Transcript:
            info = self.ffmpeg.probe(audio_path)
            maximum_duration = 18000 if self.config.cloud_mode == "standard" else 7200
            if cloud and info.duration_seconds >= maximum_duration:
                limit = "5 小时" if self.config.cloud_mode == "standard" else "2 小时"
                version = "标准版" if self.config.cloud_mode == "standard" else "极速版"
                raise ValueError(f"云端{version}要求录音短于 {limit}，请先分割文件。")
            progress("正在准备云端上传文件…" if cloud else "正在预处理音频…")
            normalized = (
                self.ffmpeg.prepare_cloud_upload(audio_path, self.config.cloud_mode)
                if cloud else self.ffmpeg.convert(audio_path)
            )
            progress("正在上传至豆包云端并识别（按账户套餐计费）…" if cloud else "正在加载本地模型/转写…")
            result = backend.transcribe(normalized, hotwords)
            result.source_file = str(audio_path)
            result.hotwords = list(hotwords)
            result.duration_ms = int(info.duration_seconds * 1000)
            if cloud:
                run_dir = Path("output") / f"cloud_{backend.request_id}"
                result.save(run_dir)
                (run_dir / "provider_response.json").write_text(
                    json.dumps(backend.raw_response, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            result.save()
            return result

        self._set_busy(True, "转写处理中…")
        self._run_task(task, self._transcription_done)

    def _transcription_done(self, result: object) -> None:
        self.transcript = result if isinstance(result, Transcript) else None
        if not self.transcript:
            self._set_busy(False, "转写失败")
            self._show_error("转写失败", "内部结果类型无效。")
            return
        self.analysis_data = None
        self.analysis_mode = None
        self.report_markdown = ""
        self.qa_messages = []
        self.report_view.clear()
        self.chat_view.clear()
        scene = "interview" if self.scene_combo.currentIndex() == 1 else "general"
        try:
            self.current_history_id = self.history_store.add(self.transcript, scene)
        except OSError:
            logger.exception("Could not archive transcript")
            self.current_history_id = None
        self._populate_roles()
        self._refresh_transcript()
        self._save_raw_transcript()
        self._set_busy(False, f"转写完成：{len(self.transcript.segments)} 段")
        self._update_llm_state()
        self.refresh_history()

    def _populate_roles(self) -> None:
        if not self.transcript:
            return
        self.role_table.blockSignals(True)
        self.role_table.setRowCount(len(self.transcript.speakers))
        for row, speaker in enumerate(self.transcript.speakers):
            speaker_item = QTableWidgetItem(f"Speaker {speaker}")
            speaker_item.setData(256, speaker)
            self.role_table.setItem(row, 0, speaker_item)
            role = QComboBox()
            role.setEditable(True)
            role.setAcceptDrops(False)
            role.lineEdit().setAcceptDrops(False)
            role.addItems([
                f"Speaker {speaker}", "主讲人", "主持人", "参与者", "访谈者", "受访者", "面试官", "我"
            ])
            role.setCurrentText(self.transcript.role_for(speaker))
            role.currentTextChanged.connect(lambda value, s=speaker: self._role_changed(s, value))
            self.role_table.setCellWidget(row, 1, role)
        self.role_table.blockSignals(False)

    def _role_changed(self, speaker: int, role: str) -> None:
        if not self.transcript:
            return
        cleaned = role.strip() or f"Speaker {speaker}"
        self.transcript.speaker_roles[speaker] = cleaned
        self.transcript.save()
        self._save_raw_transcript()
        self._refresh_transcript()

    def _refresh_transcript(self) -> None:
        if self.transcript:
            self.transcript_view.setPlainText(self.transcript.to_display_text())
            self.document_info.setText(
                f"{Path(self.transcript.source_file).name}  ·  {Transcript.format_time(self.transcript.duration_ms)}"
                f"  ·  {len(self.transcript.speakers)} 位说话人  ·  {len(self.transcript.segments)} 段记录"
            )

    def _save_raw_transcript(self) -> None:
        if not self.transcript:
            return
        target = Path("output")
        target.mkdir(parents=True, exist_ok=True)
        stem = Path(self.transcript.source_file).stem
        (target / f"{stem}_raw_transcript.json").write_text(
            json.dumps(self.transcript.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (target / f"{stem}_raw_transcript.md").write_text(
            self.transcript.to_markdown(), encoding="utf-8"
        )
        if self.current_history_id:
            try:
                self.history_store.update_transcript(self.current_history_id, self.transcript)
            except (OSError, ValueError, json.JSONDecodeError):
                logger.exception("Could not update archived transcript")

    def _provider(self) -> OpenAICompatibleProvider:
        return OpenAICompatibleProvider(self.config.base_url, self.config.api_key, self.config.model)

    def start_role_detection(self) -> None:
        if not self.transcript or not self.config.llm_ready:
            self._show_error("AI 未配置", "请先在“服务设置 → AI 整理”中配置 DeepSeek 或其他兼容服务。")
            return
        transcript = self.transcript
        self._set_busy(True, "正在推断角色…")
        self._run_task(lambda progress: InterviewAnalyzer(self._provider()).detect_roles(transcript), self._roles_done)

    def _roles_done(self, result: object) -> None:
        if self.transcript and isinstance(result, dict):
            self.transcript.speaker_roles.update(result)
            self.transcript.save()
            self._save_raw_transcript()
            self._populate_roles()
            self._refresh_transcript()
        self._set_busy(False, "角色推断完成，请人工确认")

    def start_polish(self) -> None:
        if not self.transcript or not self.config.llm_ready:
            self._show_error("AI 未配置", "请先在“服务设置 → AI 整理”中配置 DeepSeek 或其他兼容服务。")
            return
        transcript = self.transcript
        self._set_busy(True, "AI 正在结合全文校对转写…")
        self._run_task(lambda progress: self._provider().polish_transcript(transcript), self._polish_done)

    def _polish_done(self, result: object) -> None:
        if not self.transcript or not isinstance(result, dict):
            self._set_busy(False, "校对失败")
            self._show_error("校对失败", "AI 返回结构无效，原始转写未被修改。")
            return
        for index, text in result.items():
            self.transcript.segments[int(index)].text = str(text)
        self.transcript.save()
        self._save_raw_transcript()
        self.analysis_data = None
        self.analysis_mode = None
        self.report_markdown = ""
        self.qa_messages = []
        self.report_view.clear()
        self.chat_view.clear()
        if self.current_history_id:
            try:
                self.history_store.update_report(self.current_history_id, "", {}, "")
                self.history_store.update_chat(self.current_history_id, [])
            except (OSError, ValueError, json.JSONDecodeError):
                logger.exception("Could not clear archived AI results after transcript correction")
        self._refresh_transcript()
        self._set_busy(False, "AI 校对完成；请结合录音核对数字和关键信息")

    def start_analysis(self) -> None:
        if not self.transcript or not self.config.llm_ready:
            self._show_error("AI 未配置", "请先在“服务设置 → AI 整理”中配置 DeepSeek 或其他兼容服务。")
            return
        transcript = self.transcript
        mode = "interview" if self.scene_combo.currentIndex() == 1 else "general"
        self._set_busy(True, "AI 正在生成面试复盘…" if mode == "interview" else "AI 正在整理录音…")
        self._run_task(
            lambda progress: (mode, InterviewAnalyzer(self._provider()).analyze(transcript, mode)),
            self._analysis_done,
        )

    def _analysis_done(self, result: object) -> None:
        if (
            not isinstance(result, tuple) or len(result) != 2
            or not isinstance(result[1], dict) or not self.transcript
        ):
            self._set_busy(False, "分析失败")
            self._show_error("分析失败", "AI 返回结构无效。")
            return
        mode, data = result
        self.analysis_data = data
        self.analysis_mode = mode
        self.report_markdown = (
            render_report(data, self.transcript)
            if mode == "interview"
            else render_general_report(data, self.transcript)
        )
        self.report_view.setPlainText(self.report_markdown)
        self.tabs.setCurrentIndex(1)
        suffix = "interview_review" if mode == "interview" else "summary"
        default_path = Path("output") / f"{Path(self.transcript.source_file).stem}_{suffix}.md"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        default_path.write_text(self.report_markdown, encoding="utf-8")
        if self.current_history_id:
            try:
                self.history_store.update_report(self.current_history_id, mode, data, self.report_markdown)
            except (OSError, ValueError, json.JSONDecodeError):
                logger.exception("Could not update archived report")
        self.refresh_history()
        self._set_busy(False, "AI 整理完成")
        self._update_llm_state()

    def start_recording_chat(self) -> None:
        question = self.chat_input.text().strip()
        if not question:
            return
        if not self.transcript or not self.config.llm_ready:
            self._show_error("AI 未配置", "请先完成转写，并在“服务设置 → AI 整理”中配置文字 AI 服务。")
            return
        transcript = self.transcript
        report = self.analysis_data
        conversation = list(self.qa_messages)
        self._set_busy(True, "AI 正在查阅录音并回答…")
        self._run_task(
            lambda progress: (
                question,
                self._provider().answer_about_recording(transcript, question, report, conversation),
            ),
            self._recording_chat_done,
        )

    def _recording_chat_done(self, result: object) -> None:
        if (
            not isinstance(result, tuple) or len(result) != 2
            or not isinstance(result[0], str) or not isinstance(result[1], dict)
        ):
            self._set_busy(False, "问答失败")
            self._show_error("问答失败", "AI 返回结构无效。")
            return
        question, answer = result
        if self.chat_input.text().strip() == question:
            self.chat_input.clear()
        markdown = render_qa_answer(question, answer)
        self.qa_messages.append({"question": question, "answer": answer, "markdown": markdown})
        self.chat_view.setPlainText(render_qa_conversation(self.qa_messages))
        self.ai_tabs.setCurrentIndex(1)
        self.tabs.setCurrentIndex(1)
        if self.current_history_id:
            try:
                self.history_store.update_chat(self.current_history_id, self.qa_messages)
            except (OSError, ValueError, json.JSONDecodeError):
                logger.exception("Could not update archived recording Q&A")
        self._set_busy(False, "录音问答完成")

    def refresh_history(self) -> None:
        if not hasattr(self, "history_table"):
            return
        checked = set()
        for row in range(self.history_table.rowCount()):
            item = self.history_table.item(row, 0)
            name = self.history_table.item(row, 2)
            if item and name and item.checkState() == Qt.CheckState.Checked:
                checked.add(str(name.data(Qt.ItemDataRole.UserRole)))
        records = self.history_store.list()
        self.history_table.setRowCount(len(records))
        scene_names = {"interview": "面试复盘", "general": "通用整理"}
        for row, record in enumerate(records):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked if record["id"] in checked else Qt.CheckState.Unchecked)
            self.history_table.setItem(row, 0, check)
            created = str(record.get("created_at", "")).replace("T", " ")[:16]
            values = [
                created,
                str(record.get("source_name", "未知录音")),
                scene_names.get(str(record.get("scene", "")), "未分类"),
                Transcript.format_time(int(record.get("duration_ms", 0))),
                str(record.get("speaker_count", 0)),
                "已整理" if record.get("analysis_data") else ("有问答" if record.get("qa_messages") else "仅转写"),
            ]
            for column, value in enumerate(values, 1):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setData(Qt.ItemDataRole.UserRole, record["id"])
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.history_table.setItem(row, column, item)
        self.history_open_button.setEnabled(bool(records) and not self._busy)
        self.history_delete_button.setEnabled(bool(records) and not self._busy)

    def open_history_record(self, *_args) -> None:
        row = self.history_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "选择历史记录", "请先在表格中选择一条记录。")
            return
        item = self.history_table.item(row, 2)
        record_id = str(item.data(Qt.ItemDataRole.UserRole)) if item else ""
        try:
            record = self.history_store.get(record_id)
            transcript = self.history_store.load_transcript(record_id)
        except Exception as exc:
            self._show_error("无法打开历史记录", str(exc))
            return
        self.current_history_id = record_id
        self.transcript = transcript
        source = Path(transcript.source_file)
        self.audio_path = source if source.is_file() else None
        self.file_path.setText(str(source))
        self.file_info.setText("原始录音可用" if self.audio_path else "原始录音已移动或删除；仍可阅读和导出历史文字")
        self.scene_combo.setCurrentIndex(1 if record.get("scene") == "interview" else 0)
        self.analysis_mode = str(record.get("analysis_mode") or "") or None
        self.analysis_data = record.get("analysis_data") if isinstance(record.get("analysis_data"), dict) else None
        self.report_markdown = str(record.get("report_markdown") or "")
        self.report_view.setPlainText(self.report_markdown)
        messages = record.get("qa_messages")
        self.qa_messages = messages if isinstance(messages, list) else []
        self.chat_view.setPlainText(render_qa_conversation(self.qa_messages))
        self.chat_input.clear()
        self._populate_roles()
        self._refresh_transcript()
        self.tabs.setCurrentIndex(0)
        self._update_llm_state()
        self.statusBar().showMessage(f"已打开历史记录：{record.get('source_name', '')}")

    def delete_history_record(self) -> None:
        row = self.history_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "选择历史记录", "请先在表格中选择一条记录。")
            return
        item = self.history_table.item(row, 2)
        record_id = str(item.data(Qt.ItemDataRole.UserRole)) if item else ""
        name = item.text() if item else "这条记录"
        answer = QMessageBox.question(
            self,
            "删除历史记录",
            f"确定删除“{name}”的历史文字和 AI 报告吗？\n\n原始录音不会被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.history_store.delete(record_id)
        except (OSError, ValueError) as exc:
            self._show_error("删除失败", str(exc))
            return
        if self.current_history_id == record_id:
            self.current_history_id = None
        self.refresh_history()
        self.statusBar().showMessage(f"已删除历史记录：{name}")

    def _checked_history_ids(self) -> list[str]:
        result = []
        for row in range(self.history_table.rowCount()):
            check = self.history_table.item(row, 0)
            name = self.history_table.item(row, 2)
            if check and name and check.checkState() == Qt.CheckState.Checked:
                result.append(str(name.data(Qt.ItemDataRole.UserRole)))
        return result

    def start_history_analysis(self) -> None:
        record_ids = self._checked_history_ids()
        if not 2 <= len(record_ids) <= 8:
            QMessageBox.information(self, "选择对比记录", "请勾选 2–8 条记录后再生成多次复盘。")
            return
        if not self.config.llm_ready:
            self._show_error("AI 未配置", "请先在“服务设置 → AI 整理”中配置 DeepSeek 或其他兼容服务。")
            return
        try:
            payload = self.history_store.comparison_payload(record_ids)
        except Exception as exc:
            self._show_error("无法读取历史记录", str(exc))
            return
        self._set_busy(True, "AI 正在比较多次记录…")
        self._run_task(lambda progress: self._provider().analyze_history(payload), self._history_analysis_done)

    def _history_analysis_done(self, result: object) -> None:
        if not isinstance(result, dict):
            self._set_busy(False, "多次复盘失败")
            self._show_error("多次复盘失败", "AI 返回结构无效。")
            return
        self.comparison_data = result
        markdown = render_history_report(result)
        self.comparison_view.setPlainText(markdown)
        target = Path("output") / "history_comparison.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown, encoding="utf-8")
        self.tabs.setCurrentIndex(4)
        self._set_busy(False, "多次复盘完成")

    def export_file(self, kind: str) -> None:
        if not self.transcript:
            return
        stem = Path(self.transcript.source_file).stem
        exports: dict[str, tuple[str, str, str]] = {
            "transcript_txt": (self.transcript.to_plain_text(), f"{stem}_transcript.txt", "文本文件 (*.txt)"),
            "transcript_md": (self.transcript.to_markdown(), f"{stem}_transcript.md", "Markdown (*.md)"),
            "transcript_json": (
                json.dumps(self.transcript.to_dict(), ensure_ascii=False, indent=2),
                f"{stem}_transcript.json", "JSON (*.json)",
            ),
            "transcript_srt": (self.transcript.to_srt(), f"{stem}.srt", "字幕文件 (*.srt)"),
        }
        if kind.startswith("report_") and not self.analysis_data:
            QMessageBox.information(self, "尚无 AI 整理结果", "请先完成 AI 整理，再导出报告。")
            return
        if kind == "chat_md" and not self.qa_messages:
            QMessageBox.information(self, "尚无问答记录", "请先在“基于录音提问”中完成至少一次问答。")
            return
        if kind == "report_md":
            suffix = "interview_review" if self.analysis_mode == "interview" else "summary"
            item = (self.report_markdown, f"{stem}_{suffix}.md", "Markdown (*.md)")
        elif kind == "report_json":
            suffix = "interview_review" if self.analysis_mode == "interview" else "summary"
            item = (
                json.dumps(self.analysis_data, ensure_ascii=False, indent=2),
                f"{stem}_{suffix}.json", "JSON (*.json)",
            )
        elif kind == "chat_md":
            item = (render_qa_conversation(self.qa_messages), f"{stem}_recording_qa.md", "Markdown (*.md)")
        else:
            item = exports.get(kind)
        if not item:
            return
        content, suggested, file_filter = item
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出文件", str(Path("output") / suggested), file_filter
        )
        if not filename:
            return
        try:
            Path(filename).write_text(content, encoding="utf-8")
            self.statusBar().showMessage(f"已导出：{filename}")
        except OSError as exc:
            logger.exception("Export failed")
            self._show_error("导出失败", f"无法写入文件：{exc}")

    def open_settings(self) -> None:
        dialog = ConfigDialog(self.config, self)
        if dialog.exec():
            self.config = dialog.value()
            try:
                self.config.save()
            except OSError as exc:
                self._show_error("保存失败", f"无法保存本地配置：{exc}")
                return
            self._update_llm_state()
            self.statusBar().showMessage("服务设置已保存")

    def offer_startup_choice(self) -> None:
        if self.config.startup_choice:
            return
        dialog = QMessageBox(self)
        dialog.setWindowTitle("欢迎使用聆页舟")
        dialog.setText("选择你希望使用的转写方式")
        dialog.setInformativeText("云端：无需下载模型，需配置语音服务凭据，录音会上传。\n本地：推荐按需下载约 1.62 GB 的 Whisper 高质量模型，转写时录音留在电脑上。\n之后可以随时切换；AI 整理单独配置。")
        cloud = dialog.addButton("使用云端转写", QMessageBox.AcceptRole)
        local = dialog.addButton("使用本地转写", QMessageBox.ActionRole)
        dialog.addButton("稍后选择", QMessageBox.RejectRole)
        dialog.exec()
        if dialog.clickedButton() not in (cloud, local):
            return
        self.config.startup_choice = "cloud" if dialog.clickedButton() == cloud else "local"
        try:
            self.config.save()
        except OSError as exc:
            self._show_error("无法保存偏好", str(exc))
        self.model_combo.setCurrentIndex(0 if self.config.startup_choice == "cloud" else 1)
        if self.config.startup_choice == "local":
            self.open_models()
        else:
            self.open_settings()

    def open_models(self, selected_engine: str | None = None) -> None:
        if self._busy:
            return
        from lingyezhou.ui.model_dialog import ModelDialog
        # Release in-memory weights before permitting removal or a directory change.
        for backend in self.backends.values():
            if backend is not None:
                backend._model = None
        engine = selected_engine or self.model_combo.currentData() or "whisper"
        dialog = ModelDialog(self.config, engine, self)
        dialog.exec()
        self.config, self.model_store = dialog.config, dialog.store
        for backend in self.backends.values():
            if backend is not None:
                backend.store = self.model_store
        from lingyezhou.ui.workspace_view import update_engine_hint
        update_engine_hint(self)

    def _run_task(self, task, on_success) -> None:
        thread = QThread(self)
        worker = TaskWorker(task)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda message: self.progress.setFormat(message))
        worker.progress.connect(self.statusBar().showMessage)
        worker.finished.connect(on_success)
        worker.finished.connect(thread.quit)
        worker.failed.connect(self._task_failed)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._forget_task(thread, worker))
        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()

    def _forget_task(self, thread: QThread, worker: TaskWorker) -> None:
        if thread in self._threads:
            self._threads.remove(thread)
        if worker in self._workers:
            self._workers.remove(worker)

    def _task_failed(self, message: str, traceback_text: str) -> None:
        logger.error("Background task failed:\n%s", traceback_text)
        self._set_busy(False, "操作失败")
        self._show_error("操作失败", message or "发生未知错误，详情已写入日志。")

    def _set_busy(self, busy: bool, message: str) -> None:
        self._busy = busy
        self.import_action.setEnabled(not busy)
        self.drop_zone.setEnabled(not busy)
        self._highlight_drop(False)
        self.settings_button.setEnabled(not busy)
        self.models_button.setEnabled(not busy)
        self.choose_button.setEnabled(not busy)
        self.transcribe_button.setEnabled(not busy and self.audio_path is not None)
        self.model_combo.setEnabled(not busy)
        self.scene_combo.setEnabled(not busy)
        self.role_table.setEnabled(not busy)
        self.history_refresh_button.setEnabled(not busy)
        self.history_open_button.setEnabled(not busy and self.history_table.rowCount() > 0)
        self.history_delete_button.setEnabled(not busy and self.history_table.rowCount() > 0)
        self.history_table.setEnabled(not busy)
        self.compare_button.setEnabled(not busy and self.config.llm_ready)
        self.chat_input.setEnabled(not busy)
        self.report_export_button.setEnabled(not busy and bool(self.analysis_data or self.qa_messages))
        self.progress.setRange(0, 0 if busy else 100)
        self.progress.setValue(0 if busy else 100)
        self.progress.setFormat(message)
        self.statusBar().showMessage(message)
        if busy:
            self.detect_roles_button.setEnabled(False)
            self.polish_button.setEnabled(False)
            self.analyze_button.setEnabled(False)
            self.chat_send_button.setEnabled(False)
            self.export_button.setEnabled(False)
        else:
            self._update_llm_state()

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event) -> None:
        if any(thread.isRunning() for thread in self._threads):
            QMessageBox.information(self, "任务处理中", "请等待当前任务完成再关闭窗口。云端请求已经发出时，关闭窗口不会取消服务计费。")
            event.ignore()
            return
        super().closeEvent(event)
