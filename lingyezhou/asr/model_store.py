"""Explicit, resumable model installation. Importing this module never uses the network."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from lingyezhou.paths import user_data_dir


class DownloadCancelled(Exception):
    pass


@dataclass(frozen=True)
class Component:
    repo: str
    title: str
    required: tuple[str, ...]
    estimate: int
    source: str = "modelscope"
    revision: str = "master"
    pinned_files: tuple[tuple[str, int, str], ...] = ()


COMPONENTS = {
    "whisper": Component(
        "dropbox-dash/faster-whisper-large-v3-turbo",
        "Whisper large-v3-turbo 高质量识别",
        ("config.json", "model.bin", "preprocessor_config.json", "tokenizer.json", "vocabulary.json"),
        1_622_000_000,
        source="huggingface",
        revision="0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
        pinned_files=(
            ("config.json", 2263, "b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e"),
            ("model.bin", 1617884929, "e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da"),
            ("preprocessor_config.json", 340, "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711"),
            ("tokenizer.json", 2710337, "297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd"),
            ("vocabulary.json", 1068114, "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1"),
        ),
    ),
    "sensevoice": Component("iic/SenseVoiceSmall", "SenseVoice 语音识别",
        ("config.yaml", "configuration.json", "model.pt", "am.mvn", "tokens.json", "chn_jpn_yue_eng_ko_spectok.bpe.model"), 938_000_000),
    "paraformer": Component("iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch", "Paraformer 热词识别",
        ("config.yaml", "configuration.json", "model.pt", "am.mvn", "tokens.json", "seg_dict"), 1_100_000_000),
    "vad": Component("iic/speech_fsmn_vad_zh-cn-16k-common-pytorch", "语音分段",
        ("config.yaml", "configuration.json", "model.pt", "am.mvn"), 2_000_000),
    "punc": Component("iic/punc_ct-transformer_cn-en-common-vocab471067-large", "中英文标点",
        ("config.yaml", "configuration.json", "model.pt", "tokens.json", "jieba.c.dict", "jieba_usr_dict"), 1_187_000_000),
    "speaker": Component("iic/speech_campplus_sv_zh-cn_16k-common", "说话人区分",
        ("config.yaml", "configuration.json", "campplus_cn_common.bin"), 29_000_000),
}
ENGINES = {"whisper": ("whisper",),
           "sensevoice": ("sensevoice", "vad", "punc", "speaker"),
           "paraformer": ("paraformer", "vad", "punc", "speaker")}
ENGINE_NAMES = {"whisper": "Whisper large-v3-turbo（推荐 · 高质量）",
                "sensevoice": "SenseVoice（极速）",
                "paraformer": "Paraformer（中文热词）"}
MARKER = {"application": "Lingyezhou", "schema": 1}


def human_size(size: int) -> str:
    return f"{size / 1_000_000_000:.2f} GB" if size >= 1_000_000_000 else f"{size / 1_000_000:.1f} MB"


def _check_cancel(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise DownloadCancelled()


def _hash(path: Path, cancel: threading.Event) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            _check_cancel(cancel)
            digest.update(chunk)
    return digest.hexdigest()


def _safe(path: Path) -> None:
    # Windows junctions are reparse points too; do not traverse one for deletion.
    if path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400):
        raise ValueError(f"模型目录不能包含符号链接或目录联接：{path}")


class ModelStore:
    def __init__(self, base_directory: str | Path = ""):
        base = Path(base_directory).expanduser().absolute() if base_directory else user_data_dir()
        self.root = base / "Lingyezhou-models"

    def component_path(self, key: str) -> Path:
        if key not in COMPONENTS:
            raise ValueError("未知模型")
        for parent in [self.root, *self.root.parents]:
            _safe(parent)
        target = self.root / key
        _safe(target)
        return target

    def _own_root(self) -> None:
        self.component_path("sensevoice")
        marker = self.root / ".owner.json"
        _safe(marker)
        if marker.exists():
            if json.loads(marker.read_text(encoding="utf-8")) != MARKER:
                raise ValueError("该文件夹不属于聆页舟，请选择另一个模型存储位置。")
        elif self.root.exists() and any(self.root.iterdir()):
            raise ValueError("目标模型文件夹已有未识别内容，请选择空目录。")
        else:
            self.root.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps(MARKER), encoding="utf-8")

    def manifest(self, key: str) -> dict | None:
        try:
            directory = self.component_path(key)
            path = directory / "manifest.json"
            _safe(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("repo") != COMPONENTS[key].repo or data.get("schema") != 1:
                return None
            files = data["files"]
            if not isinstance(files, list) or {item["name"] for item in files} != set(COMPONENTS[key].required):
                return None
            for item in files:
                file = directory / item["name"]
                _safe(file)
                if not file.is_file() or file.stat().st_size != item["size"] or not re.fullmatch(r"[0-9a-fA-F]{64}", item["sha256"]):
                    return None
            return data
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def ready(self, engine: str) -> bool:
        return all(self.manifest(key) for key in ENGINES[engine])

    def paths(self, engine: str) -> dict[str, str]:
        if not self.ready(engine):
            raise RuntimeError("本地模型尚未准备好，请在「本地模型」中主动下载或修复后再转写。")
        return {key: str(self.component_path(key)) for key in ENGINES[engine]}

    def missing_estimate(self, engine: str) -> int:
        return sum(COMPONENTS[key].estimate for key in ENGINES[engine] if not self.manifest(key))

    def installed_size(self) -> int:
        return sum(sum(item["size"] for item in manifest["files"])
                   for key in COMPONENTS if (manifest := self.manifest(key)))

    def _metadata(self, key: str) -> list[dict]:
        component = COMPONENTS[key]
        if component.pinned_files:
            return [{"name": name, "size": size, "sha256": sha256}
                    for name, size, sha256 in component.pinned_files]
        query = urlencode({"Revision": "master", "Recursive": "true"})
        with urlopen(f"https://modelscope.cn/api/v1/models/{component.repo}/repo/files?{query}", timeout=20) as response:
            payload = json.load(response)
        entries = {entry["Path"]: entry for entry in payload["Data"]["Files"] if entry.get("Type") != "tree"}
        result = []
        for name in component.required:
            entry = entries.get(name)
            if not entry or not re.fullmatch(r"[0-9a-fA-F]{64}", entry.get("Sha256", "")) or int(entry.get("Size", 0)) <= 0:
                raise ValueError(f"模型文件清单不完整或缺少校验值：{component.title}/{name}")
            result.append({"name": name, "size": int(entry["Size"]), "sha256": entry["Sha256"].lower()})
        return result

    def prepare(self, engine: str, progress, cancel: threading.Event) -> None:
        with self.operation():
            self._prepare(engine, progress, cancel)

    @contextmanager
    def operation(self):
        from filelock import FileLock, Timeout
        self._own_root()
        lock_path = self.root / ".operation.lock"
        _safe(lock_path)
        try:
            lock = FileLock(str(lock_path), timeout=0)
            lock.acquire()
        except Timeout as exc:
            raise RuntimeError("另一个聆页舟窗口正在管理模型，请稍后重试。") from exc
        try:
            yield
        finally:
            lock.release()

    def _prepare(self, engine: str, progress, cancel: threading.Event) -> None:
        plans = []
        for key in ENGINES[engine]:
            _check_cancel(cancel)
            if self.manifest(key):
                continue
            progress(0, 0, f"正在获取文件清单：{COMPONENTS[key].title}")
            plans.append((key, self._metadata(key)))
        total = sum(item["size"] for _, files in plans for item in files)
        if not plans:
            progress(1, 1, "模型已准备好")
            return
        # Conservative space check includes partial downloads and copy staging.
        if shutil.disk_usage(self.root).free < total + 256 * 1024 * 1024:
            raise OSError(f"磁盘空间不足，请至少预留 {human_size(total + 256 * 1024 * 1024)} 后重试。")
        done = 0
        for key, files in plans:
            directory = self.component_path(key)
            directory.mkdir(exist_ok=True)
            for item in files:
                _check_cancel(cancel)
                target = directory / item["name"]
                partial = directory / (item["name"] + ".part")
                _safe(target)
                _safe(partial)
                label = f"{COMPONENTS[key].title} / {item['name']}"
                progress(done, total, f"正在校验：{label}")
                if target.is_file() and target.stat().st_size == item["size"] and _hash(target, cancel) == item["sha256"]:
                    done += item["size"]
                    continue
                # Reuse a previously downloaded SDK cache only after hash validation.
                cached = Path.home() / ".cache/modelscope/models" / COMPONENTS[key].repo.replace("/", "--") / "snapshots/master" / item["name"]
                if COMPONENTS[key].source != "modelscope":
                    cached = Path("__no_external_cache__")
                if cached.is_file() and cached.stat().st_size == item["size"] and _hash(cached, cancel) == item["sha256"]:
                    progress(done, total, f"复用本机已有模型：{label}")
                    with cached.open("rb") as source, partial.open("wb") as dest:
                        copied = 0
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            _check_cancel(cancel)
                            dest.write(chunk)
                            copied += len(chunk)
                            progress(done + copied, total, f"复用本机已有模型：{label}")
                else:
                    self._download(key, item, partial, lambda count: progress(done + count, total, label), cancel)
                progress(done + item["size"], total, f"正在校验：{label}")
                if partial.stat().st_size != item["size"]:
                    raise OSError(f"下载尚未完整，已保留进度，请重试：{label}")
                if _hash(partial, cancel) != item["sha256"]:
                    partial.unlink()
                    raise ValueError(f"模型文件校验失败，请重试：{label}")
                partial.replace(target)
                done += item["size"]
            manifest = directory / "manifest.json"
            temp = directory / "manifest.tmp"
            _safe(manifest)
            _safe(temp)
            temp.write_text(json.dumps({"schema": 1, "repo": COMPONENTS[key].repo, "files": files}), encoding="utf-8")
            temp.replace(manifest)
        progress(total, total, "模型已准备好，可以开始本地转写")

    def _download(self, key, item, partial, progress, cancel):
        offset = partial.stat().st_size if partial.exists() else 0
        if offset >= item["size"]:
            if offset == item["size"] and _hash(partial, cancel) == item["sha256"]:
                return
            partial.unlink()
            offset = 0
        component = COMPONENTS[key]
        if component.source == "huggingface":
            url = f"https://huggingface.co/{component.repo}/resolve/{component.revision}/{item['name']}"
        else:
            query = urlencode({"Revision": component.revision, "FilePath": item["name"]})
            url = f"https://modelscope.cn/api/v1/models/{component.repo}/repo?{query}"
        request = Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
        with urlopen(request, timeout=20) as response:
            content_range = response.headers.get("Content-Range", "")
            resumed = response.status == 206 or bool(content_range)
            if resumed and not content_range.startswith(f"bytes {offset}-"):
                raise ValueError("下载服务器返回的续传位置无效，请重试。")
            # Some mirrors return a ranged body with HTTP 200 and no Content-Range.
            # Keep the old prefix until the response length tells us whether it is
            # the complete file or the requested suffix; prepare() checks its hash.
            original_offset = offset
            ambiguous = bool(offset and not resumed)
            staging = partial.with_name(partial.name + ".response") if ambiguous else partial
            _safe(staging)
            if not resumed:
                offset = 0
            with staging.open("ab" if resumed else "wb") as stream:
                while True:
                    _check_cancel(cancel)
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    offset += len(chunk)
                    if offset > item["size"]:
                        raise ValueError("下载内容超出模型清单大小，请重试。")
                    stream.write(chunk)
                    progress(offset)
            if ambiguous:
                if offset == item["size"]:
                    staging.replace(partial)
                elif offset == item["size"] - original_offset:
                    with staging.open("rb") as source, partial.open("ab") as dest:
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            _check_cancel(cancel)
                            dest.write(chunk)
                    staging.unlink()
                else:
                    raise OSError("下载响应不完整，已保留原有进度，请重试。")

    def delete_engine(self, engine: str) -> list[str]:
        with self.operation():
            return self._delete_engine(engine)

    def _delete_engine(self, engine: str) -> list[str]:
        if engine not in ENGINES:
            raise ValueError("未知模型")
        installed_others = [name for name in ENGINES if name != engine and self.ready(name)]
        needed = {key for name in installed_others for key in ENGINES[name]}
        keys = [key for key in ENGINES[engine] if key not in needed]
        removed = []
        for key in keys:
            directory = self.component_path(key)
            if not directory.exists():
                continue
            for child in directory.rglob("*"):
                _safe(child)
            if directory.resolve().parent != self.root.resolve():
                raise ValueError("模型删除路径不在专用目录中。")
            shutil.rmtree(directory)
            removed.append(key)
        return removed
