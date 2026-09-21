from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from lingyezhou.llm.openai_compatible import OpenAICompatibleProvider
from lingyezhou.models.transcript import Transcript, TranscriptSegment


class RecordingQATests(unittest.TestCase):
    def test_payload_contains_timestamps_report_and_recent_context(self) -> None:
        transcript = Transcript(
            "离职协商.m4a",
            240000,
            [TranscriptSegment(192000, 198000, 1, "周五给你答复。")],
            {1: "人事"},
        )
        provider = OpenAICompatibleProvider("https://example.test", "key", "model")
        expected = {"answer": "记录中的答复时间是周五。", "evidence": []}
        with patch.object(provider, "_complete_json", return_value=expected) as complete:
            result = provider.answer_about_recording(
                transcript,
                "对方什么时候答复？",
                {"summary": "离职协商"},
                [{"question": "上一问", "answer": {"answer": "上一答"}}],
            )
        self.assertEqual(result, expected)
        system, user = complete.call_args.args
        payload = json.loads(user)
        self.assertIn("法律", system)
        self.assertEqual(payload["segments"][0]["time"], "03:12")
        self.assertEqual(payload["segments"][0]["speaker"], "人事")
        self.assertEqual(payload["report"]["summary"], "离职协商")
        self.assertEqual(payload["recent_conversation"][0]["question"], "上一问")


if __name__ == "__main__":
    unittest.main()
