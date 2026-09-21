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


class ParaformerBackend(ASRBackend):
    def __init__(self, device: str = "cpu", store: ModelStore | None = None) -> None:
        self.device = device
        self.store = store or ModelStore()
        self._model: Any = None
        self._lock = threading.Lock()

    def _get_model(self) -> Any:
        with self._lock:
            if self._model is None:
                paths = self.store.paths("paraformer")
                AutoModel, _ = import_funasr()
                logger.info("Loading Paraformer/FSMN-VAD/CT-Punc/CAM++ on %s", self.device)
                self._model = AutoModel(
                    model=paths["paraformer"],
                    vad_model=paths["vad"],
                    punc_model=paths["punc"],
                    spk_model=paths["speaker"],
                    device=self.device,
                    disable_update=True,
                    trust_remote_code=False,
                    check_latest=False,
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

