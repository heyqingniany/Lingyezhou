from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from lingyezhou.asr.base import ASRError
from lingyezhou.models.transcript import Transcript, TranscriptSegment

logger = logging.getLogger(__name__)


def clean_asr_text(text: str) -> str:
    """Remove punctuation artifacts produced by composing rich ASR with CT-Punc."""
    value = re.sub(r"\s+", " ", text).strip()
    value = re.sub(r"^[，。！？、；：,.!?;\s]+", "", value)
    value = re.sub(r"[，,](?:\s*[，,])+", "，", value)
    value = re.sub(r"[。．.](?:\s*[。．.])+", "。", value)
    value = re.sub(r"[，,]\s*[。．.]", "。", value)
    value = re.sub(r"[。．.]\s*[，,]", "。", value)
    value = re.sub(r"[；;](?:\s*[；;])+", "；", value)
    return value.strip()


def compact_segments(
    segments: list[TranscriptSegment], max_gap_ms: int = 1500, max_duration_ms: int = 45000
) -> list[TranscriptSegment]:
    """Smooth tiny speaker islands and combine adjacent sentences into readable turns."""
    if not segments:
        return []
    smoothed = [TranscriptSegment(s.start, s.end, s.speaker, clean_asr_text(s.text)) for s in segments]
    for index in range(1, len(smoothed) - 1):
        previous, current, following = smoothed[index - 1:index + 2]
        if (
            current.end - current.start <= 1200
            and previous.speaker == following.speaker
            and current.speaker != previous.speaker
            and current.start - previous.end <= max_gap_ms
            and following.start - current.end <= max_gap_ms
        ):
            current.speaker = previous.speaker

    result: list[TranscriptSegment] = []
    for segment in smoothed:
        if not segment.text:
            continue
        if result:
            previous = result[-1]
            can_merge = (
                previous.speaker == segment.speaker
                and segment.start - previous.end <= max_gap_ms
                and segment.end - previous.start <= max_duration_ms
            )
            if can_merge:
                previous.end = segment.end
                previous.text = clean_asr_text(previous.text + segment.text)
                continue
        result.append(segment)
    return result


def import_funasr() -> tuple[Any, Any]:
    try:
        from funasr import AutoModel
        from funasr.utils.postprocess_utils import rich_transcription_postprocess
    except ImportError as exc:
        raise ASRError("未安装 FunASR。请在 Python 3.11 环境运行 pip install -r requirements.txt。") from exc
    return AutoModel, rich_transcription_postprocess


def parse_result(result: Any, audio_path: Path | str, postprocess: Any) -> Transcript:
    if not isinstance(result, list) or not result:
        raise ASRError("ASR 未返回可用结果。")
    item = result[0]
    sentence_info = item.get("sentence_info") or []
    segments: list[TranscriptSegment] = []
    for sentence in sentence_info:
        raw_text = sentence.get("text", sentence.get("sentence", ""))
        text = clean_asr_text(postprocess(str(raw_text)))
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start=int(sentence.get("start", 0)),
                end=int(sentence.get("end", sentence.get("start", 0))),
                speaker=int(sentence.get("spk", sentence.get("speaker", 0))),
                text=text,
            )
        )
    if segments:
        segments = compact_segments(segments)
    if not segments:
        text = postprocess(str(item.get("text", ""))).strip()
        if text:
            segments.append(TranscriptSegment(start=0, end=0, speaker=0, text=text))
    if not segments:
        raise ASRError("ASR 完成，但没有识别到语音内容。")
    duration = max((segment.end for segment in segments), default=0)
    return Transcript(source_file=str(Path(audio_path).resolve()), duration_ms=duration, segments=segments)
