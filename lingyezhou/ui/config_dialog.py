from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)

from lingyezhou.config import AppConfig


AI_PRESETS = {
    "deepseek": ("https://api.deepseek.com", "deepseek-flash"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
}


class ConfigDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.original_config = config
        self.setWindowTitle("服务设置")
        self.setMinimumSize(620, 480)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_ai_tab(config), "AI 整理")
        tabs.addTab(self._build_cloud_tab(config), "云端转写")
        layout.addWidget(tabs)
        privacy = QLabel("密钥仅保存在本机 config.local.json，目前为明文存储；请勿共享该文件。")
        privacy.setWordWrap(True)
        privacy.setObjectName("muted")
        layout.addWidget(privacy)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_ai_tab(self, config: AppConfig) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        intro = QLabel("用于 AI 校对、单次整理、角色推断和多次记录对比。DeepSeek 价格较低，默认推荐。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        group = QGroupBox("文字 AI 服务")
        form = QFormLayout(group)
        self.ai_provider = QComboBox()
        self.ai_provider.addItem("DeepSeek（推荐）", "deepseek")
        self.ai_provider.addItem("OpenAI", "openai")
        self.ai_provider.addItem("自定义 OpenAI-compatible", "custom")
        self.ai_provider.setCurrentIndex(max(0, self.ai_provider.findData(config.ai_provider)))
        self.base_url = QLineEdit(config.base_url)
        self.api_key = QLineEdit(config.api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("在服务商控制台创建的 API Key")
        self.model = QLineEdit(config.model)
        form.addRow("服务商", self.ai_provider)
        form.addRow("API Key", self.api_key)
        form.addRow("接口地址", self.base_url)
        form.addRow("模型", self.model)
        layout.addWidget(group)
        cost = QLabel("建议先用 deepseek-flash，适合控制日常整理成本。校对和整理会发送转写文字，不会发送原始录音。实际费用以服务商为准。")
        cost.setWordWrap(True)
        layout.addWidget(cost)
        layout.addStretch()
        self.ai_provider.currentIndexChanged.connect(self._apply_ai_preset)
        self._update_ai_editability()
        return tab

    def _apply_ai_preset(self) -> None:
        provider = self.ai_provider.currentData()
        if provider in AI_PRESETS:
            base_url, model = AI_PRESETS[provider]
            self.base_url.setText(base_url)
            self.model.setText(model)
        self._update_ai_editability()

    def _update_ai_editability(self) -> None:
        self.base_url.setReadOnly(self.ai_provider.currentData() != "custom")
        self.model.setReadOnly(False)

    def _build_cloud_tab(self, config: AppConfig) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        intro = QLabel("仅在选择“豆包云端”识别引擎时使用。录音会上传到火山引擎，并按账户套餐计费。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.cloud_mode = QComboBox()
        self.cloud_mode.addItem("录音文件识别 2.0（标准版）", "standard")
        self.cloud_mode.addItem("录音文件识别极速版（旧版）", "flash")
        self.cloud_mode.setCurrentIndex(max(0, self.cloud_mode.findData(config.cloud_mode)))
        layout.addWidget(self.cloud_mode)
        self.cloud_credentials = QStackedWidget()
        standard = QGroupBox("标准版凭据")
        standard_form = QFormLayout(standard)
        self.cloud_api_key = QLineEdit(config.cloud_api_key)
        self.cloud_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        standard_form.addRow("语音 API Key", self.cloud_api_key)
        self.cloud_credentials.addWidget(standard)
        legacy = QGroupBox("旧版凭据")
        legacy_form = QFormLayout(legacy)
        self.cloud_app_id = QLineEdit(config.cloud_app_id)
        self.cloud_access_token = QLineEdit(config.cloud_access_token)
        self.cloud_access_token.setEchoMode(QLineEdit.EchoMode.Password)
        legacy_form.addRow("App ID", self.cloud_app_id)
        legacy_form.addRow("Access Token", self.cloud_access_token)
        self.cloud_credentials.addWidget(legacy)
        layout.addWidget(self.cloud_credentials)
        help_label = QLabel('<a href="https://www.volcengine.com/docs/6561/1631584?lang=zh">查看火山引擎录音文件识别接入说明</a>')
        help_label.setOpenExternalLinks(True)
        layout.addWidget(help_label)
        layout.addStretch()
        self.cloud_mode.currentIndexChanged.connect(self._update_cloud_fields)
        self._update_cloud_fields()
        return tab

    def _update_cloud_fields(self) -> None:
        self.cloud_credentials.setCurrentIndex(0 if self.cloud_mode.currentData() == "standard" else 1)

    def value(self) -> AppConfig:
        return replace(
            self.original_config,
            ai_provider=self.ai_provider.currentData(),
            base_url=self.base_url.text().strip(),
            api_key=self.api_key.text().strip(),
            model=self.model.text().strip(),
            cloud_api_key=self.cloud_api_key.text().strip(),
            cloud_app_id=self.cloud_app_id.text().strip(),
            cloud_access_token=self.cloud_access_token.text().strip(),
            cloud_mode=self.cloud_mode.currentData(),
        )
