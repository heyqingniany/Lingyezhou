"""Presentation for the desktop workspace; operations live in MainWindow."""
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QPlainTextEdit, QProgressBar, QTableWidget, QMenu,
    QTabWidget, QWidget, QScrollArea, QTextBrowser, QStyle, QSizePolicy,
)

ICON_PATH = Path(__file__).resolve().parents[2] / "assets" / "interviewlens.svg"


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
    titles.addWidget(label("InterviewLens", "brand"))
    titles.addWidget(label("听见重点 · 留下价值", "muted"))
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
        w.model_combo.addItem(text)
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
    fields.addWidget(w.transcribe_button)
    fields.addStretch()
    scroll.setWidget(contents)
    side.addWidget(scroll, 1)
    w.ffmpeg_banner = label("", "muted", True)
    side.addWidget(w.ffmpeg_banner)
    w.llm_status = label("", "muted", True)
    side.addWidget(w.llm_status)
    w.settings_button = QPushButton("服务设置")
    w.settings_button.clicked.connect(w.open_settings)
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

    w.document_info = label("尚无转写记录", "documentInfo")
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
    w.transcript_view.setPlaceholderText("让每一段对话，都有迹可循。\n\n从左侧导入一段录音，选择识别引擎，然后点击「开始转写」。\n\n完成后，你可以在这里阅读原文、查看说话人，并导出文字或字幕。")
    pane.addWidget(w.transcript_view, 1)
    w.tabs.addTab(transcript, "转写原文")

    report = QWidget()
    pane = QVBoxLayout(report)
    pane.setContentsMargins(22, 20, 22, 20)
    toolbar = QHBoxLayout()
    w.report_title = label("摘要、重点与待办事项", "section")
    toolbar.addWidget(w.report_title, 1)
    w.analyze_button = QPushButton("AI 整理")
    w.analyze_button.setObjectName("primaryButton")
    w.analyze_button.clicked.connect(w.start_analysis)
    toolbar.addWidget(w.analyze_button)
    pane.addLayout(toolbar)
    w.report_view = ReportView()
    w.report_view.setOpenExternalLinks(False)
    w.report_view.setPlaceholderText("把长对话整理成重点。\n\n完成转写并配置文字 AI 服务后，即可生成摘要、决策与待办。")
    pane.addWidget(w.report_view, 1)
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
    w.statusBar().showMessage("就绪 · 导入录音开始工作")


def update_engine_hint(w):
    cloud = w.model_combo.currentIndex() == 0
    w.engine_hint.setText("录音上传至火山引擎，按账户套餐计费。词表仅供 AI 校对使用。" if cloud else
                         "FunASR 本地识别，录音无需上传。" + ("支持热词。" if w.model_combo.currentIndex() == 2 else "词表仅供 AI 校对使用。"))


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
