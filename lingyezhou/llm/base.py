from __future__ import annotations

from abc import ABC, abstractmethod

from lingyezhou.models.transcript import Transcript


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    @abstractmethod
    def analyze_interview(self, transcript: Transcript) -> dict:
        pass

    @abstractmethod
    def detect_speaker_roles(self, transcript: Transcript) -> dict[int, str]:
        pass

