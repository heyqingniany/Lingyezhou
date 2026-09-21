"""Verify imports and real FFmpeg conversion without cloud calls or model downloads."""
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    import PySide6
    import openai
    import torch
    import torchaudio
    import modelscope
    from lingyezhou.asr.funasr_common import import_funasr
    from lingyezhou.audio.ffmpeg import FFmpegProcessor

    import_funasr()
    print(f"Python: {sys.version.split()[0]}")
    for name in ("PySide6", "funasr", "modelscope", "torch", "torchaudio", "openai", "imageio-ffmpeg"):
        print(f"{name}: {version(name)}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    processor = FFmpegProcessor()
    processor.require_available()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "stereo.wav"
        with wave.open(str(source), "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(44100)
            audio.writeframes(b"\x00\x00\x00\x00" * 44100)
        compressed = root / "sample.mp3"
        subprocess.run([processor.ffmpeg, "-y", "-loglevel", "error", "-i", str(source), str(compressed)], check=True)
        info = processor.probe(compressed)
        assert 0.9 <= info.duration_seconds <= 1.2, info
        converted = processor.convert(compressed, root / "converted.wav")
        with wave.open(str(converted), "rb") as audio:
            assert (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) == (1, 16000, 2)
    print("PASS: imports, FFmpeg MP3 probing and PCM conversion")


if __name__ == "__main__":
    main()
