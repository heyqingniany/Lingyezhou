from __future__ import annotations

import base64
import json
import socket
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lingyezhou.asr.base import ASRBackend, ASRError
from lingyezhou.models.transcript import Transcript, TranscriptSegment


class DoubaoBackend(ASRBackend):
    """Seed ASR 2.0 submit/query or separately provisioned BigASR Flash."""

    ENDPOINT = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
    MAX_BYTES_BY_MODE = {"standard": 512_000_000, "flash": 100_000_000}

    def __init__(self, api_key: str = "", app_id: str = "", access_token: str = "", mode: str = "standard") -> None:
        self.mode = mode
        if mode not in {"standard", "flash"}:
            raise ASRError("未知的云端识别版本，请在服务设置中重新选择。")
        self.resource_id = "volc.seedasr.auc" if mode == "standard" else "volc.bigasr.auc_turbo"
        self.api_key = api_key.strip()
        self.app_id = app_id.strip()
        self.access_token = access_token.strip()
        self.request_id = ""
        self.raw_response: dict | None = None

    def transcribe(self, audio_path: Path | str, hotwords: list[str] | None = None) -> Transcript:
        if not self.api_key and not (self.app_id and self.access_token):
            raise ASRError("请在服务设置中填写豆包语音 API Key，或旧版 App ID 和 Access Token。")
        path = Path(audio_path)
        self.validate_audio(path)
        self.request_id = str(uuid.uuid4())
        headers = {
            "Content-Type": "application/json",
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": self.request_id,
            "X-Api-Sequence": "-1",
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        else:
            headers.update({"X-Api-App-Key": self.app_id, "X-Api-Access-Key": self.access_token})
        payload = {
            "user": {"uid": "lingyezhou"},
            "audio": {"data": base64.b64encode(path.read_bytes()).decode("ascii")},
            "request": {
                "model_name": "bigmodel", "enable_itn": True, "enable_punc": True,
                "enable_ddc": False, "show_utterances": True, "enable_speaker_info": True,
            },
        }
        # The UI marks cloud hotwords as metadata-only until the service's
        # request-level context contract has been verified for this API version.
        endpoint = self.ENDPOINT if self.mode == "flash" else "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
        request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            # Deliberately no automatic retry: a timeout can occur after billing.
            with urlopen(request, timeout=600) as response:
                status = response.headers.get("X-Api-Status-Code", "")
                if status != "20000000":
                    raise ASRError(f"豆包识别未成功（状态 {status or '缺失'}，请求 {self.request_id}）。请检查服务权限和额度。")
                raw = response.read()
                data = json.loads(raw.decode("utf-8")) if raw else {}
            if self.mode == "standard":
                task_dir = Path("output") / f"cloud_{self.request_id}"
                task_dir.mkdir(parents=True, exist_ok=True)
                (task_dir / "task.json").write_text(json.dumps({
                    "request_id": self.request_id, "resource_id": self.resource_id,
                    "source_file": str(path.resolve()), "status": "submitted",
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                deadline = time.monotonic() + 1800
                while time.monotonic() < deadline:
                    query = Request("https://openspeech.bytedance.com/api/v3/auc/bigmodel/query", data=b"{}", headers=headers, method="POST")
                    with urlopen(query, timeout=60) as response:
                        status = response.headers.get("X-Api-Status-Code", "")
                        if status == "20000000":
                            data = json.loads(response.read().decode("utf-8"))
                            break
                        if status not in {"20000001", "20000002"}:
                            raise ASRError(f"查询识别失败（状态 {status}，请求 {self.request_id}）。")
                    time.sleep(3)
                else:
                    raise ASRError(f"识别仍未完成，请求 {self.request_id}。请勿重复提交。")
        except HTTPError as exc:
            detail = exc.headers.get("X-Api-Message", "")
            if not detail:
                try:
                    body = json.loads(exc.read(4096).decode("utf-8"))
                    detail = str(body.get("message", body.get("error", "")))
                except (ValueError, UnicodeError):
                    detail = ""
            for secret in (self.api_key, self.access_token):
                if secret:
                    detail = detail.replace(secret, "[REDACTED]")
            raise ASRError(f"豆包识别 HTTP {exc.code}；资源 {self.resource_id}；请求 {self.request_id}。{detail[:500]}") from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise ASRError(f"云端连接失败或超时（请求 {self.request_id}）。未自动重试；请先检查网络和控制台调用记录。") from exc
        except (ValueError, UnicodeError) as exc:
            raise ASRError("云端返回无效 JSON，未覆盖已有转写。") from exc
        self.raw_response = data
        transcript = self.parse_response(data, path)
        transcript.hotwords = list(hotwords or [])
        return transcript

    def validate_audio(self, path: Path) -> None:
        maximum = self.MAX_BYTES_BY_MODE[self.mode]
        size = path.stat().st_size if path.is_file() else 0
        valid_size = 0 < size < maximum if self.mode == "standard" else 0 < size <= maximum
        if not valid_size:
            limit = "512 MB" if self.mode == "standard" else "100 MB"
            name = "标准版" if self.mode == "standard" else "极速版"
            raise ASRError(f"云端{name}需要非空且小于 {limit} 的上传文件。")

    @staticmethod
    def parse_response(data: dict, path: Path | str) -> Transcript:
        try:
            utterances = data["result"]["utterances"]
            if not isinstance(utterances, list) or not utterances:
                raise ValueError("missing utterances")
            segments = []
            speakers: dict[str, int] = {}
            roles: dict[int, str] = {}
            for item in utterances:
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                additions = item.get("additions") or {}
                label = str(additions.get("speaker", item.get("speaker", "unknown")))
                if label not in speakers:
                    speakers[label] = len(speakers)
                    if label in {"unknown", "", "-1"}:
                        roles[speakers[label]] = "未区分说话人"
                start, end = int(item["start_time"]), int(item["end_time"])
                if start < 0 or end <= start:
                    raise ValueError("invalid timestamps")
                segments.append(TranscriptSegment(start, end, speakers[label], text))
            if not segments:
                raise ValueError("empty transcript")
            duration = int((data.get("audio_info") or {}).get("duration") or max(s.end for s in segments))
            # Preserve server sentence boundaries and speaker assignments; no
            # local tiny-speaker smoothing that could erase a third participant.
            return Transcript(str(Path(path).resolve()), duration, segments, roles)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ASRError("云端结果缺少有效分句或时间戳，无法生成可靠的带时间轴转写。") from exc
