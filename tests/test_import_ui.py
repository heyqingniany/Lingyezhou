from __future__ import annotations

import os
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from lingyezhou.models.transcript import Transcript, TranscriptSegment
from lingyezhou.ui.main_window import MainWindow


class ImportUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "讨论 录音.WAV"
        with wave.open(str(self.path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\x00\x00" * 16000)
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.wait_idle()
        self.window.close()
        self.temp.cleanup()

    def wait_idle(self):
        deadline = time.monotonic() + 5
        while self.window._threads and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertFalse(self.window._threads, "Import worker did not finish")

    def mime(self, urls):
        data = QMimeData()
        data.setUrls(urls)
        return data

    def enter(self, mime, target=None):
        event = QDragEnterEvent(QPoint(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        self.app.sendEvent(target or self.window, event)
        return event

    def seed_previous_result(self):
        self.window.audio_path = self.path
        previous = Transcript("previous.wav", 1000, [TranscriptSegment(0, 1000, 0, "旧内容")])
        self.window.transcript = previous
        self.window.report_markdown = "旧报告"
        self.window.transcript_view.setPlainText("旧内容")
        self.window.report_view.setPlainText("旧报告")
        self.window._populate_roles()
        self.window._update_llm_state()
        return previous

    def test_drop_over_editor_imports_and_clears_previous_result(self):
        self.seed_previous_result()
        data = self.mime([QUrl.fromLocalFile(str(self.path))])
        # Qt must route a drag over the text viewport up to the window.
        target = self.window.transcript_view.viewport()
        self.assertTrue(self.enter(data, target).isAccepted())
        self.assertTrue(self.window.drop_zone.property("dragActive"))
        drop = QDropEvent(QPointF(10, 10), Qt.CopyAction, data, Qt.LeftButton, Qt.NoModifier)
        self.app.sendEvent(target, drop)
        self.assertTrue(drop.isAccepted())
        self.wait_idle()
        self.assertEqual(self.window.audio_path, self.path.resolve())
        self.assertIsNone(self.window.transcript)
        self.assertEqual(self.window.report_markdown, "")
        self.assertEqual(self.window.role_table.rowCount(), 0)
        self.assertFalse(self.window.export_button.isEnabled())
        self.assertTrue(self.window.transcribe_button.isEnabled())
        self.assertFalse(self.window.drop_zone.property("dragActive"))

    def test_invalid_drops_preserve_current_result(self):
        previous = self.seed_previous_result()
        bad = Path(self.temp.name) / "notes.txt"
        bad.write_text("not audio")
        cases = [
            [QUrl.fromLocalFile(str(bad))],
            [QUrl.fromLocalFile(self.temp.name)],
            [QUrl.fromLocalFile(str(self.path))] * 2,
            [QUrl("https://example.com/recording.mp3")],
            [QUrl.fromLocalFile(str(self.path.with_name("missing.wav")))],
        ]
        for urls in cases:
            with self.subTest(urls=urls):
                self.assertFalse(self.enter(self.mime(urls)).isAccepted())
                self.assertIs(self.window.transcript, previous)
                self.assertTrue(self.window.statusBar().currentMessage())

    def test_busy_and_drag_leave(self):
        data = self.mime([QUrl.fromLocalFile(str(self.path))])
        self.assertTrue(self.enter(data).isAccepted())
        self.app.sendEvent(self.window, QDragLeaveEvent())
        self.assertFalse(self.window.drop_zone.property("dragActive"))
        self.window._set_busy(True, "测试处理中")
        self.assertFalse(self.enter(data).isAccepted())
        self.window.import_audio(self.path)
        self.assertIsNone(self.window.audio_path)
        self.assertFalse(self.window.import_action.isEnabled())
        self.window._set_busy(False, "完成")

    def test_probe_failure_keeps_previous_result(self):
        previous = self.seed_previous_result()
        with patch.object(self.window.ffmpeg, "probe", side_effect=ValueError("损坏的录音")), \
             patch.object(self.window, "_show_error") as error, \
             self.assertLogs("lingyezhou.ui.main_window", level="ERROR"):
            self.window.import_audio(self.path)
            self.wait_idle()
            error.assert_called_once()
        self.assertIs(self.window.transcript, previous)
        self.assertEqual(self.window.report_markdown, "旧报告")
        self.assertFalse(self.window._busy)

    def test_ctrl_o_imports_using_same_flow(self):
        self.window.activateWindow()
        self.window.hotwords.setFocus()
        QTest.qWait(20)
        with patch("lingyezhou.ui.main_window.QFileDialog.getOpenFileName", return_value=(str(self.path), "")) as dialog:
            QTest.keyClick(self.window.hotwords, Qt.Key_O, Qt.ControlModifier)
            self.wait_idle()
            dialog.assert_called_once()
        self.assertEqual(self.window.audio_path, self.path.resolve())


if __name__ == "__main__":
    unittest.main()
