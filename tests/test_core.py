from __future__ import annotations

import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from lingyezhou.analysis.report import render_general_report, render_qa_answer, render_qa_conversation, render_report
from lingyezhou.asr.funasr_common import clean_asr_text, compact_segments, parse_result
from lingyezhou.audio.ffmpeg import FFmpegProcessor
from lingyezhou.models.transcript import Transcript, TranscriptSegment


def passthrough(value: str) -> str:
    return value


class AudioTests(unittest.TestCase):
    def test_standard_wav_probe_and_noop_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.wav"
            with wave.open(str(source), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b"\x00\x00" * 16000)
            processor = FFmpegProcessor()
            info = processor.probe(source)
            self.assertAlmostEqual(info.duration_seconds, 1.0)
            self.assertEqual(processor.convert(source), source.resolve())

    def test_cloud_upload_preserves_supported_audio_and_compresses_unsupported_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mp3 = root / "small.mp3"
            mp3.write_bytes(b"ID3 fixture")
            processor = FFmpegProcessor()
            self.assertEqual(processor.prepare_cloud_upload(mp3, "standard"), mp3.resolve())

            flac = root / "recording.flac"
            flac.write_bytes(b"fLaC fixture")
            target = root / "upload.mp3"

            def create_output(command, **kwargs):
                Path(command[-1]).write_bytes(b"compressed")

            with patch.object(processor, "require_available"), patch("lingyezhou.audio.ffmpeg.subprocess.run", side_effect=create_output) as run:
                result = processor.prepare_cloud_upload(flac, "flash", target)
            self.assertEqual(result, target.resolve())
            self.assertIn("libmp3lame", run.call_args.args[0])
            self.assertIn("64k", run.call_args.args[0])


class TranscriptTests(unittest.TestCase):
    def test_transcript_roundtrip(self) -> None:
        original = Transcript(
            "meeting.wav", 5000,
            [TranscriptSegment(100, 900, 2, "内容")],
            {2: "客户"}, ["术语"],
        )
        restored = Transcript.from_dict(original.to_dict())
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_parse_funasr_sentence_info(self) -> None:
        result = [{"sentence_info": [
            {"start": 1200, "end": 2500, "spk": 0, "text": "介绍一下 FreeRTOS"},
            {"start": 2700, "end": 4100, "spk": 1, "sentence": "它是实时操作系统"},
        ]}]
        transcript = parse_result(result, "input.wav", passthrough)
        self.assertEqual([s.speaker for s in transcript.segments], [0, 1])
        self.assertEqual(transcript.segments[1].start, 2700)

    def test_cleanup_and_compaction(self) -> None:
        self.assertEqual(clean_asr_text("。，，今天。。"), "今天。")
        segments = [
            TranscriptSegment(0, 1000, 0, "你好，"),
            TranscriptSegment(1100, 1500, 1, "嗯"),
            TranscriptSegment(1550, 2400, 0, "开始吧。"),
        ]
        compacted = compact_segments(segments)
        self.assertEqual(len(compacted), 1)
        self.assertEqual(compacted[0].speaker, 0)
        self.assertEqual(compacted[0].text, "你好，嗯开始吧。")

    def test_save_structured_outputs(self) -> None:
        transcript = Transcript(
            source_file="interview.wav",
            duration_ms=42000,
            segments=[TranscriptSegment(12000, 18000, 0, "问题")],
            speaker_roles={0: "面试官"},
        )
        with tempfile.TemporaryDirectory() as directory:
            json_path, md_path = transcript.save(directory)
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["segments"][0]["start"], 12000)
            self.assertEqual(data["hotwords"], [])
            self.assertIn("[00:12] 面试官", md_path.read_text(encoding="utf-8"))

    def test_plain_text_and_srt_exports(self) -> None:
        transcript = Transcript(
            source_file="meeting.wav",
            segments=[TranscriptSegment(1234, 4567, 0, "确认下周交付。")],
            speaker_roles={0: "项目经理"},
        )
        self.assertIn("项目经理", transcript.to_plain_text())
        self.assertIn("00:00:01,234 --> 00:00:04,567", transcript.to_srt())
        self.assertIn("项目经理：确认下周交付。", transcript.to_srt())

    def test_report_contains_required_sections(self) -> None:
        transcript = Transcript("a.wav", 10000, [TranscriptSegment(0, 1000, 0, "Q")])
        report = render_report({
            "summary": "概览",
            "questions": [{
                "question": "BASEPRI 是什么？", "candidate_answer": "回答", "analysis": "不完整",
                "missing_points": ["PRIMASK"], "better_answer": "参考回答",
            }],
            "knowledge_gaps": ["中断屏蔽"],
            "review_suggestions": ["复习 Cortex-M"],
        }, transcript)
        for heading in ("面试概览", "我的回答", "回答分析", "遗漏知识点", "更完整的参考回答", "知识盲区", "建议重点复习"):
            self.assertIn(heading, report)

    def test_general_report_contains_actions(self) -> None:
        transcript = Transcript("meeting.wav", 60000)
        report = render_general_report({
            "title": "项目周会",
            "summary": "讨论了交付计划。",
            "topics": ["进度"],
            "highlights": ["接口已完成"],
            "decisions": ["周五发布"],
            "action_items": [{"task": "补充测试", "owner": "小王", "deadline": "周四"}],
            "notes": ["需确认兼容性"],
        }, transcript)
        for value in ("项目周会", "主要话题", "决策与结论", "补充测试", "小王", "周四"):
            self.assertIn(value, report)

    def test_recording_qa_report_keeps_evidence_and_notice(self) -> None:
        answer = {
            "answer": "录音明确提到周五答复。",
            "evidence": [{"time": "03:12", "quote": "周五给你答复", "meaning": "说明答复时间"}],
            "uncertainties": ["未说明补偿金额"],
            "suggested_actions": ["回听并核对日期"],
            "professional_notice": "劳动规则取决于地区和事件日期，建议向当地专业人士核实。",
        }
        markdown = render_qa_answer("对方承诺了什么？", answer)
        conversation = render_qa_conversation([{"question": "对方承诺了什么？", "answer": answer}])
        for text in ("03:12", "周五给你答复", "未说明补偿金额", "建议向当地专业人士核实"):
            self.assertIn(text, markdown)
            self.assertIn(text, conversation)


if __name__ == "__main__":
    unittest.main()
