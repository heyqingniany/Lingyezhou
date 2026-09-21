from __future__ import annotations

from lingyezhou.llm.base import LLMProvider
from lingyezhou.models.transcript import Transcript


class InterviewAnalyzer:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def analyze(self, transcript: Transcript, mode: str = "interview") -> dict:
        if mode == "general" and hasattr(self.provider, "analyze_with_prompt"):
            return self.provider.analyze_with_prompt(transcript, "prompts/general_analysis.md")
        return self.provider.analyze_interview(transcript)

    def detect_roles(self, transcript: Transcript) -> dict[int, str]:
        return self.provider.detect_speaker_roles(transcript)
