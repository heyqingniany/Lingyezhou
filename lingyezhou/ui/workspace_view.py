"""Presentation for the desktop workspace; operations live in MainWindow."""
from pathlib import Path
from lingyezhou.paths import resource_path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QPlainTextEdit, QProgressBar, QTableWidget, QMenu,
    QTabWidget, QWidget, QScrollArea, QTextBrowser, QStyle, QSizePolicy,
)

ICON_PATH = resource_path("assets/lingyezhou.svg")


class ReportView(QTextBrowser):
    def setPlainText(self, text):
        # Existing controllers supply Markdown; render it for comfortable reading.
        self.setMarkdown(text)


def label(text, name="", wrap=False):
    result = QLabel(text)
    result.setObjectName(name)
    result.setWordWrap(wrap)
    return result


def build_workspace(w):
    w.setWindowIcon(QIcon(str(ICON_PATH)))
    w.setMinimumSize(980, 680)
    w.resize(1280, 860)
    font = QFont("Microsoft YaHei UI", 10)
    w.setFont(font)
    root = QWidget()
    root.setObjectName("workspace")
    w.setCentralWidget(root)
    outer = QHBoxLayout(root)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    sidebar = QFrame()
    sidebar.setObjectName("sidebar")
    sidebar.setFixedWidth(304)
    side = QVBoxLayout(sidebar)
    side.setContentsMargins(22, 24, 22, 18)
    side.setSpacing(14)
    brand = QHBoxLayout()
    mark = QLabel()
    mark.setFixedSize(42, 42)
    mark.setPixmap(QIcon(str(ICON_PATH)).pixmap(QSize(42, 42)))
    brand.addWidget(mark)
    titles = QVBoxLayout()
    titles.setSpacing(0)
    titles.addWidget(label("聆页舟", "brand"))
    titles.addWidget(label("让声音落成文字", "muted"))
    brand.addLayout(titles)
    brand.addStretch()
    side.addLayout(brand)
    side.addSpacing(8)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    contents = QWidget()
    fields = QVBoxLayout(contents)
    fields.setContentsMargins(0, 0, 4, 0)
    fields.setSpacing(12)
    fields.addWidget(label("录音工作台", "section"))
    w.choose_button = QPushButton("  导入录音")
    w.choose_button.setIcon(w.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
    w.choose_button.clicked.connect(w.choose_audio)
    w.choose_button.setToolTip("选择录音（Ctrl+O），也可拖放文件到窗口任意位置")
    fields.addWidget(w.choose_button)
    w.file_path = QLineEdit()
    w.file_path.setReadOnly(True)
    w.file_path.setPlaceholderText("尚未选择文件")
    fields.addWidget(w.file_path)
    w.file_info = label("支持 WAV、MP3、M4A、FLAC", "muted", True)
    fields.addWidget(w.file_info)
    fields.addSpacing(10)
    fields.addWidget(label("识别引擎", "section"))
    w.model_combo = QComboBox()
    w.model_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    w.model_combo.setMinimumContentsLength(12)
    w.model_combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    for text in w.backends:
        w.model_combo.addItem(text, w.backend_engines[text])
    if w.config.startup_choice == "local" or (not w.config.startup_choice and not w.config.cloud_ready):
        preferred = "whisper" if w.model_store.ready("whisper") else (
            "sensevoice" if w.model_store.ready("sensevoice") else "whisper"
        )
        w.model_combo.setCurrentIndex(w.model_combo.findData(preferred))
    fields.addWidget(w.model_combo)
    w.engine_hint = label("", "muted", True)
    fields.addWidget(w.engine_hint)
    w.model_combo.currentIndexChanged.connect(lambda: update_engine_hint(w))
    fields.addWidget(label("整理场景", "section"))
    w.scene_combo = QComboBox()
    w.scene_combo.addItems(["通用录音整理", "技术面试复盘"])
    fields.addWidget(w.scene_combo)
    fields.addWidget(label("专业词汇  /  可选", "section"))
    w.hotwords = QPlainTextEdit()
    w.hotwords.setPlaceholderText("每行一个词\n例如：产品名称、技术术语")
    w.hotwords.setFixedHeight(100)
    fields.addWidget(w.hotwords)
    w.transcribe_button = QPushButton("开始转写")
    w.transcribe_button.setObjectName("primaryButton")
    w.transcribe_button.setEnabled(False)
    w.transcribe_button.clicked.connect(w.start_transcription)
    fields.addStretch()
    scroll.setWidget(contents)
    side.addWidget(scroll, 1)
    side.addWidget(w.transcribe_button)
    w.ffmpeg_banner = label("", "muted", True)
    side.addWidget(w.ffmpeg_banner)
    w.llm_status = label("", "muted", True)
    side.addWidget(w.llm_status)
    w.settings_button = QPushButton("服务设置")
    w.settings_button.clicked.connect(w.open_settings)
    w.models_button = QPushButton("本地模型 · 下载与管理")
    w.models_button.clicked.connect(w.open_models)
    side.addWidget(w.models_button)
    side.addWidget(w.settings_button)
    outer.addWidget(sidebar)

    main = QWidget()
    layout = QVBoxLayout(main)
    layout.setContentsMargins(30, 26, 30, 16)
    layout.setSpacing(18)
    header = QHBoxLayout()
    heading = QVBoxLayout()
    heading.setSpacing(4)
    heading.addWidget(label("录音工作台", "heading"))
    heading.addWidget(label("从原始声音，到清晰记录。", "muted"))
    header.addLayout(heading, 1)
    w.export_button = QPushButton("导出文件")
    w.export_button.setIcon(w.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
    menu = QMenu(w.export_button)
    for title, kind in [("转写文本 · TXT", "transcript_txt"), ("转写文档 · Markdown", "transcript_md"),
                        ("结构化转写 · JSON", "transcript_json"), ("字幕 · SRT", "transcript_srt"),
                        ("AI 报告 · Markdown", "report_md"), ("AI 结果 · JSON", "report_json")]:
        if kind == "report_md":
            menu.addSeparator()
        menu.addAction(title).triggered.connect(lambda checked=False, value=kind: w.export_file(value))
    w.export_button.setMenu(menu)
    header.addWidget(w.export_button)
    layout.addLayout(header)

    w.drop_zone = QPushButton("拖放录音到窗口，即可导入\n或点击选择文件 · Ctrl+O")
    w.drop_zone.setObjectName("dropZone")
    w.drop_zone.setMinimumHeight(78)
    w.drop_zone.setCursor(Qt.CursorShape.PointingHandCursor)
    w.drop_zone.setToolTip("支持 WAV、MP3、M4A、FLAC；每次导入一个录音。导入后由你点击开始转写。")
    w.drop_zone.clicked.connect(w.choose_audio)
    layout.addWidget(w.drop_zone)

    w.document_info = label("尚无转写记录", "documentInfo")
    w.document_info.setWordWrap(True)
    layout.addWidget(w.document_info)
    w.tabs = QTabWidget()
    transcript = QWidget()
    pane = QVBoxLayout(transcript)
    pane.setContentsMargins(22, 20, 22, 20)
    pane.setSpacing(16)
    toolbar = QHBoxLayout()
    toolbar.addWidget(label("带时间轴的完整记录", "section"), 1)
    w.polish_button = QPushButton("AI 校对")
    w.polish_button.clicked.connect(w.start_polish)
    toolbar.addWidget(w.polish_button)
    pane.addLayout(toolbar)
    w.transcript_view = QPlainTextEdit()
    w.transcript_view.setObjectName("transcriptEditor")
    w.transcript_view.setReadOnly(True)
    w.transcript_view.setPlaceholderText("让每一段对话，都有迹可循。\n\n拖放一段录音到窗口，或按 Ctrl+O 选择文件。\n\n确认识别引擎后，点击「开始转写」。完成后可在这里阅读原文、查看说话人，并导出文字或字幕。")
    pane.addWidget(w.transcript_view, 1)
    w.tabs.addTab(transcript, "转写原文")

    report = QWidget()
    pane = QVBoxLayout(report)
    pane.setContentsMargins(22, 20, 22, 20)
    toolbar = QHBoxLayout()
    w.report_title = label("摘要、重点与待办事项", "section")
    toolbar.addWidget(w.report_title, 1)
    w.report_export_button = QPushButton("导出")
    report_export_menu = QMenu(w.report_export_button)
    report_export_menu.addAction("整理报告 · Markdown").triggered.connect(lambda: w.export_file("report_md"))
    report_export_menu.addAction("整理数据 · JSON").triggered.connect(lambda: w.export_file("report_json"))
    report_export_menu.addSeparator()
    report_export_menu.addAction("问答记录 · Markdown").triggered.connect(lambda: w.export_file("chat_md"))
    w.report_export_button.setMenu(report_export_menu)
    toolbar.addWidget(w.report_export_button)
    w.analyze_button = QPushButton("AI 整理")
    w.analyze_button.setObjectName("primaryButton")
    w.analyze_button.clicked.connect(w.start_analysis)
    toolbar.addWidget(w.analyze_button)
    pane.addLayout(toolbar)
    w.ai_tabs = QTabWidget()
    result_page = QWidget()
    result_layout = QVBoxLayout(result_page)
    result_layout.setContentsMargins(0, 8, 0, 0)
    w.report_view = ReportView()
    w.report_view.setOpenExternalLinks(False)
    w.report_view.setPlaceholderText("把长对话整理成重点。\n\n完成转写并配置文字 AI 服务后，即可生成摘要、决策与待办。")
    result_layout.addWidget(w.report_view)
    w.ai_tabs.addTab(result_page, "整理结果")

    chat_page = QWidget()
    chat_layout = QVBoxLayout(chat_page)
    chat_layout.setContentsMargins(0, 8, 0, 0)
    chat_layout.setSpacing(10)
    chat_layout.addWidget(label("围绕当前录音追问事实、承诺、分歧和待核实事项。法律类回答仅作材料整理与一般信息参考。", "muted", True))
    w.chat_view = ReportView()
    w.chat_view.setOpenExternalLinks(False)
    w.chat_view.setPlaceholderText("尚无问答记录。可以询问：对方承诺了什么？哪些事项还没有确认？有哪些费用或交付条件应写进合同？")
    chat_layout.addWidget(w.chat_view, 1)
    question_row = QHBoxLayout()
    w.chat_input = QLineEdit()
    w.chat_input.setPlaceholderText("输入关于这段录音的问题，按 Enter 发送")
    w.chat_input.returnPressed.connect(w.start_recording_chat)
    w.chat_input.textChanged.connect(w._update_chat_button)
    question_row.addWidget(w.chat_input, 1)
    w.chat_send_button = QPushButton("发送")
    w.chat_send_button.setObjectName("primaryButton")
    w.chat_send_button.clicked.connect(w.start_recording_chat)
    question_row.addWidget(w.chat_send_button)
    chat_layout.addLayout(question_row)
    w.ai_tabs.addTab(chat_page, "基于录音提问")
    pane.addWidget(w.ai_tabs, 1)
    w.tabs.addTab(report, "AI 整理")

    people = QWidget()
    pane = QVBoxLayout(people)
    pane.setContentsMargins(22, 20, 22, 20)
    toolbar = QHBoxLayout()
    toolbar.addWidget(label("为说话人设置名称或角色", "section"), 1)
    w.detect_roles_button = QPushButton("AI 推断角色")
    w.detect_roles_button.clicked.connect(w.start_role_detection)
    toolbar.addWidget(w.detect_roles_button)
    pane.addLayout(toolbar)
    pane.addWidget(label("转写完成后，可直接编辑角色列；修改会同步到原文与导出文件。", "muted", True))
    w.role_table = QTableWidget(0, 2)
    w.role_table.setHorizontalHeaderLabels(["说话人", "显示名称 / 角色"])
    w.role_table.verticalHeader().hide()
    w.role_table.horizontalHeader().setStretchLastSection(True)
    w.role_table.setColumnWidth(0, 160)
    w.role_table.setShowGrid(False)
    pane.addWidget(w.role_table, 1)
    w.tabs.addTab(people, "说话人")

    history = QWidget()
    pane = QVBoxLayout(history)
    pane.setContentsMargins(22, 20, 22, 20)
    pane.setSpacing(12)
    toolbar = QHBoxLayout()
    toolbar.addWidget(label("本地录音档案", "section"), 1)
    w.history_refresh_button = QPushButton("刷新")
    w.history_refresh_button.clicked.connect(w.refresh_history)
    toolbar.addWidget(w.history_refresh_button)
    w.history_open_button = QPushButton("打开所选记录")
    w.history_open_button.clicked.connect(w.open_history_record)
    toolbar.addWidget(w.history_open_button)
    w.history_delete_button = QPushButton("删除")
    w.history_delete_button.clicked.connect(w.delete_history_record)
    toolbar.addWidget(w.history_delete_button)
    pane.addLayout(toolbar)
    pane.addWidget(label("每次转写完成后自动保存文字、角色和 AI 报告；原始音频仍保留在原位置。删除历史不会删除录音。勾选至少两条记录可生成多次复盘。", "muted", True))
    w.history_table = QTableWidget(0, 7)
    w.history_table.setHorizontalHeaderLabels(["对比", "日期", "录音", "场景", "时长", "说话人", "整理状态"])
    w.history_table.verticalHeader().hide()
    w.history_table.setShowGrid(False)
    w.history_table.setColumnWidth(0, 55)
    w.history_table.setColumnWidth(1, 150)
    w.history_table.setColumnWidth(2, 260)
    w.history_table.setColumnWidth(3, 120)
    w.history_table.setColumnWidth(4, 80)
    w.history_table.setColumnWidth(5, 75)
    w.history_table.horizontalHeader().setStretchLastSection(True)
    w.history_table.doubleClicked.connect(w.open_history_record)
    pane.addWidget(w.history_table, 1)
    compare_row = QHBoxLayout()
    w.history_compare_hint = label("勾选 2–8 条同类记录，AI 会引用证据比较变化，不生成虚假分数。", "muted", True)
    compare_row.addWidget(w.history_compare_hint, 1)
    w.compare_button = QPushButton("生成多次复盘")
    w.compare_button.setObjectName("primaryButton")
    w.compare_button.clicked.connect(w.start_history_analysis)
    compare_row.addWidget(w.compare_button)
    pane.addLayout(compare_row)
    w.tabs.addTab(history, "历史记录")

    comparison = QWidget()
    pane = QVBoxLayout(comparison)
    pane.setContentsMargins(22, 20, 22, 20)
    pane.setSpacing(12)
    pane.addWidget(label("多次记录复盘", "section"))
    pane.addWidget(label("从表达、结构、专业知识、沟通策略和行动落实等维度寻找有证据的变化。", "muted", True))
    w.comparison_view = ReportView()
    w.comparison_view.setPlaceholderText("在“历史记录”中勾选至少两条记录，然后点击“生成多次复盘”。")
    pane.addWidget(w.comparison_view, 1)
    w.tabs.addTab(comparison, "多次复盘")
    layout.addWidget(w.tabs, 1)
    w.progress = QProgressBar()
    w.progress.setRange(0, 100)
    w.progress.setValue(0)
    w.progress.setTextVisible(False)
    w.progress.setFixedHeight(4)
    layout.addWidget(w.progress)
    outer.addWidget(main, 1)
    w.scene_combo.currentIndexChanged.connect(w._scene_changed)
    update_engine_hint(w)
    w.statusBar().showMessage("就绪 · 拖放录音到窗口，或按 Ctrl+O 导入")


def update_engine_hint(w):
    engine = w.model_combo.currentData()
    cloud = engine is None
    term_hint = "支持术语提示。" if engine in {"whisper", "paraformer"} else "词表仅供 AI 校对使用。"
    w.engine_hint.setText("录音上传至火山引擎，按账户套餐计费。词表仅供 AI 校对使用。" if cloud else
                         ("本地模型已就绪，录音无需上传。" if w.model_store.ready(engine) else "本地模型未准备好，请点击下方「本地模型」下载。") +
                         term_hint)


STYLE = """
QWidget { color: #24324A; font-size: 10pt; }
QWidget#workspace { background: #F5F7FA; }
QFrame#sidebar { background: #EDF1F6; border-right: 1px solid #DCE3EB; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
QLabel { background: transparent; }
QLabel#brand { font-size: 15pt; font-weight: 700; color: #172B4B; }
QLabel#heading { font-size: 23pt; font-weight: 700; color: #172B4B; }
QLabel#muted { color: #6B7B90; font-size: 9pt; }
QLabel#section { font-weight: 600; color: #43536C; }
QLabel#documentInfo { color: #65768D; padding: 12px 16px; background: #EAF0F7; border-radius: 8px; }
QPushButton { background: #FFFFFF; border: 1px solid #D4DDE8; border-radius: 7px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #E7EFFA; border-color: #9BB3D7; }
QPushButton:pressed { background: #D6E4F6; }
QPushButton#dropZone { background: #F0F5FC; border: 2px dashed #B7C9DF; color: #43638C; border-radius: 10px; padding: 12px; }
QPushButton#dropZone:hover, QPushButton#dropZone[dragActive="true"] { background: #E0F3EF; border-color: #36AD9B; color: #196D60; }
QPushButton#dropZone:disabled { background: #EDF0F5; border-color: #D4DDE8; color: #96A3B4; }
QPushButton#primaryButton { background: #244F86; color: white; border-color: #244F86; }
QPushButton#primaryButton:hover { background: #1B406F; }
QPushButton:disabled, QPushButton#primaryButton:disabled { background: #E8EDF3; color: #96A3B4; border-color: #DFE5ED; }
QLineEdit, QComboBox, QPlainTextEdit, QTextBrowser { background: white; border: 1px solid #D7E0EA; border-radius: 7px; padding: 9px; selection-background-color: #D8E9FA; selection-color: #172B4B; }
QComboBox { min-height: 22px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #D8E9FA; padding: 6px; }
QPlainTextEdit#transcriptEditor, QTextBrowser { border: none; font-size: 11pt; padding: 8px; }
QTabWidget::pane { background: white; border: 1px solid #DDE5EE; border-radius: 9px; }
QTabBar::tab { background: transparent; color: #738298; padding: 12px 20px; margin-right: 10px; border-bottom: 3px solid transparent; }
QTabBar::tab:selected { color: #244F86; border-bottom: 3px solid #244F86; font-weight: 600; }
QTabBar::tab:hover { color: #244F86; }
QTableWidget { background: white; border: none; selection-background-color: #EEF4FC; }
QHeaderView::section { background: #F4F7FA; color: #718096; border: none; padding: 12px; }
QProgressBar { background: #E4EAF2; border: none; border-radius: 2px; }
QProgressBar::chunk { background: #36AD9B; border-radius: 2px; }
QStatusBar { background: #F5F7FA; color: #66768C; font-size: 9pt; }
QStatusBar::item { border: none; }
QMenu { background: white; border: 1px solid #DCE3EB; padding: 6px; }
QMenu::item { padding: 9px 22px; }
QMenu::item:selected { background: #EAF1FA; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #CED8E5; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
