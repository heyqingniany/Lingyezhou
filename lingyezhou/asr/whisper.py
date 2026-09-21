from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from lingyezhou.asr.base import ASRBackend, ASRError
from lingyezhou.asr.model_store import ModelStore
from lingyezhou.models.transcript import Transcript, TranscriptSegment

logger = logging.getLogger(__name__)


class WhisperBackend(ASRBackend):
    """High-quality local transcription with faster-whisper large-v3-turbo."""

    def __init__(self, store: ModelStore | None = None, device: str | None = None) -> None:
        self.store = store or ModelStore()
        self.device = device
        self._model: Any = None
        self._lock = threading.Lock()

    def _preferred_device(self) -> str:
        if self.device:
            return self.device
        try:
            import ctranslate2
            return "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
        except Exception:
            return "cpu"

    def _load(self, device: str) -> Any:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ASRError("Whisper 运行组件缺失，请重新安装或更新聆页舟。") from exc
        model_path = self.store.paths("whisper")["whisper"]
        compute_type = "float16" if device == "cuda" else "int8"
        return WhisperModel(model_path, device=device, compute_type=compute_type, local_files_only=True)

    def _get_model(self) -> Any:
        with self._lock:
            if self._model is None:
                device = self._preferred_device()
                logger.info("Loading Whisper large-v3-turbo on %s", device)
                try:
                    self._model = self._load(device)
                except Exception:
                    if device != "cuda":
                        raise
                    logger.warning("CUDA Whisper load failed; falling back to CPU", exc_info=True)
                    self._model = self._load("cpu")
            return self._model

    def transcribe(self, audio_path: Path | str, hotwords: list[str] | None = None) -> Transcript:
        try:
            prompt = "以下是录音中可能出现的专有名词：" + "、".join(hotwords) if hotwords else None
            raw_segments, info = self._get_model().transcribe(
                str(audio_path),
                language=None,
                multilingual=True,
                beam_size=5,
                vad_filter=True,
                condition_on_previous_text=True,
                initial_prompt=prompt,
                hotwords=" ".join(hotwords) if hotwords else None,
            )
            segments = [
                TranscriptSegment(
                    start=max(0, int(segment.start * 1000)),
                    end=max(0, int(segment.end * 1000)),
                    speaker=0,
                    text=segment.text.strip(),
                )
                for segment in raw_segments if segment.text.strip()
            ]
            return Transcript(
                source_file=str(audio_path),
                duration_ms=max(0, int(getattr(info, "duration", 0) * 1000)),
                segments=segments,
            )
        except ASRError:
            raise
        except Exception as exc:
            logger.exception("Whisper ASR failed")
            raise ASRError(f"Whisper 识别失败：{exc}") from exc
