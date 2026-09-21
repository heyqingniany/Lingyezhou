from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from lingyezhou.llm.base import LLMError, LLMProvider
from lingyezhou.models.transcript import Transcript
from lingyezhou.paths import resource_path

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str, prompt_path: Path | str = "prompts/interview_analysis.md") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.prompt_path = Path(prompt_path)

    def _client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMError("未安装 openai SDK，请运行 pip install -r requirements.txt。") from exc
        return OpenAI(base_url=self.base_url, api_key=self.api_key)

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
        if fenced:
            cleaned = fenced.group(1)
        else:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start >= 0 and end > start:
                cleaned = cleaned[start:end + 1]
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.exception("LLM JSON parse failed; response=%r", content[:1000])
            raise LLMError("AI 返回的内容不是有效 JSON，请重试或更换模型。") from exc
        if not isinstance(value, dict):
            raise LLMError("AI 返回的 JSON 顶层必须是对象。")
        return value

    def _complete_json(self, system: str, user: str) -> dict[str, Any]:
        logger.info("Sending LLM request to %s, model=%s", self.base_url, self.model)
        try:
            response = self._client().chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.2,
                max_tokens=8192,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or ""
            return self._extract_json(content)
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("LLM request failed")
            raise LLMError(f"AI 请求失败：{exc}") from exc

    @staticmethod
    def _transcript_payload(transcript: Transcript) -> str:
        return json.dumps(transcript.to_dict(), ensure_ascii=False)

    def analyze_interview(self, transcript: Transcript) -> dict:
        return self.analyze_with_prompt(transcript, self.prompt_path)

    def analyze_with_prompt(self, transcript: Transcript, prompt_path: Path | str) -> dict:
        path = Path(prompt_path)
        if not path.is_absolute():
            path = resource_path(str(path))
        if not path.is_file():
            raise LLMError(f"分析 Prompt 不存在：{path}")
        prompt = path.read_text(encoding="utf-8")
        return self._complete_json(prompt, self._transcript_payload(transcript))

    def analyze_history(self, records: list[dict]) -> dict:
        path = resource_path("prompts/history_analysis.md")
        if not path.is_file():
            raise LLMError("多次复盘 Prompt 不存在。")
        return self._complete_json(
            path.read_text(encoding="utf-8"),
            json.dumps({"records": records}, ensure_ascii=False),
        )

    def answer_about_recording(
        self,
        transcript: Transcript,
        question: str,
        report: dict | None = None,
        conversation: list[dict] | None = None,
    ) -> dict:
        path = resource_path("prompts/recording_qa.md")
        if not path.is_file():
            raise LLMError("录音问答 Prompt 不存在。")
        segments = []
        used = 0
        for segment in transcript.segments:
            text = segment.text.strip()
            if used + len(text) > 60000:
                break
            segments.append({
                "time": Transcript.format_time(segment.start),
                "speaker": transcript.role_for(segment.speaker),
                "text": text,
            })
            used += len(text)
        recent = []
        for item in (conversation or [])[-6:]:
            if isinstance(item, dict):
                recent.append({"question": item.get("question"), "answer": item.get("answer")})
        payload = {
            "question": question,
            "recording": Path(transcript.source_file).name,
            "segments": segments,
            "report": report or {},
            "recent_conversation": recent,
            "transcript_truncated": len(segments) < len(transcript.segments),
        }
        return self._complete_json(
            path.read_text(encoding="utf-8"),
            json.dumps(payload, ensure_ascii=False),
        )

    def detect_speaker_roles(self, transcript: Transcript) -> dict[int, str]:
        system = (
            "你负责从一段通用录音中推断说话人角色。根据语境使用简短、明确的角色名称，例如"
            "‘主持人’‘主讲人’‘客户’‘老师’‘面试官’或‘我’；无法确定时必须保留‘Speaker N’。"
            "返回 JSON，例如：{\"roles\":{\"0\":\"主讲人\",\"1\":\"参与者\"}}。不要返回其他文字。"
        )
        data = self._complete_json(system, self._transcript_payload(transcript))
        roles = data.get("roles", {})
        result: dict[int, str] = {}
        if isinstance(roles, dict):
            for key, value in roles.items():
                try:
                    speaker = int(key)
                except (TypeError, ValueError):
                    continue
                role = str(value).strip()
                if role and len(role) <= 20:
                    result[speaker] = role
        return result

    def polish_transcript(self, transcript: Transcript) -> dict[int, str]:
        system = """你是一名严格的中文录音转写校对员。输入包含带 index 的分段转写。
你的任务仅限于结合全文上下文修正明显的同音字、漏字、重复字、数字格式和标点，例如把语境明确的
“饭钱”改为“换签”、“薪头”改为“薪酬”。不得总结、删减信息、润色立场、改变数字、补写录音中
没有的信息，不能调整分段、说话人或时间戳。无法确定的地方必须保留原文。
只返回合法 JSON：{"segments":[{"index":0,"text":"校对后的原文"}]}。
必须返回每一个输入 index，顺序和数量必须完全一致。"""
        payload = {
            "hotwords": transcript.hotwords,
            "segments": [
                {
                    "index": index,
                    "speaker": transcript.role_for(segment.speaker),
                    "start_ms": segment.start,
                    "end_ms": segment.end,
                    "text": segment.text,
                }
                for index, segment in enumerate(transcript.segments)
            ],
        }
        data = self._complete_json(system, json.dumps(payload, ensure_ascii=False))
        values = data.get("segments")
        if not isinstance(values, list) or len(values) != len(transcript.segments):
            raise LLMError("AI 校对返回的分段数量与原稿不一致，已拒绝应用。")
        corrected: dict[int, str] = {}
        for item in values:
            if not isinstance(item, dict):
                raise LLMError("AI 校对返回了无效分段，已拒绝应用。")
            try:
                index = int(item.get("index"))
            except (TypeError, ValueError) as exc:
                raise LLMError("AI 校对返回了无效序号，已拒绝应用。") from exc
            text = str(item.get("text") or "").strip()
            if index in corrected or not 0 <= index < len(transcript.segments) or not text:
                raise LLMError("AI 校对返回的序号或文本无效，已拒绝应用。")
            corrected[index] = text
        if set(corrected) != set(range(len(transcript.segments))):
            raise LLMError("AI 校对缺少部分分段，已拒绝应用。")
        return corrected
