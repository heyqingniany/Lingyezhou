"""Packaged runtime acceptance check; never calls a paid service."""
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

from lingyezhou.paths import resource_path


def run(window, arguments):
    output = Path(arguments[arguments.index("--self-test-report") + 1]).absolute()
    result = {"ok": False}
    try:
        assert resource_path("assets/lingyezhou.svg").is_file()
        assert resource_path("prompts/general_analysis.md").is_file()
        window.ffmpeg.require_available()
        result["window"] = window.windowTitle()
        result["startup_imported_torch"] = "torch" in sys.modules
        result["ffmpeg"] = window.ffmpeg.ffmpeg
        import av
        import ctranslate2
        import faster_whisper
        result["whisper_runtime"] = {
            "faster_whisper": faster_whisper.__version__,
            "ctranslate2": ctranslate2.__version__,
            "av": av.__version__,
        }
        if "--smoke-audio" in arguments:
            from lingyezhou.asr.model_store import ModelStore
            from lingyezhou.asr.sensevoice import SenseVoiceBackend
            from lingyezhou.asr.whisper import WhisperBackend
            base = arguments[arguments.index("--model-base") + 1] if "--model-base" in arguments else ""
            engine = arguments[arguments.index("--smoke-engine") + 1] if "--smoke-engine" in arguments else "sensevoice"
            audio = Path(arguments[arguments.index("--smoke-audio") + 1])
            normalized = window.ffmpeg.convert(audio, output.parent / "diagnostic_16k.wav")
            with patch.object(socket.socket, "connect", side_effect=RuntimeError("Network prohibited during offline inference")):
                backend = WhisperBackend(store=ModelStore(base)) if engine == "whisper" else SenseVoiceBackend(store=ModelStore(base))
                transcript = backend.transcribe(normalized)
            assert transcript.segments and any(segment.text.strip() for segment in transcript.segments)
            result["offline_engine"] = engine
            result["offline_transcript"] = transcript.to_display_text()
        result["ok"] = True
    except Exception as exc:
        import traceback
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
