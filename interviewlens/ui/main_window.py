from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QThread
from PySide6.QtGui import QAction
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

from interviewlens.analysis.interview_analyzer import InterviewAnalyzer
from interviewlens.analysis.report import render_general_report, render_report
from interviewlens.asr.paraformer import ParaformerBackend
from interviewlens.asr.doubao import DoubaoBackend
from interviewlens.asr.sensevoice import SenseVoiceBackend
from interviewlens.audio.ffmpeg import FFmpegProcessor
from interviewlens.config import AppConfig
from interviewlens.llm.openai_compatible import OpenAICompatibleProvider
from interviewlens.models.transcript import Transcript
from interviewlens.ui.config_dialog import ConfigDialog
from interviewlens.ui.workers import TaskWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("InterviewLens — 录音转写与 AI 整理")
        self.resize(1180, 820)
        self.config = AppConfig.load()
        self.ffmpeg = FFmpegProcessor()
        self.backends = {
            "豆包云端（需配置 · 按量计费）": None,
            "FunASR · SenseVoice（本地）": SenseVoiceBackend(),
            "FunASR · Paraformer（本地）": ParaformerBackend(),
        }
        self.audio_path: Path | None = None
        self.transcript: Transcript | None = None
        self.analysis_data: dict | None = None
        self.analysis_mode: str | None = None
        self.report_markdown: str = ""
        self._threads: list[QThread] = []
        self._workers: list[TaskWorker] = []
        self._build_ui()
        self._apply_style()
        self._update_llm_state()
        self._check_ffmpeg()

    def _build_ui(self) -> None:
        from interviewlens.ui.workspace_view import build_workspace
        build_workspace(self)

    def _apply_style(self) -> None:
        from interviewlens.ui.workspace_view import STYLE
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
        self.llm_status.setText("AI：已配置" if ready else "AI：未配置（ASR 不受影响）")
        available = ready and self.transcript is not None
        self.detect_roles_button.setEnabled(available)
        self.polish_button.setEnabled(available)
        self.analyze_button.setEnabled(available)
        self.export_button.setEnabled(bool(self.report_markdown or self.transcript))

    def choose_audio(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择录音", "", "音频文件 (*.wav *.mp3 *.m4a *.flac)"
        )
        if not filename:
            return
        try:
            info = self.ffmpeg.probe(filename)
        except Exception as exc:
            self._show_error("无法读取音频", str(exc))
            return
        self.audio_path = info.path
        self.file_path.setText(str(info.path))
        self.file_info.setText(
            f"文件名：{info.path.name}    时长：{Transcript.format_time(int(info.duration_seconds * 1000))}"
            f"    大小：{info.readable_size}"
        )
        self.transcribe_button.setEnabled(True)
        self.statusBar().showMessage("音频已就绪")

    def _hotword_list(self) -> list[str]:
        return [line.strip() for line in self.hotwords.toPlainText().splitlines() if line.strip()]

    def start_transcription(self) -> None:
        if not self.audio_path:
            return
        audio_path = self.audio_path
        cloud = self.model_combo.currentIndex() == 0
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
            if cloud and info.duration_seconds > 7200:
                raise ValueError("当前云端极速版支持不超过 2 小时的录音，请先分割文件。")
            progress("正在预处理音频…")
            normalized = self.ffmpeg.convert(audio_path)
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
        self.report_view.clear()
        self._populate_roles()
        self._refresh_transcript()
        self._save_raw_transcript()
        self._set_busy(False, f"转写完成：{len(self.transcript.segments)} 段")
        self._update_llm_state()

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

    def _provider(self) -> OpenAICompatibleProvider:
        return OpenAICompatibleProvider(self.config.base_url, self.config.api_key, self.config.model)

    def start_role_detection(self) -> None:
        if not self.transcript or not self.config.llm_ready:
            self._show_error("AI 未配置", "请先在“设置 → AI 设置”中填写 Base URL、API Key 和 Model。")
            return
        transcript = self.transcript
        self._set_busy(True, "正在推断角色…")
        self._run_task(lambda progress: InterviewAnalyzer(self._provider()).detect_roles(transcript), self._roles_done)

    def _roles_done(self, result: object) -> None:
        if self.transcript and isinstance(result, dict):
            self.transcript.speaker_roles.update(result)
            self.transcript.save()
            self._populate_roles()
            self._refresh_transcript()
        self._set_busy(False, "角色推断完成，请人工确认")

    def start_polish(self) -> None:
        if not self.transcript or not self.config.llm_ready:
            self._show_error("AI 未配置", "请先在“设置 → AI 设置”中填写 Base URL、API Key 和 Model。")
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
        self.analysis_data = None
        self.analysis_mode = None
        self.report_markdown = ""
        self.report_view.clear()
        self._refresh_transcript()
        self._set_busy(False, "AI 校对完成；请结合录音核对数字和关键信息")

    def start_analysis(self) -> None:
        if not self.transcript or not self.config.llm_ready:
            self._show_error("AI 未配置", "请先在“设置 → AI 设置”中填写 Base URL、API Key 和 Model。")
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
        self._set_busy(False, "AI 整理完成")
        self._update_llm_state()

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
        if kind == "report_md":
            suffix = "interview_review" if self.analysis_mode == "interview" else "summary"
            item = (self.report_markdown, f"{stem}_{suffix}.md", "Markdown (*.md)")
        elif kind == "report_json":
            suffix = "interview_review" if self.analysis_mode == "interview" else "summary"
            item = (
                json.dumps(self.analysis_data, ensure_ascii=False, indent=2),
                f"{stem}_{suffix}.json", "JSON (*.json)",
            )
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
            self.statusBar().showMessage("AI 设置已保存")

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
        self.settings_button.setEnabled(not busy)
        self.choose_button.setEnabled(not busy)
        self.transcribe_button.setEnabled(not busy and self.audio_path is not None)
        self.model_combo.setEnabled(not busy)
        self.scene_combo.setEnabled(not busy)
        self.role_table.setEnabled(not busy)
        self.progress.setRange(0, 0 if busy else 100)
        self.progress.setValue(0 if busy else 100)
        self.progress.setFormat(message)
        self.statusBar().showMessage(message)
        if busy:
            self.detect_roles_button.setEnabled(False)
            self.polish_button.setEnabled(False)
            self.analyze_button.setEnabled(False)
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
