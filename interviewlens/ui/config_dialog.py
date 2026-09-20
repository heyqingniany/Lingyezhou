from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from interviewlens.config import AppConfig


class ConfigDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("服务设置 · 云端识别与 AI 整理")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        note = QLabel("配置仅保存在本机 config.local.json（已加入 .gitignore）。API Key 以明文保存。")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        cloud_note = QLabel(
            '云端转写：<a href="https://www.volcengine.com/docs/6561/1354868?lang=zh">豆包录音文件识别接入说明</a><br>'
            '请选择与控制台已开通服务对应的版本。录音上传火山引擎，按账户套餐计费。<br>'
            '新版控制台填写 API Key；旧版填写 App ID + Access Token。与下方文字 AI 密钥独立。'
        )
        cloud_note.setOpenExternalLinks(True)
        cloud_note.setWordWrap(True)
        form.addRow(cloud_note)
        self.cloud_mode = QComboBox()
        self.cloud_mode.addItem("录音文件识别 2.0（标准版）", "standard")
        self.cloud_mode.addItem("录音文件识别极速版（单独开通）", "flash")
        self.cloud_mode.setCurrentIndex(max(0, self.cloud_mode.findData(config.cloud_mode)))
        form.addRow("已开通的语音服务", self.cloud_mode)
        self.cloud_api_key = QLineEdit(config.cloud_api_key)
        self.cloud_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.cloud_app_id = QLineEdit(config.cloud_app_id)
        self.cloud_access_token = QLineEdit(config.cloud_access_token)
        self.cloud_access_token.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("语音 API Key（新版）", self.cloud_api_key)
        form.addRow("App ID（旧版）", self.cloud_app_id)
        form.addRow("Access Token（旧版）", self.cloud_access_token)
        form.addRow(QLabel("AI 整理 / 校对（可选，OpenAI-compatible）"))
        self.base_url = QLineEdit(config.base_url)
        self.base_url.setPlaceholderText("https://api.openai.com/v1")
        self.api_key = QLineEdit(config.api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-... 或本地服务要求的占位值")
        self.model = QLineEdit(config.model)
        self.model.setPlaceholderText("模型名称")
        form.addRow("Base URL", self.base_url)
        form.addRow("API Key", self.api_key)
        form.addRow("Model", self.model)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> AppConfig:
        return AppConfig(
            base_url=self.base_url.text().strip(),
            api_key=self.api_key.text().strip(),
            model=self.model.text().strip(),
            cloud_api_key=self.cloud_api_key.text().strip(),
            cloud_app_id=self.cloud_app_id.text().strip(),
            cloud_access_token=self.cloud_access_token.text().strip(),
            cloud_mode=self.cloud_mode.currentData(),
        )
