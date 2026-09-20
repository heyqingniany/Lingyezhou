from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


class FFmpegError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AudioInfo:
    path: Path
    duration_seconds: float
    size_bytes: int

    @property
    def readable_size(self) -> str:
        size = float(self.size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} GB"


class FFmpegProcessor:
    def __init__(self, ffmpeg: str | None = None, ffprobe: str | None = None) -> None:
        bundled_bin = Path(__file__).resolve().parents[2] / ".tools" / "ffmpeg" / "bin"
        bundled_ffmpeg = bundled_bin / "ffmpeg.exe"
        bundled_ffprobe = bundled_bin / "ffprobe.exe"
        self.ffmpeg = ffmpeg or (str(bundled_ffmpeg) if bundled_ffmpeg.is_file() else self._packaged_ffmpeg())
        self.ffprobe = ffprobe or (str(bundled_ffprobe) if bundled_ffprobe.is_file() else "ffprobe")

    @staticmethod
    def _packaged_ffmpeg() -> str:
        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except (ImportError, RuntimeError):
            return "ffmpeg"

    def is_available(self) -> bool:
        return self._executable_exists(self.ffmpeg)

    @staticmethod
    def _executable_exists(value: str) -> bool:
        return Path(value).is_file() or shutil.which(value) is not None

    def require_available(self) -> None:
        if not self.is_available():
            raise FFmpegError(
                "未检测到 FFmpeg。请运行 pip install -r requirements.txt，或安装 FFmpeg 并将其加入 PATH。"
            )

    def probe(self, audio_path: Path | str) -> AudioInfo:
        path = Path(audio_path)
        if not path.is_file():
            raise FFmpegError(f"音频文件不存在：{path}")
        duration = self._wave_duration(path)
        if duration is None:
            self.require_available()
            try:
                if self._executable_exists(self.ffprobe):
                    command = [
                        self.ffprobe, "-v", "error", "-show_entries", "format=duration",
                        "-of", "json", str(path),
                    ]
                    result = subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
                    duration = float(json.loads(result.stdout)["format"]["duration"])
                else:
                    # imageio-ffmpeg intentionally ships only ffmpeg. Its diagnostic
                    # output contains the container duration and avoids a second binary.
                    command = [self.ffmpeg, "-hide_banner", "-i", str(path), "-f", "null", "-"]
                    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
                    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
                    if not match:
                        raise ValueError("duration missing")
                    hours, minutes, seconds = match.groups()
                    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError, OSError) as exc:
                logger.exception("Audio probe failed: %s", path)
                raise FFmpegError("无法读取音频信息，请确认文件未损坏且格式受支持。") from exc
        return AudioInfo(path.resolve(), duration, path.stat().st_size)

    @staticmethod
    def _wave_duration(path: Path) -> float | None:
        if path.suffix.lower() != ".wav":
            return None
        try:
            with wave.open(str(path), "rb") as audio:
                return audio.getnframes() / float(audio.getframerate())
        except (wave.Error, OSError):
            return None

    @staticmethod
    def _is_target_wav(path: Path) -> bool:
        if path.suffix.lower() != ".wav":
            return False
        try:
            with wave.open(str(path), "rb") as audio:
                return (
                    audio.getnchannels() == 1
                    and audio.getframerate() == 16000
                    and audio.getsampwidth() == 2
                    and audio.getcomptype() == "NONE"
                )
        except (wave.Error, OSError):
            return False

    def convert(self, audio_path: Path | str, output_path: Path | str = "cache/input_16k.wav") -> Path:
        source = Path(audio_path)
        target = Path(output_path)
        if self._is_target_wav(source):
            logger.info("Audio already mono 16 kHz PCM WAV: %s", source)
            return source.resolve()
        self.require_available()
        target.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target),
        ]
        logger.info("Converting audio: %s -> %s", source, target)
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8")
        except subprocess.CalledProcessError as exc:
            logger.exception("FFmpeg conversion failed")
            detail = (exc.stderr or "").strip()
            raise FFmpegError(f"音频转换失败。{detail[-300:]}") from exc
        return target.resolve()
