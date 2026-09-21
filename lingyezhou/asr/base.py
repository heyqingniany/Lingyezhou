from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from lingyezhou.models.transcript import Transcript


class ASRError(RuntimeError):
    pass


class ASRBackend(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path | str, hotwords: list[str] | None = None) -> Transcript:
        """Transcribe a mono 16 kHz PCM WAV into structured segments."""

