from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from interviewlens.asr.base import ASRBackend, ASRError
from interviewlens.asr.funasr_common import import_funasr, parse_result
from interviewlens.models.transcript import Transcript

logger = logging.getLogger(__name__)


class ParaformerBackend(ASRBackend):
    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._model: Any = None
        self._lock = threading.Lock()

    def _get_model(self) -> Any:
        with self._lock:
            if self._model is None:
                AutoModel, _ = import_funasr()
                logger.info("Loading Paraformer/FSMN-VAD/CT-Punc/CAM++ on %s", self.device)
                self._model = AutoModel(
                    model="paraformer-zh",
                    vad_model="fsmn-vad",
                    punc_model="ct-punc",
                    spk_model="cam++",
                    device=self.device,
                    disable_update=True,
                )
            return self._model

    def transcribe(self, audio_path: Path | str, hotwords: list[str] | None = None) -> Transcript:
        try:
            _, postprocess = import_funasr()
            kwargs: dict[str, Any] = {"input": str(audio_path), "batch_size_s": 300}
            if hotwords:
                kwargs["hotword"] = " ".join(hotwords)
            return parse_result(self._get_model().generate(**kwargs), audio_path, postprocess)
        except ASRError:
            raise
        except Exception as exc:
            logger.exception("Paraformer ASR failed")
            raise ASRError(f"Paraformer 识别失败：{exc}") from exc

