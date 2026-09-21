from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from lingyezhou.asr.base import ASRBackend, ASRError
from lingyezhou.asr.funasr_common import import_funasr, parse_result
from lingyezhou.models.transcript import Transcript
from lingyezhou.asr.model_store import ModelStore

logger = logging.getLogger(__name__)


class SenseVoiceBackend(ASRBackend):
    """SenseVoice + FSMN-VAD + CAM++ using the current FunASR AutoModel API."""

    def __init__(self, device: str | None = None, store: ModelStore | None = None) -> None:
        self.device = device
        self.store = store or ModelStore()
        self._model: Any = None
        self._lock = threading.Lock()

    @staticmethod
    def _detect_device() -> str:
        try:
            import torch
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _get_model(self) -> Any:
        with self._lock:
            if self._model is None:
                paths = self.store.paths("sensevoice")
                self.device = self.device or self._detect_device()
                AutoModel, _ = import_funasr()
                logger.info("Loading SenseVoice/FSMN-VAD/CAM++ on %s", self.device)
                self._model = AutoModel(
                    model=paths["sensevoice"],
                    vad_model=paths["vad"],
                    vad_kwargs={"max_single_segment_time": 30000},
                    punc_model=paths["punc"],
                    spk_model=paths["speaker"],
                    spk_mode="punc_segment",
                    device=self.device,
                    disable_update=True,
                    trust_remote_code=False,
                    check_latest=False,
                )
                logger.info("SenseVoice model pipeline loaded")
            return self._model

    def transcribe(self, audio_path: Path | str, hotwords: list[str] | None = None) -> Transcript:
        # SenseVoiceSmall has no documented hotword parameter. Keep the words for a
        # future postprocessor/Paraformer instead of pretending they affect decoding.
        if hotwords:
            logger.info("Saved %d hotwords; SenseVoice does not consume them", len(hotwords))
        try:
            _, postprocess = import_funasr()
            logger.info("ASR started: %s", audio_path)
            result = self._get_model().generate(
                input=str(audio_path),
                cache={},
                language="zh",
                use_itn=True,
                batch_size_s=60,
                merge_vad=True,
                merge_length_s=15,
            )
            transcript = parse_result(result, audio_path, postprocess)
            logger.info("ASR completed with %d segments", len(transcript.segments))
            return transcript
        except ASRError:
            logger.exception("ASR failed")
            raise
        except Exception as exc:
            logger.exception("ASR failed")
            raise ASRError(f"语音识别失败：{exc}") from exc
