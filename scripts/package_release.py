"""Audit and archive the tested Windows directory distribution."""
from pathlib import Path
import hashlib
import json
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    package = root / "dist/Lingyezhou"
    executable = package / "Lingyezhou.exe"
    for name in ("exe-startup.json", "exe-offline.json"):
        report = root / "output" / name
        result = json.loads(report.read_text(encoding="utf-8"))
        if not result.get("ok") or report.stat().st_mtime < executable.stat().st_mtime:
            raise RuntimeError(f"Run acceptance checks against the current EXE first: {report}")
    (package / "使用说明.txt").write_text(
        "聆页舟 — 让声音落成文字\n\n"
        "解压整个文件夹后运行 Lingyezhou.exe；请保留 _internal 文件夹。无需安装 Python。\n"
        "首次使用可选择云端或本地转写。云端需要自行配置语音服务凭据。\n"
        "豆包标准版支持小于 512 MB、5 小时的录音；极速版支持不超过 100 MB、2 小时。\n"
        "本地转写请在「本地模型 · 下载与管理」中确认下载；推荐 Whisper 模型约 1.62 GB。\n"
        "本发布包不含模型权重，支持下载进度、暂停续传、失败重试、更换位置和删除。\n"
        "AI 整理默认推荐 DeepSeek（deepseek-flash），也支持 OpenAI 和其他兼容服务。\n"
        "AI 整理结果和录音问答记录均可导出；法律类问答只用于材料整理和一般信息参考。\n"
        "每次转写会自动进入历史；可勾选 2–8 条记录生成多次复盘。\n\n"
        "配置、日志和结果默认保存在 %LOCALAPPDATA%\\Lingyezhou。\n"
        "模型默认保存在其 Lingyezhou-models 子目录，也可在软件中另选位置。\n"
        "可拖放 WAV、MP3、M4A、FLAC 到窗口，或按 Ctrl+O 导入录音。\n",
        encoding="utf-8-sig")
    (package / "LICENSE").write_text((root / "LICENSE").read_text(encoding="utf-8"), encoding="utf-8")
    files = sorted(path for path in package.rglob("*") if path.is_file())
    forbidden = [p for p in files if p.name in {"model.pt", "campplus_cn_common.bin", "config.local.json", ".env"}
                 or p.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac"}]
    if forbidden:
        raise RuntimeError(f"Unexpected model weights or user files: {forbidden}")
    target = root / "dist/Lingyezhou-Windows-x64.zip"
    print(f"Archiving {len(files)} files...", flush=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for file in files:
            archive.write(file, file.relative_to(package.parent))
    with zipfile.ZipFile(target) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Archive verification failed: {bad}")
    digest = hashlib.sha256()
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    target.with_suffix(".zip.sha256").write_text(f"{digest.hexdigest()}  {target.name}\n", encoding="ascii")
    report = {"archive": target.name, "archive_bytes": target.stat().st_size,
              "unpacked_bytes": sum(p.stat().st_size for p in files), "files": len(files),
              "model_weights_included": False, "private_files_found": len(forbidden),
              "sha256": digest.hexdigest()}
    (root / "output/release-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
