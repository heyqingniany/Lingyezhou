from __future__ import annotations

import threading
from dataclasses import replace

from PySide6.QtCore import QObject, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QProgressBar, QFileDialog, QMessageBox)

from lingyezhou.asr.model_store import ModelStore, ENGINES, ENGINE_NAMES, DownloadCancelled, human_size


class DownloadWorker(QObject):
    progress = Signal(object, object, str)
    result = Signal(str, str)
    finished = Signal()

    def __init__(self, store, engine):
        super().__init__()
        self.store, self.engine = store, engine
        self.cancel = threading.Event()

    def run(self):
        try:
            self.store.prepare(self.engine, self.progress.emit, self.cancel)
            self.result.emit("done", "模型已准备好。关闭此窗口后，点击「开始转写」。")
        except DownloadCancelled:
            self.result.emit("cancelled", "下载已暂停，已下载的部分保留；点击「下载 / 继续」可续传。")
        except Exception as exc:
            self.result.emit("failed", f"下载失败：{exc}\n已下载部分保留，检查网络或磁盘空间后点击重试。")
        finally:
            self.finished.emit()


class ModelDialog(QDialog):
    def __init__(self, config, engine="sensevoice", parent=None):
        super().__init__(parent)
        self.config = config
        self.store = ModelStore(config.model_directory)
        self.thread = None
        self.worker = None
        self.setWindowTitle("本地模型 · 按需下载")
        self.resize(660, 470)
        layout = QVBoxLayout(self)
        note = QLabel("云端转写无需下载模型。本地模型由你按需下载；下载完成后，录音和识别过程均留在电脑上。")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.engine = QComboBox()
        for key, name in ENGINE_NAMES.items():
            self.engine.addItem(name, key)
        self.engine.setCurrentIndex(max(0, self.engine.findData(engine)))
        layout.addWidget(self.engine)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.location = QLabel()
        self.location.setWordWrap(True)
        layout.addWidget(self.location)
        row = QHBoxLayout()
        self.choose = QPushButton("更换存储位置")
        self.choose.clicked.connect(self.choose_directory)
        row.addWidget(self.choose)
        self.open_folder = QPushButton("打开模型目录")
        self.open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root))))
        row.addWidget(self.open_folder)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.message = QLabel("点击下载后才会连接模型来源。模型文件下载后会校验 SHA-256。")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        layout.addStretch()
        row = QHBoxLayout()
        self.download = QPushButton("下载 / 继续")
        self.download.clicked.connect(self.start_download)
        row.addWidget(self.download)
        self.pause = QPushButton("暂停下载")
        self.pause.setEnabled(False)
        self.pause.clicked.connect(self.pause_download)
        row.addWidget(self.pause)
        self.delete = QPushButton("删除所选模型")
        self.delete.clicked.connect(self.delete_model)
        row.addWidget(self.delete)
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.reject)
        row.addWidget(self.close_button)
        layout.addLayout(row)
        self.engine.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        key = self.engine.currentData()
        ready = self.store.ready(key)
        detail = ({
            "whisper": "约 1.62 GB；准确率优先，支持中英混说和术语提示，暂不区分说话人。",
            "sensevoice": "速度优先；与 Paraformer 共用标点、分段和说话人模型。",
            "paraformer": "中文热词优先；与 SenseVoice 共用标点、分段和说话人模型。",
        })[key]
        self.summary.setText("已下载 · 可用于本地转写" if ready else
            f"未准备好 · 预计还需 {human_size(self.store.missing_estimate(key))}\n{detail}")
        self.location.setText(f"存储位置：{self.store.root}\n已安装模型占用：{human_size(self.store.installed_size())}")
        self.download.setText("已准备好" if ready else "下载 / 继续")
        self.download.setEnabled(not ready)
        self.delete.setEnabled(any(self.store.component_path(c).exists() for c in ENGINES[key]))
        self.open_folder.setEnabled(self.store.root.is_dir())

    def choose_directory(self):
        selected = QFileDialog.getExistingDirectory(self, "选择模型存储位置（创建专用子文件夹）", str(self.store.root.parent))
        if not selected:
            return
        proposed = replace(self.config, model_directory=selected)
        try:
            store = ModelStore(selected)
            store.component_path("sensevoice")
            proposed.save()
        except Exception as exc:
            QMessageBox.warning(self, "无法保存位置", str(exc))
            return
        self.config, self.store = proposed, store
        self.refresh()
        self.message.setText("已切换位置。原位置的模型保留；可选择原位置继续使用，也可在新位置下载。")

    def start_download(self):
        if self.thread:
            return
        estimate = human_size(self.store.missing_estimate(self.engine.currentData()))
        if QMessageBox.question(self, "下载本地模型", f"预计需要 {estimate} 存储空间。\n保存到：{self.store.root}\n\n是否开始下载？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.thread = QThread(self)
        self.worker = DownloadWorker(self.store, self.engine.currentData())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.show_progress)
        self.worker.result.connect(self.show_result)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.job_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        for widget in (self.engine, self.choose, self.delete, self.download):
            widget.setEnabled(False)
        self.pause.setEnabled(True)
        self.thread.start()

    def show_progress(self, current, total, message):
        self.progress.setRange(0, 1000 if total else 0)
        if total:
            self.progress.setValue(int(current * 1000 / total))
            self.progress.setFormat(f"{human_size(current)} / {human_size(total)} · %p%")
        self.message.setText(message)

    def show_result(self, status, message):
        self.progress.setRange(0, 1000)
        self.message.setText(message)

    def job_finished(self):
        self.thread, self.worker = None, None
        self.engine.setEnabled(True)
        self.choose.setEnabled(True)
        self.pause.setEnabled(False)
        self.refresh()

    def pause_download(self):
        if self.worker:
            self.worker.cancel.set()
            self.pause.setEnabled(False)
            self.message.setText("正在暂停，等待当前网络读取结束（通常不超过 20 秒）…")

    def delete_model(self):
        if self.thread:
            return
        if QMessageBox.question(self, "删除本地模型", "删除所选引擎及不再被其他引擎使用的共用模型？\n录音、报告和其他应用的模型缓存不会删除。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.store.delete_engine(self.engine.currentData())
            self.message.setText("模型已删除，需要时可以重新下载。")
        except Exception as exc:
            QMessageBox.warning(self, "无法删除模型", str(exc))
        self.refresh()

    def reject(self):
        if self.thread:
            self.pause_download()
            return
        super().reject()

    def closeEvent(self, event):
        if self.thread:
            self.pause_download()
            event.ignore()
        else:
            event.accept()
