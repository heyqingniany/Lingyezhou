"""Run an explicitly requested, billable cloud transcription for comparison."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lingyezhou.asr.doubao import DoubaoBackend
from lingyezhou.audio.ffmpeg import FFmpegProcessor
from lingyezhou.config import AppConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="上传录音至豆包云端识别（按账户套餐计费）")
    parser.add_argument("audio", type=Path)
    args = parser.parse_args()
    config = AppConfig.load()
    if not config.cloud_ready:
        print("尚未配置语音服务凭据。请在软件 设置 → 服务设置 中填写；未上传录音。")
        return 2
    processor = FFmpegProcessor()
    info = processor.probe(args.audio)
    if info.duration_seconds > 7200:
        print("极速版支持不超过 2 小时的音频；未上传。")
        return 2
    backend = DoubaoBackend(config.cloud_api_key, config.cloud_app_id, config.cloud_access_token, config.cloud_mode)
    print("正在上传并识别…", flush=True)
    transcript = backend.transcribe(processor.convert(args.audio))
    transcript.source_file = str(args.audio.resolve())
    transcript.duration_ms = int(info.duration_seconds * 1000)
    output = Path("output") / f"cloud_{backend.request_id}"
    transcript.save(output)
    (output / "provider_response.json").write_text(json.dumps(backend.raw_response, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "transcript.srt").write_text(transcript.to_srt(), encoding="utf-8")
    print(f"完成：{len(transcript.segments)} 段，{len(transcript.speakers)} 个说话人标签。结果：{output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
