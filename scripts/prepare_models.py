"""Download and load the default local ASR pipeline before first use."""
from pathlib import Path
import argparse
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lingyezhou.asr.sensevoice import SenseVoiceBackend
from lingyezhou.asr.model_store import ModelStore, human_size
from lingyezhou.config import AppConfig
import threading
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="Transcribe the model's bundled Chinese example")
    parser.add_argument("--engine", choices=["whisper", "sensevoice", "paraformer"], default="whisper")
    parser.add_argument("--directory", default="", help="Base directory for the application's dedicated model folder")
    parser.add_argument("--audio", help="Audio file for --smoke; otherwise use the existing SDK sample cache")
    args = parser.parse_args()
    os.environ.setdefault("MODELSCOPE_DOWNLOAD_PARALLEL_WORKERS", "4")
    store = ModelStore(args.directory or AppConfig.load().model_directory)
    last_update = 0.0
    def progress(current, total, message):
        nonlocal last_update
        if time.monotonic() - last_update > 1 or current == total:
            print(f"{human_size(current)} / {human_size(total)}: {message}", flush=True)
            last_update = time.monotonic()
    store.prepare(args.engine, progress, threading.Event())
    from lingyezhou.asr.paraformer import ParaformerBackend
    from lingyezhou.asr.whisper import WhisperBackend
    backends = {
        "whisper": WhisperBackend(store=store),
        "sensevoice": SenseVoiceBackend(store=store),
        "paraformer": ParaformerBackend(store=store),
    }
    backend = backends[args.engine]
    print(f"Loading prepared local models from {store.root}", flush=True)
    model = backend._get_model()
    print("Local ASR models loaded successfully.", flush=True)
    if args.smoke:
        from lingyezhou.audio.ffmpeg import FFmpegProcessor
        source = Path(args.audio) if args.audio else Path.home() / ".cache/modelscope/models/iic--SenseVoiceSmall/snapshots/master/example/zh.mp3"
        if not source.is_file():
            raise FileNotFoundError("No cached sample audio found. Use --smoke --audio <your-audio-file> to verify transcription.")
        output = Path(__file__).resolve().parents[1] / "output" / "runtime-smoke"
        output.mkdir(parents=True, exist_ok=True)
        audio = FFmpegProcessor().convert(source, output / "example_16k.wav")
        transcript = backend.transcribe(audio)
        if not transcript.segments or not any(segment.text.strip() for segment in transcript.segments):
            raise RuntimeError("ASR returned an empty transcript for the bundled Chinese example")
        transcript.save(output)
        print(f"PASS: real local transcription; {len(transcript.segments)} segments. Output: {output}", flush=True)


if __name__ == "__main__":
    main()
