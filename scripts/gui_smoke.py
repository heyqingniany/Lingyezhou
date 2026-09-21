from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from lingyezhou.logging_config import configure_logging
from lingyezhou.ui.main_window import MainWindow


configure_logging()
app = QApplication(sys.argv)
for filename in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf"):
    font_path = Path("C:/Windows/Fonts") / filename
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
window = MainWindow()
if os.environ.get("LINGYEZHOU_SMOKE_DEMO"):
    from lingyezhou.models.transcript import Transcript, TranscriptSegment
    window.transcript = Transcript("产品讨论（界面演示）.m4a", 192000, [
        TranscriptSegment(12000, 28000, 0, "今天主要讨论录音工具的使用体验。我们希望导入文件后，能够快速找到重点，也能保留完整的原始记录。"),
        TranscriptSegment(31000, 54000, 1, "我建议把原文和 AI 整理分开。阅读原文时保留时间和说话人，整理页则集中展示结论与待办。"),
        TranscriptSegment(58000, 81000, 0, "可以。导出也要放在容易找到的位置，文字、结构化数据和字幕都需要支持。"),
    ], {0: "主持人", 1: "产品设计师"})
    window._populate_roles()
    window._refresh_transcript()
    window._update_llm_state()
if os.environ.get("LINGYEZHOU_SMOKE_COMPACT"):
    window.resize(980, 680)
if tab := os.environ.get("LINGYEZHOU_SMOKE_TAB"):
    window.tabs.setCurrentIndex(int(tab))
if ai_tab := os.environ.get("LINGYEZHOU_SMOKE_AI_TAB"):
    window.ai_tabs.setCurrentIndex(int(ai_tab))
window.show()
if screenshot := os.environ.get("LINGYEZHOU_SMOKE_SCREENSHOT"):
    QTimer.singleShot(250, lambda: window.grab().save(screenshot))
QTimer.singleShot(500, app.quit)
raise SystemExit(app.exec())
