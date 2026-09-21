from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lingyezhou.analysis.report import render_history_report
from lingyezhou.history import HistoryStore
from lingyezhou.models.transcript import Transcript, TranscriptSegment


class HistoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = HistoryStore(Path(self.temp.name))

    @staticmethod
    def transcript(name: str, text: str = "回答") -> Transcript:
        return Transcript(
            source_file=f"C:/recordings/{name}",
            duration_ms=61000,
            segments=[TranscriptSegment(0, 12000, 0, text)],
            speaker_roles={0: "我"},
            hotwords=["FreeRTOS"],
        )

    def test_archive_roundtrip_and_report_update(self) -> None:
        record_id = self.store.add(self.transcript("first.m4a"), "interview")
        self.assertEqual(self.store.list()[0]["source_name"], "first.m4a")
        loaded = self.store.load_transcript(record_id)
        self.assertEqual(loaded.segments[0].text, "回答")
        self.assertEqual(loaded.speaker_roles, {0: "我"})

        loaded.segments[0].text = "校对后的回答"
        self.store.update_transcript(record_id, loaded)
        self.store.update_report(record_id, "interview", {"summary": "更清楚"}, "# 报告")
        messages = [{"question": "承诺了什么？", "answer": {"answer": "周五答复"}, "markdown": "## 问答"}]
        self.store.update_chat(record_id, messages)
        record = self.store.get(record_id)
        self.assertEqual(record["analysis_data"]["summary"], "更清楚")
        self.assertEqual(record["qa_messages"], messages)
        self.assertEqual(self.store.load_transcript(record_id).segments[0].text, "校对后的回答")

    def test_comparison_is_chronological_and_uses_reports_when_available(self) -> None:
        with patch("lingyezhou.history.datetime") as clock:
            clock.now.return_value.astimezone.return_value.strftime.return_value = "20260921T120000"
            clock.now.return_value.astimezone.return_value.isoformat.return_value = "2026-09-21T12:00:00+08:00"
            newer = self.store.add(self.transcript("new.m4a", "新回答"), "interview")
            clock.now.return_value.astimezone.return_value.strftime.return_value = "20260920T120000"
            clock.now.return_value.astimezone.return_value.isoformat.return_value = "2026-09-20T12:00:00+08:00"
            older = self.store.add(self.transcript("old.m4a", "旧回答"), "interview")
        self.store.update_report(newer, "interview", {"summary": "已有报告"}, "# 报告")

        payload = self.store.comparison_payload([newer, older])
        self.assertEqual([item["name"] for item in payload], ["old.m4a", "new.m4a"])
        self.assertIn("旧回答", payload[0]["transcript"])
        self.assertEqual(payload[1]["transcript"], "")
        self.assertEqual(payload[1]["report"], {"summary": "已有报告"})

    def test_invalid_record_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.store.get("../outside")

    def test_delete_removes_archive_but_not_source_audio(self) -> None:
        source = Path(self.temp.name) / "source.wav"
        source.write_bytes(b"audio")
        transcript = self.transcript("source.wav")
        transcript.source_file = str(source)
        record_id = self.store.add(transcript, "general")
        self.store.delete(record_id)
        self.assertEqual(self.store.list(), [])
        self.assertTrue(source.is_file())


class HistoryReportTests(unittest.TestCase):
    def test_report_contains_evidence_and_limits(self) -> None:
        markdown = render_history_report({
            "overview": "比较两次面试。",
            "improvements": [{"dimension": "表达结构", "finding": "更清楚", "evidence": ["第二次先给结论"]}],
            "regressions": [],
            "recurring_patterns": [{"pattern": "遗漏边界条件", "evidence": ["两次均未提到"]}],
            "next_actions": ["练习三分钟结构化回答"],
            "limitations": ["仅有两次记录"],
        })
        for text in ("有证据支持的进步", "第二次先给结论", "遗漏边界条件", "三分钟结构化回答", "仅有两次记录"):
            self.assertIn(text, markdown)


if __name__ == "__main__":
    unittest.main()
